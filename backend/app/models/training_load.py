from sqlalchemy import Column, Numeric, DateTime, ForeignKey, Date
import uuid
from datetime import datetime
from app.database import Base, GUID


class TrainingLoad(Base):
    __tablename__ = "training_load"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    athlete_id = Column(GUID, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    load_date = Column(Date, nullable=False)
    ctl = Column(Numeric(8, 4))
    atl = Column(Numeric(8, 4))
    tsb = Column(Numeric(8, 4))
    daily_tss = Column(Numeric(8, 2))
    weekly_tss = Column(Numeric(8, 2))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
