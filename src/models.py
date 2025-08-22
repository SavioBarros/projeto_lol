from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .db import Base

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    team1 = Column(String)
    team2 = Column(String)
    start_time = Column(DateTime)
    odds = relationship("Odd", back_populates="match")

class Odd(Base):
    __tablename__ = "odds"
    id = Column(Integer, primary_key=True, index=True)
    market = Column(String)
    line = Column(Float)
    price = Column(Float)
    match_id = Column(Integer, ForeignKey("matches.id"))
    match = relationship("Match", back_populates="odds")
