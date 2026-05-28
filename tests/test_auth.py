"""
Authentication and authorization tests.
"""

from app.utils.auth import ROLE_VIEWER, authenticate


def test_local_admin_login():
  claims = authenticate("heisenberg", "P@ssw0rd")
  assert claims is not None
  assert claims.username == "heisenberg"
  assert claims.role == "admin"


def test_local_viewer_login():
  claims = authenticate("tester", "foobar123")
  assert claims is not None
  assert claims.username == "tester"
  assert claims.role == ROLE_VIEWER


def test_local_invalid_login():
  assert authenticate("heisenberg", "wrong") is None
