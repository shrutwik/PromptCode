from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitCounter(Base):
    __tablename__='rate_limit_counters'
    key: Mapped[str]=mapped_column(String(128),primary_key=True)
    window_start: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    count: Mapped[int]=mapped_column(Integer,nullable=False)
    expires_at: Mapped[int]=mapped_column(BigInteger,nullable=False,index=True)
