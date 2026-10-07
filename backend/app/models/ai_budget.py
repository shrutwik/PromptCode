from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIBudget(Base):
    __tablename__='ai_budgets'
    key: Mapped[str]=mapped_column(String(160),primary_key=True)
    requests: Mapped[int]=mapped_column(Integer,nullable=False)
    tokens: Mapped[int]=mapped_column(BigInteger,nullable=False)
    cost_micros: Mapped[int]=mapped_column(BigInteger,nullable=False)
