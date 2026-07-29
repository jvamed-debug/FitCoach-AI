from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base, GUID, JSONVariant


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    athlete_id = Column(GUID, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(255))
    source = Column(String(50), nullable=False)
    sport_type = Column(String(50), nullable=False)
    title = Column(String(255))
    description = Column(Text)
    start_time = Column(DateTime(timezone=True), nullable=False)
    duration_seconds = Column(Integer)
    distance_meters = Column(Numeric(10, 2))
    elevation_gain_meters = Column(Numeric(8, 2))
    avg_heart_rate = Column(Integer)
    max_heart_rate = Column(Integer)
    avg_power_watts = Column(Integer)
    normalized_power_watts = Column(Integer)
    max_power_watts = Column(Integer)
    avg_cadence = Column(Integer)
    calories = Column(Integer)
    tss = Column(Numeric(8, 2))
    # Proveniência do TSS (§13 do contrato do agente): distingue MEDIDA de ESTIMATIVA.
    #   'power'    → derivado de potência normalizada + FTP (medida confiável)
    #   'hr'       → estimado por FC via TRIMP (inferência, menos preciso)
    #   'stored'   → importado pronto da plataforma de origem (ex.: TrainingPeaks)
    #   'strength' → carga de força por duração × RPE (estimativa empírica)
    #   None       → sem dados suficientes para atribuir TSS
    tss_method = Column(String(20))
    if_score = Column(Numeric(5, 3))
    hr_zones = Column(JSONVariant)
    power_zones = Column(JSONVariant)
    raw_data = Column(JSONVariant)
    is_completed = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
