from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base, GUID


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    crm = Column(String(50))
    stripe_account_id = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    athletes = relationship("Athlete", back_populates="admin")
