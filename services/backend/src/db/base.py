from sqlalchemy.orm import DeclarativeBase


class AuthBase(DeclarativeBase):
    pass


class MedicalBase(DeclarativeBase):
    pass


class AuditBase(DeclarativeBase):
    pass
