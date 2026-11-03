"""Database package.

Session configuration intentionally lives in :mod:`src.db.sessions`; ORM
models can therefore be imported by Alembic or tooling without opening or
validating any service configuration.
"""
