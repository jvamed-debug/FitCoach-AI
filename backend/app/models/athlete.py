from sqlalchemy import Column, String, Boolean, DateTime, Date, Numeric, Integer, ForeignKey, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(30))
    birth_date = Column(Date)
    gender = Column(String(20))
    height_cm = Column(Numeric(5, 2))
    weight_kg = Column(Numeric(5, 2))
    sport_modalities = Column(ARRAY(String), default=[])
    primary_modality = Column(String(50))
    fitness_level = Column(String(20))
    goal = Column(Text)
    weekly_availability = Column(JSONB)
    ftp_watts = Column(Integer)
    max_hr = Column(Integer)
    resting_hr = Column(Integer)
    anamnese_encrypted = Column("anamnese_encrypted", String)  # pgp_sym_encrypt result stored as text
    is_active = Column(Boolean, default=True)
    onboarding_complete = Column(Boolean, default=False)
    apple_health_token = Column(UUID(as_uuid=True), default=uuid.uuid4)
    auto_report_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    admin = relationship("AdminUser", back_populates="athletes")
    lgpd_consents = relationship("LGPDConsent", back_populates="athlete", cascade="all, delete-orphan")
    platform_connections = relationship("PlatformConnection", back_populates="athlete", cascade="all, delete-orphan")


class PlatformConnection(Base):
    __tablename__ = "platform_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_athlete_id = Column(String(255))
    access_token_enc = Column(String)
    refresh_token_enc = Column(String)
    token_expires_at = Column(DateTime(timezone=True))
    scope = Column(Text)
    webhook_subscription_id = Column(String(255))
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime(timezone=True))
    sync_error = Column(Text)
    consecutive_failures = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    athlete = relationship("Athlete", back_populates="platform_connections")
