from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class LGPDConsent(Base):
    __tablename__ = "lgpd_consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    consent_version = Column(String(20), nullable=False)
    consented_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    revoked_at = Column(DateTime(timezone=True))
    revoke_reason = Column(Text)

    athlete = relationship("Athlete", back_populates="lgpd_consents")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    actor_type = Column(String(20), nullable=False)  # 'admin' | 'athlete' | 'system'
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True))
    ip_address = Column(String(45))
    metadata_ = Column("metadata", String)  # JSONB stored as text for flexibility
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class LGPDDeletionRequest(Base):
    __tablename__ = "lgpd_deletion_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    requested_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    deadline = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True))
    status = Column(String(20), default="pending")  # 'pending' | 'executed'
    confirmation_email_sent = Column(Boolean, default=False)
