"""
This module builds shared parts for other modules.
"""

import json
import os

from fastapi.templating import Jinja2Templates


with open("config.json") as config_json:
  config = json.load(config_json)
  db_path = config["db_path"]
  secret_key = config["secret_key"]
  auth_mode = config.get("auth_mode", "local")
  users = config.get("users", {})
  user_roles = config.get("user_roles", {})
  ldap_config = None

  if auth_mode == "ldap":
    from app.utils.ldap import LdapConfig

    ldap_config = LdapConfig(config.get("ldap", {}))


templates = Jinja2Templates(directory="templates")
