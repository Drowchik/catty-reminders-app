"""
Security, authentication, and role-based access control.
"""

import jwt
import secrets

from app import auth_mode, db_path, ldap_config, secret_key, user_roles, users
from app.utils.exceptions import ForbiddenException, UnauthorizedException, UnauthorizedPageException
from app.utils.storage import ReminderStorage

from fastapi import Cookie, Depends, Form
from fastapi.security import HTTPBasic
from pydantic import BaseModel
from typing import Literal, Optional

if ldap_config:
  from app.utils.ldap import authenticate_and_authorize, register_user as ldap_register_user


ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"
Role = Literal["admin", "viewer"]

basic_auth = HTTPBasic(auto_error=False)
auth_cookie_name = "reminders_session"


class AuthCookie(BaseModel):
  name: str
  token: str
  username: str
  role: Role
  email: Optional[str] = None

  @property
  def can_edit(self) -> bool:
    return self.role == ROLE_ADMIN


class SessionClaims(BaseModel):
  username: str
  role: Role
  email: Optional[str] = None


def serialize_token(claims: SessionClaims) -> str:
  payload = claims.model_dump(exclude_none=True)
  return jwt.encode(payload, secret_key, algorithm="HS256")


def deserialize_token(token: str) -> Optional[SessionClaims]:
  try:
    data = jwt.decode(token, secret_key, algorithms=["HS256"])
    username = data.get("username")
    role = data.get("role", ROLE_ADMIN)
    if not username or role not in (ROLE_ADMIN, ROLE_VIEWER):
      return None
    return SessionClaims(username=username, role=role, email=data.get("email"))
  except Exception:
    return None


def _local_role(username: str) -> Role:
  return user_roles.get(username, ROLE_ADMIN)


def _authenticate_local(username: str, password: str) -> Optional[SessionClaims]:
  stored = users.get(username)
  if stored is None:
    return None
  if not secrets.compare_digest(password, stored):
    return None
  return SessionClaims(username=username, role=_local_role(username))


def _authenticate_ldap(login: str, password: str) -> Optional[SessionClaims]:
  if not ldap_config:
    return None
  user_info = authenticate_and_authorize(ldap_config, login, password)
  if not user_info:
    return None
  return SessionClaims(
    username=user_info["username"],
    role=user_info["role"],
    email=user_info["email"],
  )


def authenticate(login: str, password: str) -> Optional[SessionClaims]:
  if auth_mode == "ldap":
    return _authenticate_ldap(login, password)
  return _authenticate_local(login, password)


def _claims_allowed(claims: SessionClaims) -> bool:
  if auth_mode == "ldap":
    return True
  return claims.username in users


def get_login_form_creds(username: str = Form(), password: str = Form()) -> Optional[AuthCookie]:
  claims = authenticate(username, password)
  if not claims:
    return None

  token = serialize_token(claims)
  return AuthCookie(
    name=auth_cookie_name,
    username=claims.username,
    role=claims.role,
    email=claims.email,
    token=token,
  )


def get_auth_cookie(reminders_session: Optional[str] = Cookie(default=None)) -> Optional[AuthCookie]:
  if not reminders_session:
    return None

  claims = deserialize_token(reminders_session)
  if not claims or not _claims_allowed(claims):
    return None

  return AuthCookie(
    name=auth_cookie_name,
    username=claims.username,
    role=claims.role,
    email=claims.email,
    token=reminders_session,
  )


def get_username_for_api(cookie: Optional[AuthCookie] = Depends(get_auth_cookie)) -> str:
  if not cookie:
    raise UnauthorizedException()
  return cookie.username


def get_username_for_page(cookie: Optional[AuthCookie] = Depends(get_auth_cookie)) -> str:
  if not cookie:
    raise UnauthorizedPageException()
  return cookie.username


def require_admin_api(cookie: Optional[AuthCookie] = Depends(get_auth_cookie)) -> AuthCookie:
  if not cookie:
    raise UnauthorizedException()
  if not cookie.can_edit:
    raise ForbiddenException()
  return cookie


def require_admin_page(cookie: Optional[AuthCookie] = Depends(get_auth_cookie)) -> AuthCookie:
  if not cookie:
    raise UnauthorizedPageException()
  if not cookie.can_edit:
    raise ForbiddenException()
  return cookie


def get_can_edit(cookie: Optional[AuthCookie] = Depends(get_auth_cookie)) -> bool:
  return bool(cookie and cookie.can_edit)


def get_storage_for_api(username: str = Depends(get_username_for_api)) -> ReminderStorage:
  return ReminderStorage(owner=username, db_path=db_path)


def get_storage_for_page(username: str = Depends(get_username_for_page)) -> ReminderStorage:
  return ReminderStorage(owner=username, db_path=db_path)


def register_ad_user(email: str, password: str) -> tuple[bool, str]:
  if auth_mode != "ldap" or not ldap_config:
    return False, "LDAP registration is disabled"
  return ldap_register_user(ldap_config, email, password)
