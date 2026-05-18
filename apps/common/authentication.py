"""Stateless JWT authentication for the participation-service.

Decodes the token locally without hitting the IAM database,
reading user id, email, and role from token claims.
"""

from __future__ import annotations
