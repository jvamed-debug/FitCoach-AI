from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base, GUID


class StrengthSession(Base):
    __tablename__ = "strength_sessions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    athlete_id = Column(GUID, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    session_date = Column(DateTime(timezone=True), nullable=False)
    session_type = Column(String(50))
    duration_minutes = Column(Integer)
    rpe_overall = Column(Integer)
    notes = Column(Text)
    tss = Column(Numeric(8, 2))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    exercises = relationship("StrengthExercise", back_populates="session", cascade="all, delete-orphan")


class StrengthExercise(Base):
    __tablename__ = "strength_exercises"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID, ForeignKey("strength_sessions.id", ondelete="CASCADE"), nullable=False)
    exercise_name = Column(String(255), nullable=False)
    sets = Column(Integer, nullable=False)
    reps = Column(Integer)
    duration_seconds = Column(Integer)
    load_kg = Column(Numeric(6, 2))
    rpe = Column(Integer)
    notes = Column(Text)
    exercise_order = Column(Integer)

    session = relationship("StrengthSession", back_populates="exercises")
