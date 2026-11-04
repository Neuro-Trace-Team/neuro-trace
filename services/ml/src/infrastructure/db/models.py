from uuid import UUID
from sqlalchemy import BigInteger, Float, Integer, Identity
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class AnalysisRow(Base):
    __tablename__ = "analyses"

    analysis_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    examination_id: Mapped[UUID] = mapped_column(index=True)
    time_stamp: Mapped[float] = mapped_column(Float)
    result: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    total_analyses_count: Mapped[int] = mapped_column(Integer)