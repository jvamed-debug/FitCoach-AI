from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, Text, String, Date
import uuid
from datetime import datetime
from app.database import Base, GUID


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    athlete_id = Column(GUID, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False)
    weight_kg = Column(Numeric(5, 2))
    sleep_hours = Column(Numeric(4, 2))
    sleep_quality = Column(Integer)
    hrv_ms = Column(Integer)
    resting_hr = Column(Integer)
    fatigue_score = Column(Integer)
    muscle_soreness = Column(Integer)
    stress_score = Column(Integer)
    motivation_score = Column(Integer)
    notes = Column(Text)
    source = Column(String(50), default="manual")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
