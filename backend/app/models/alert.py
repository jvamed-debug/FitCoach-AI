from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.database import Base, GUID


class AdminAlert(Base):
    __tablename__ = "admin_alerts"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    admin_id = Column(
        GUID,
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_id = Column(
        GUID,
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=True,
    )
    # 'overreaching' | 'no_workout' | 'no_metrics' | 'sync_failure' | 'milestone' | 'weekly_report'
    alert_type = Column(String(50), nullable=False)
    # 'info' | 'warning' | 'critical'
    severity = Column(String(20), default="info", nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
