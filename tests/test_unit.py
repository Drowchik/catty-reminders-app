"""
This module contains unit tests for the Catty app.
"""

from app.utils.auth import ROLE_ADMIN, ROLE_VIEWER, deserialize_token, serialize_token
from app.utils.auth import SessionClaims
from testlib.inputs import User


def test_token_serialization(user: User):
  claims = SessionClaims(username=user.username, role=ROLE_ADMIN)
  token = serialize_token(claims)
  assert token
  assert isinstance(token, str)
  assert token != user.username

  restored = deserialize_token(token)
  assert restored.username == user.username
  assert restored.role == ROLE_ADMIN


def test_token_serialization_viewer(user: User):
  claims = SessionClaims(username=user.username, role=ROLE_VIEWER)
  token = serialize_token(claims)
  restored = deserialize_token(token)
  assert restored.role == ROLE_VIEWER
