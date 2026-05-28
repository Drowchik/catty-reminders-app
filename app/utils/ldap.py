"""
Active Directory / LDAP authentication and user management.
"""

import logging
import os
from typing import Optional

from ldap3 import ALL, MODIFY_REPLACE, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException

logger = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"


class LdapConfig:
  def __init__(self, raw: dict):
    self.server = raw.get("server", "localhost")
    self.port = int(raw.get("port", 636))
    self.use_ssl = bool(raw.get("use_ssl", True))
    self.base_dn = raw["base_dn"]
    self.bind_user = os.environ.get("LDAP_BIND_USER", raw.get("bind_user", ""))
    self.bind_password = os.environ.get("LDAP_BIND_PASSWORD", raw.get("bind_password", ""))
    self.email_domain = raw.get("email_domain", "todolist.lan")
    self.staff_ou = raw.get("staff_ou", f"OU=Staff,{self.base_dn}")
    self.admin_group = raw.get("admin_group", "")
    self.viewer_group = raw.get("viewer_group", "")


def normalize_email(login: str, email_domain: str) -> str:
  login = login.strip()
  if "@" in login:
    return login
  return f"{login}@{email_domain}"


def _server(cfg: LdapConfig) -> Server:
  return Server(cfg.server, port=cfg.port, use_ssl=cfg.use_ssl, get_info=ALL)


def authenticate_user(cfg: LdapConfig, email: str, password: str) -> bool:
  try:
    conn = Connection(_server(cfg), user=email, password=password, auto_bind=True)
    conn.unbind()
    return True
  except LDAPException as exc:
    logger.warning("LDAP bind failed for %s: %s", email, exc)
    return False


def _service_connection(cfg: LdapConfig) -> Connection:
  return Connection(
    _server(cfg),
    user=cfg.bind_user,
    password=cfg.bind_password,
    auto_bind=True,
  )


def _groups_from_entry(entry) -> list[str]:
  if not entry.memberOf:
    return []
  values = entry.memberOf.values if hasattr(entry.memberOf, "values") else entry.memberOf
  return [str(group) for group in values]


def resolve_role(member_of: list[str], admin_group: str, viewer_group: str) -> Optional[str]:
  normalized = {group.lower() for group in member_of}
  if admin_group and admin_group.lower() in normalized:
    return ROLE_ADMIN
  if viewer_group and viewer_group.lower() in normalized:
    return ROLE_VIEWER
  return None


def lookup_user(cfg: LdapConfig, email: str) -> Optional[dict]:
  conn = None
  try:
    conn = _service_connection(cfg)
    conn.search(
      search_base=cfg.base_dn,
      search_filter=f"(&(objectClass=user)(userPrincipalName={email}))",
      search_scope=SUBTREE,
      attributes=["sAMAccountName", "userPrincipalName", "memberOf"],
    )
    if not conn.entries:
      return None

    entry = conn.entries[0]
    member_of = _groups_from_entry(entry)
    role = resolve_role(member_of, cfg.admin_group, cfg.viewer_group)
    if not role:
      return None

    return {
      "username": str(entry.sAMAccountName),
      "email": str(entry.userPrincipalName),
      "role": role,
      "groups": member_of,
    }
  except LDAPException as exc:
    logger.error("LDAP lookup failed for %s: %s", email, exc)
    return None
  finally:
    if conn:
      conn.unbind()


def authenticate_and_authorize(cfg: LdapConfig, login: str, password: str) -> Optional[dict]:
  email = normalize_email(login, cfg.email_domain)
  if not authenticate_user(cfg, email, password):
    return None
  return lookup_user(cfg, email)


def register_user(cfg: LdapConfig, email: str, password: str) -> tuple[bool, str]:
  username = email.split("@")[0]
  user_dn = f"CN={username},{cfg.staff_ou}"
  conn = None

  try:
    conn = _service_connection(cfg)
    conn.search(cfg.base_dn, f"(sAMAccountName={username})", SUBTREE)
    if conn.entries:
      return False, f"User {username} already exists"

    quoted_password = f'"{password}"'
    encoded_password = quoted_password.encode("utf-16-le")
    attrs = {
      "objectClass": ["top", "person", "organizationalPerson", "user"],
      "cn": username,
      "sn": username,
      "sAMAccountName": username,
      "userPrincipalName": email,
      "displayName": username,
      "unicodePwd": encoded_password,
      "userAccountControl": "514",
    }

    if not conn.add(user_dn, attributes=attrs):
      return False, f"Create failed: {conn.result}"

    if not conn.modify(user_dn, {"userAccountControl": [(MODIFY_REPLACE, ["512"])]}):
      return False, f"User created but not activated: {conn.result}"

    return True, f"User {email} created and activated"
  except LDAPException as exc:
    return False, str(exc)
  finally:
    if conn:
      conn.unbind()
