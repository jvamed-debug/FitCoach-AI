from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Date, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime
from app.database import Base


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    recommendation_date = Column(Date, nullable=False)
    ai_provider = Column(String(50), nullable=False)
    ai_model = Column(String(100))
    workout_type = Column(String(50))
    title = Column(String(255))
    recommendation_text = Column(Text, nullable=False)
    structured_plan = Column(JSONB)
    nutrition_plan = Column(JSONB)
    rationale = Column(Text)
    input_context = Column(JSONB)
    tokens_used = Column(Integer)
    generation_time_ms = Column(Integer)
    feedback_rating = Column(Integer)
    feedback_notes = Column(Text)
    was_followed = Column(Boolean)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
