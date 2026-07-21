# FITNESS PERFORMANCE APP — Especificação para Claude Code

> **Instruções para Claude Code:** Leia este documento na íntegra antes de criar qualquer arquivo.
> Execute cada fase em ordem. Ao final de cada fase, verifique se todos os arquivos foram criados e os testes básicos passam.

---

## VISÃO GERAL DO PRODUTO

Aplicação web pessoal de performance esportiva que combina **musculação e ciclismo**. O sistema integra dados do Strava (e futuramente Garmin/TrainingPeaks), permite registro manual de treinos de força, calcula métricas de carga de treino (CTL/ATL/TSB) e usa IA (Anthropic Claude + OpenAI com roteamento flexível) para gerar recomendações diárias de treino com base no histórico e estado de fadiga do atleta.

**Usuário-alvo inicial:** uso pessoal de um atleta (educador físico / ciclista + musculação).  
**Arquitetura:** escalável para suportar múltiplos atletas futuramente.

---

## STACK DEFINITIVA

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + FastAPI + Pydantic v2 |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Banco de dados | PostgreSQL via Supabase |
| Auth | Supabase Auth (JWT) + OAuth 2.0 para Strava |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind CSS |
| Componentes UI | shadcn/ui |
| Gráficos | Recharts |
| AI Router | Anthropic Claude API + OpenAI API (provider abstrato) |
| Deploy Backend | Railway ou Render |
| Deploy Frontend | Vercel |
| Tarefas agendadas | APScheduler (embutido no backend) |

---

## FASE 1 — ESTRUTURA DO PROJETO

Crie a seguinte estrutura de pastas e arquivos (todos os arquivos listados devem ser criados com conteúdo real, não placeholders):

```
fitness-performance/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── workouts.py
│   │   │   ├── strength.py
│   │   │   ├── metrics.py
│   │   │   ├── recommendations.py
│   │   │   └── ai.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── strava_service.py
│   │   │   ├── tp_service.py
│   │   │   ├── ai_service.py
│   │   │   ├── training_load.py
│   │   │   └── scheduler.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── athlete.py
│   │   │   ├── workout.py
│   │   │   ├── strength.py
│   │   │   ├── metric.py
│   │   │   └── recommendation.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── calculations.py
│   │       └── oauth.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── scripts/
│   │   └── daily_update.py
│   ├── tests/
│   │   ├── test_calculations.py
│   │   └── test_ai_service.py
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── globals.css
│   │   ├── dashboard/
│   │   │   └── page.tsx
│   │   ├── workouts/
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   ├── strength/
│   │   │   ├── page.tsx
│   │   │   └── new/
│   │   │       └── page.tsx
│   │   ├── metrics/
│   │   │   └── page.tsx
│   │   ├── recommendations/
│   │   │   └── page.tsx
│   │   └── auth/
│   │       ├── login/
│   │       │   └── page.tsx
│   │       └── callback/
│   │           └── strava/
│   │               └── page.tsx
│   ├── components/
│   │   ├── ui/                    # shadcn/ui components (instale via CLI)
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── AppShell.tsx
│   │   ├── dashboard/
│   │   │   ├── TrainingLoadChart.tsx
│   │   │   ├── FatigueCard.tsx
│   │   │   ├── WeeklyTSS.tsx
│   │   │   └── DailyRecommendation.tsx
│   │   ├── workouts/
│   │   │   ├── WorkoutCard.tsx
│   │   │   ├── WorkoutList.tsx
│   │   │   └── PowerZoneChart.tsx
│   │   ├── strength/
│   │   │   ├── StrengthForm.tsx
│   │   │   └── ExerciseLog.tsx
│   │   ├── metrics/
│   │   │   ├── MetricsForm.tsx
│   │   │   └── SleepQualityChart.tsx
│   │   └── charts/
│   │       ├── CTLATLTSBChart.tsx
│   │       └── ProgressChart.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   ├── supabase.ts
│   │   └── types.ts
│   ├── hooks/
│   │   ├── useWorkouts.ts
│   │   ├── useMetrics.ts
│   │   └── useRecommendation.ts
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── next.config.ts
│   └── .env.example
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql
├── docs/
│   ├── ARCHITECTURE.md
│   ├── STRAVA_SETUP.md
│   └── AI_PROMPTS.md
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## FASE 2 — BANCO DE DADOS (Supabase PostgreSQL)

Crie o arquivo `supabase/migrations/001_initial_schema.sql` com o seguinte schema completo:

```sql
-- Extensões
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tabela de atletas
CREATE TABLE IF NOT EXISTS athletes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL, -- referência ao Supabase Auth
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    gender VARCHAR(10),
    birth_date DATE,
    height_cm NUMERIC(5,2),
    weight_kg NUMERIC(5,2),
    ftp_watts INTEGER,              -- Functional Threshold Power
    max_hr INTEGER,                 -- Frequência cardíaca máxima
    goals TEXT,                     -- Objetivos do atleta em texto livre
    weekly_availability JSONB,      -- Ex: {"cycling": ["tue","thu","sat"], "strength": ["mon","fri"]}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conexões OAuth com plataformas externas
CREATE TABLE IF NOT EXISTS platform_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- 'strava', 'garmin', 'trainingpeaks'
    provider_athlete_id VARCHAR(255),
    access_token TEXT,              -- armazenar criptografado em produção
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    scope TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, provider)
);

-- Treinos (importados ou planejados)
CREATE TABLE IF NOT EXISTS workouts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    external_id VARCHAR(255),       -- ID na plataforma de origem
    source VARCHAR(50) NOT NULL,    -- 'strava', 'trainingpeaks', 'manual', 'planned'
    sport_type VARCHAR(50) NOT NULL, -- 'cycling', 'running', 'strength', 'rest', 'mobility'
    title VARCHAR(255),
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER,
    distance_meters NUMERIC(10,2),
    elevation_gain_meters NUMERIC(8,2),
    avg_heart_rate INTEGER,
    max_heart_rate INTEGER,
    avg_power_watts INTEGER,
    normalized_power_watts INTEGER,
    max_power_watts INTEGER,
    avg_cadence INTEGER,
    calories INTEGER,
    tss NUMERIC(8,2),               -- Training Stress Score
    if_score NUMERIC(5,3),          -- Intensity Factor
    hr_zones JSONB,                 -- {"z1": 600, "z2": 1200, ...} em segundos
    power_zones JSONB,
    raw_data JSONB,                 -- dados brutos da API de origem
    is_completed BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessões de musculação
CREATE TABLE IF NOT EXISTS strength_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    session_date DATE NOT NULL,
    session_type VARCHAR(50),       -- 'upper', 'lower', 'full_body', 'push', 'pull'
    duration_minutes INTEGER,
    rpe_overall INTEGER CHECK (rpe_overall BETWEEN 1 AND 10),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Exercícios dentro de uma sessão de musculação
CREATE TABLE IF NOT EXISTS strength_exercises (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES strength_sessions(id) ON DELETE CASCADE,
    exercise_name VARCHAR(255) NOT NULL,
    sets INTEGER NOT NULL,
    reps INTEGER,                   -- NULL para exercícios com tempo
    duration_seconds INTEGER,       -- para exercícios por tempo
    load_kg NUMERIC(6,2),
    rpe INTEGER CHECK (rpe BETWEEN 1 AND 10),
    notes TEXT,
    exercise_order INTEGER
);

-- Métricas diárias de saúde e bem-estar
CREATE TABLE IF NOT EXISTS daily_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    weight_kg NUMERIC(5,2),
    sleep_hours NUMERIC(4,2),
    sleep_quality INTEGER CHECK (sleep_quality BETWEEN 1 AND 10),
    hrv_ms INTEGER,                 -- Heart Rate Variability
    resting_hr INTEGER,
    fatigue_score INTEGER CHECK (fatigue_score BETWEEN 1 AND 10),
    muscle_soreness INTEGER CHECK (muscle_soreness BETWEEN 1 AND 10),
    stress_score INTEGER CHECK (stress_score BETWEEN 1 AND 10),
    motivation_score INTEGER CHECK (motivation_score BETWEEN 1 AND 10),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, metric_date)
);

-- Carga de treino calculada (CTL/ATL/TSB)
CREATE TABLE IF NOT EXISTS training_load (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    load_date DATE NOT NULL,
    ctl NUMERIC(8,4),               -- Chronic Training Load (Fitness)
    atl NUMERIC(8,4),               -- Acute Training Load (Fatigue)
    tsb NUMERIC(8,4),               -- Training Stress Balance (Form)
    daily_tss NUMERIC(8,2),
    weekly_tss NUMERIC(8,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, load_date)
);

-- Recomendações geradas pela IA
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    recommendation_date DATE NOT NULL,
    ai_provider VARCHAR(50) NOT NULL, -- 'anthropic', 'openai'
    ai_model VARCHAR(100),
    workout_type VARCHAR(50),       -- 'cycling_endurance', 'cycling_intervals', 'strength', 'rest', 'mobility'
    title VARCHAR(255),
    recommendation_text TEXT NOT NULL,
    structured_plan JSONB,          -- plano estruturado parseado da resposta da IA
    rationale TEXT,                 -- explicação do motivo da recomendação
    input_context JSONB,            -- contexto enviado para a IA (para auditoria)
    feedback_rating INTEGER CHECK (feedback_rating BETWEEN 1 AND 5),
    feedback_notes TEXT,
    was_followed BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, recommendation_date)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_workouts_athlete_date ON workouts(athlete_id, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_strength_sessions_athlete_date ON strength_sessions(athlete_id, session_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_athlete_date ON daily_metrics(athlete_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_training_load_athlete_date ON training_load(athlete_id, load_date DESC);
CREATE INDEX IF NOT EXISTS idx_ai_recommendations_athlete_date ON ai_recommendations(athlete_id, recommendation_date DESC);

-- RLS (Row Level Security) — habilitar para produção
ALTER TABLE athletes ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE workouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE strength_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE strength_exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_load ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_recommendations ENABLE ROW LEVEL SECURITY;

-- Policies RLS básicas (ajustar conforme necessidade)
CREATE POLICY "athletes_own_data" ON athletes FOR ALL USING (user_id = auth.uid());
CREATE POLICY "workouts_own_data" ON workouts FOR ALL USING (
    athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid())
);
CREATE POLICY "strength_own_data" ON strength_sessions FOR ALL USING (
    athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid())
);
CREATE POLICY "metrics_own_data" ON daily_metrics FOR ALL USING (
    athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid())
);
CREATE POLICY "load_own_data" ON training_load FOR ALL USING (
    athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid())
);
CREATE POLICY "recommendations_own_data" ON ai_recommendations FOR ALL USING (
    athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid())
);
```

---

## FASE 3 — BACKEND (FastAPI)

### 3.1 `backend/requirements.txt`

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
sqlalchemy[asyncio]==2.0.31
asyncpg==0.29.0
alembic==1.13.2
pydantic==2.7.4
pydantic-settings==2.3.4
python-jose[cryptography]==3.3.0
httpx==0.27.0
anthropic==0.29.0
openai==1.35.10
apscheduler==3.10.4
python-dotenv==1.0.1
supabase==2.5.1
cryptography==42.0.8
tenacity==8.4.1
pytest==8.2.2
pytest-asyncio==0.23.7
```

### 3.2 `backend/.env.example`

```env
# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
DATABASE_URL=postgresql+asyncpg://postgres:password@db.xxxx.supabase.co:5432/postgres

# Auth
SECRET_KEY=your-super-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Strava OAuth
STRAVA_CLIENT_ID=your-strava-client-id
STRAVA_CLIENT_SECRET=your-strava-client-secret
STRAVA_REDIRECT_URI=http://localhost:3000/auth/callback/strava

# AI Providers
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DEFAULT_AI_PROVIDER=anthropic   # 'anthropic' ou 'openai'
ANTHROPIC_MODEL=claude-opus-4-6
OPENAI_MODEL=gpt-4o

# App
APP_ENV=development
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

### 3.3 `backend/app/config.py`

```python
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    database_url: str

    # Auth
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Strava
    strava_client_id: str
    strava_client_secret: str
    strava_redirect_uri: str

    # AI
    anthropic_api_key: str
    openai_api_key: str
    default_ai_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_model: str = "claude-opus-4-6"
    openai_model: str = "gpt-4o"

    # App
    app_env: Literal["development", "production"] = "development"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### 3.4 `backend/app/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### 3.5 `backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.routers import auth, workouts, strength, metrics, recommendations, ai
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="Fitness Performance API",
    description="API para análise e recomendação de treinos de ciclismo e musculação",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(workouts.router, prefix="/api/workouts", tags=["workouts"])
app.include_router(strength.router, prefix="/api/strength", tags=["strength"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.app_env}
```

### 3.6 `backend/app/models/workout.py`

```python
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from datetime import datetime


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
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
    if_score = Column(Numeric(5, 3))
    hr_zones = Column(JSONB)
    power_zones = Column(JSONB)
    raw_data = Column(JSONB)
    is_completed = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Pydantic schemas (criar em app/schemas/workout.py)
```

### 3.7 `backend/app/utils/calculations.py`

Implemente **todas** as funções abaixo com lógica real:

```python
"""
Cálculos de carga de treino baseados no modelo de Banister (PMC).
CTL = Chronic Training Load = média exponencial 42 dias (Fitness)
ATL = Acute Training Load  = média exponencial 7 dias  (Fatigue)
TSB = Training Stress Balance = CTL - ATL              (Form)
TSS = Training Stress Score (por sessão)
"""

def calculate_tss_cycling(
    duration_seconds: int,
    normalized_power: int,
    ftp: int,
    intensity_factor: float | None = None,
) -> float:
    """
    TSS = (duration_sec × NP × IF) / (FTP × 3600) × 100
    IF = NP / FTP
    """
    ...

def calculate_tss_from_hr(
    duration_seconds: int,
    avg_hr: int,
    max_hr: int,
    resting_hr: int,
) -> float:
    """
    Estimativa de TSS via TRIMP quando não há dados de potência.
    TRIMP = duration_min × hr_ratio × 0.64 × e^(1.92 × hr_ratio)
    hr_ratio = (avg_hr - resting_hr) / (max_hr - resting_hr)
    """
    ...

def calculate_strength_tss(duration_minutes: int, rpe: int) -> float:
    """
    Estimativa de TSS para treinos de força.
    Fórmula empírica: (duration × rpe²) / (10 × 60) × 100
    Limitar máximo a 150 TSS por sessão.
    """
    ...

def calculate_ctl(
    previous_ctl: float,
    daily_tss: float,
    time_constant_days: int = 42,
) -> float:
    """CTL(t) = CTL(t-1) + (TSS - CTL(t-1)) × (1 - e^(-1/42))"""
    ...

def calculate_atl(
    previous_atl: float,
    daily_tss: float,
    time_constant_days: int = 7,
) -> float:
    """ATL(t) = ATL(t-1) + (TSS - ATL(t-1)) × (1 - e^(-1/7))"""
    ...

def calculate_tsb(ctl: float, atl: float) -> float:
    """TSB = CTL - ATL (positivo = forma boa, negativo = fatigado)"""
    return ctl - atl

def calculate_training_load_series(
    tss_series: list[dict],  # [{"date": date, "tss": float}]
    initial_ctl: float = 0.0,
    initial_atl: float = 0.0,
) -> list[dict]:
    """
    Calcula série temporal completa de CTL/ATL/TSB a partir de lista de TSS diário.
    Retorna: [{"date": date, "ctl": float, "atl": float, "tsb": float, "daily_tss": float}]
    """
    ...

def calculate_intensity_zones_cycling(ftp: int) -> dict:
    """
    Retorna limites das 7 zonas de potência (Coggan):
    Z1 < 55% FTP, Z2 55-75%, Z3 75-90%, Z4 90-105%, Z5 105-120%, Z6 120-150%, Z7 >150%
    """
    ...

def calculate_hr_zones(max_hr: int, resting_hr: int) -> dict:
    """
    Zonas de FC baseadas em Karvonen (HRR):
    Z1 50-60%, Z2 60-70%, Z3 70-80%, Z4 80-90%, Z5 >90%
    """
    ...
```

### 3.8 `backend/app/services/strava_service.py`

```python
"""
Cliente para a API do Strava v3.
Documentação: https://developers.strava.com/docs/reference/

OAuth 2.0 flow:
1. Redirecionar atleta para: https://www.strava.com/oauth/authorize?...
2. Receber callback com `code`
3. Trocar `code` por access_token + refresh_token
4. Salvar tokens criptografados em platform_connections
5. Usar access_token para chamadas de API
6. Refrescar token quando expires_at < now()

Limites: 200 req/15min, 2000 req/dia
"""

import httpx
from datetime import datetime
from app.config import settings

STRAVA_BASE_URL = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


class StravaService:
    def get_authorization_url(self, state: str) -> str:
        """Gera URL de autorização OAuth para redirecionar o atleta."""
        ...

    async def exchange_code_for_tokens(self, code: str) -> dict:
        """Troca código de autorização por access_token e refresh_token."""
        ...

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresca o access_token usando o refresh_token."""
        ...

    async def get_athlete(self, access_token: str) -> dict:
        """GET /athlete — dados do perfil do atleta autenticado."""
        ...

    async def get_activities(
        self,
        access_token: str,
        after: int | None = None,  # timestamp Unix
        before: int | None = None,
        page: int = 1,
        per_page: int = 30,
    ) -> list[dict]:
        """GET /athlete/activities — lista de atividades com paginação."""
        ...

    async def get_activity_detail(self, access_token: str, activity_id: int) -> dict:
        """
        GET /activities/{id} — detalhes completos incluindo:
        - splits, laps
        - zones (FC e potência)
        - best efforts
        """
        ...

    async def get_athlete_zones(self, access_token: str) -> dict:
        """GET /athlete/zones — zonas de FC e potência configuradas no Strava."""
        ...

    def parse_activity_to_workout(self, activity: dict, athlete_id: str) -> dict:
        """
        Converte o formato JSON do Strava para o modelo interno Workout.
        Calcula TSS se houver dados de potência (normalised_power + FTP).
        Se não houver potência, estima via TRIMP.
        """
        ...

    async def sync_recent_activities(
        self,
        db,
        athlete_id: str,
        access_token: str,
        days_back: int = 7,
    ) -> list[dict]:
        """
        Importa atividades recentes do Strava e salva no banco.
        Evita duplicatas verificando external_id.
        Retorna lista de workouts novos inseridos.
        """
        ...
```

### 3.9 `backend/app/services/ai_service.py`

Este é o módulo central de IA. Implemente com **provider abstrato** que alterna entre Anthropic e OpenAI:

```python
"""
AI Service — Router flexível entre Anthropic Claude e OpenAI GPT.
Responsabilidade: formatar contexto do atleta → chamar API de IA → parsear resposta.
"""

from enum import Enum
from dataclasses import dataclass
import anthropic
import openai
from app.config import settings


class AIProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class AthleteContext:
    """Contexto completo do atleta para enviar à IA."""
    name: str
    age: int
    weight_kg: float
    height_cm: float
    ftp_watts: int
    max_hr: int
    goals: str
    weekly_availability: dict
    recent_workouts: list[dict]       # últimos 10 treinos
    recent_strength: list[dict]       # últimas 5 sessões de musculação
    latest_metrics: dict              # métricas do dia atual
    ctl: float
    atl: float
    tsb: float
    weekly_tss: float
    target_event: str | None = None
    weeks_to_event: int | None = None


@dataclass
class TrainingRecommendation:
    """Recomendação estruturada retornada pela IA."""
    workout_type: str
    title: str
    recommendation_text: str
    structured_plan: dict
    rationale: str
    ai_provider: str
    ai_model: str


SYSTEM_PROMPT = """
You are an elite endurance coach and certified strength & conditioning specialist (CSCS).
You specialize in athletes who combine cycling with strength training.

Your role:
- Analyze the athlete's recent training load, fatigue indicators, and subjective metrics
- Propose ONE specific training session for tomorrow
- Explain your reasoning clearly, referencing the physiological principles behind your decision
- Adjust recommendations based on TSB (Training Stress Balance):
  * TSB < -20: prescribe recovery or very light session
  * TSB -20 to -5: normal training, moderate intensity
  * TSB -5 to +5: quality training, threshold/VO2max work appropriate
  * TSB > +5: athlete is fresh, high-intensity work appropriate
- For cycling sessions, include: warm-up, main set (with targets in watts/RPE/HR zones), cool-down
- For strength sessions, include: exercises, sets, reps, load (% of estimated 1RM or RPE target)
- Always output in JSON format as specified

Output format (JSON):
{
  "workout_type": "cycling_endurance|cycling_threshold|cycling_vo2max|cycling_long|strength_upper|strength_lower|strength_full|rest|mobility",
  "title": "Título curto do treino",
  "duration_minutes": 60,
  "intensity": "easy|moderate|hard|very_hard",
  "sections": [
    {
      "name": "Warm-up",
      "duration_minutes": 15,
      "description": "...",
      "targets": {"power_pct_ftp": 60, "hr_zone": 2, "rpe": 3}
    }
  ],
  "exercises": [],  // para sessões de musculação
  "rationale": "Explicação detalhada do raciocínio...",
  "key_metrics_considered": ["CTL: X", "ATL: Y", "TSB: Z", "..."],
  "cautions": []  // alertas sobre fadiga, lesão, etc.
}
"""


class AIService:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or AIProvider(settings.default_ai_provider)
        self._anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._openai_client = openai.OpenAI(api_key=settings.openai_api_key)

    def format_athlete_context(self, ctx: AthleteContext) -> str:
        """
        Formata o contexto do atleta em texto estruturado para o prompt.
        Incluir: perfil, métricas de carga (CTL/ATL/TSB), treinos recentes,
        métricas subjetivas (fadiga, sono, dor), objetivo e disponibilidade.
        """
        ...

    async def generate_recommendation(
        self,
        context: AthleteContext,
        provider: AIProvider | None = None,
    ) -> TrainingRecommendation:
        """
        Gera recomendação de treino usando o provider especificado.
        Faz parse do JSON retornado pela IA.
        Em caso de falha no provider primário, faz fallback para o alternativo.
        """
        ...

    async def _call_anthropic(self, user_message: str) -> str:
        """
        Chama Claude via API Anthropic.
        Usar claude-opus-4-6 (configurável via settings).
        max_tokens=2048, temperature=0.3 (determinístico para treinos).
        """
        ...

    async def _call_openai(self, user_message: str) -> str:
        """
        Chama GPT-4o via API OpenAI.
        response_format={"type": "json_object"} para garantir JSON.
        """
        ...

    def _parse_recommendation(self, raw_response: str, provider: str, model: str) -> TrainingRecommendation:
        """
        Parseia resposta JSON da IA para TrainingRecommendation.
        Tratar erros de JSON malformado com fallback gracioso.
        """
        ...

    async def analyze_fatigue(self, context: AthleteContext) -> dict:
        """
        Análise de fadiga em linguagem natural.
        Retorna: {"level": "low|moderate|high|critical", "summary": "...", "recommendations": [...]}
        """
        ...

    async def generate_weekly_plan(self, context: AthleteContext) -> list[dict]:
        """
        Gera plano semanal completo (7 dias) como lista de recomendações diárias.
        """
        ...
```

### 3.10 `backend/app/services/training_load.py`

```python
"""
Serviço de cálculo e atualização de carga de treino no banco de dados.
Orquestra cálculo de CTL/ATL/TSB para um atleta com base no histórico.
"""

async def recalculate_athlete_load(db, athlete_id: str, days_back: int = 90) -> None:
    """
    Busca todos os treinos dos últimos `days_back` dias,
    calcula TSS de cada um, recalcula série CTL/ATL/TSB
    e salva/atualiza tabela training_load.
    """
    ...

async def get_current_load(db, athlete_id: str) -> dict:
    """
    Retorna CTL/ATL/TSB atual do atleta (última entrada em training_load).
    """
    ...

async def get_load_history(
    db,
    athlete_id: str,
    days: int = 90,
) -> list[dict]:
    """
    Retorna série histórica de CTL/ATL/TSB para plotagem de gráfico.
    """
    ...
```

### 3.11 `backend/app/routers/auth.py`

```python
"""
Endpoints de autenticação:
POST /api/auth/register     — cadastro com email/senha via Supabase Auth
POST /api/auth/login        — login, retorna JWT
POST /api/auth/logout
GET  /api/auth/strava       — inicia OAuth Strava (redireciona atleta)
GET  /api/auth/strava/callback — recebe code, troca por tokens, salva conexão
DELETE /api/auth/strava     — desconecta Strava
GET  /api/auth/me           — retorna perfil do atleta autenticado
PUT  /api/auth/me           — atualiza perfil (FTP, peso, objetivos, etc.)
"""
```

### 3.12 `backend/app/routers/workouts.py`

```python
"""
Endpoints de treinos:
GET    /api/workouts                  — lista treinos com filtros (data, tipo, fonte)
GET    /api/workouts/{id}             — detalhes de um treino
POST   /api/workouts/sync/strava      — importa atividades recentes do Strava
DELETE /api/workouts/{id}
GET    /api/workouts/stats/weekly     — TSS semanal, distância, tempo
GET    /api/workouts/load             — CTL/ATL/TSB atual e histórico
"""
```

### 3.13 `backend/app/routers/strength.py`

```python
"""
Endpoints de musculação:
GET    /api/strength                  — lista sessões de musculação
GET    /api/strength/{id}             — detalhes com exercícios
POST   /api/strength                  — cria nova sessão
PUT    /api/strength/{id}             — edita sessão
DELETE /api/strength/{id}
POST   /api/strength/{id}/exercises   — adiciona exercício à sessão
DELETE /api/strength/{id}/exercises/{exercise_id}
"""
```

### 3.14 `backend/app/routers/metrics.py`

```python
"""
Endpoints de métricas diárias:
GET  /api/metrics                     — histórico de métricas (range de datas)
POST /api/metrics                     — registra métricas do dia (upsert por data)
GET  /api/metrics/today               — métricas de hoje
GET  /api/metrics/trends              — tendências (média 7d, 30d)
"""
```

### 3.15 `backend/app/routers/recommendations.py`

```python
"""
Endpoints de recomendações:
GET  /api/recommendations             — histórico de recomendações
GET  /api/recommendations/today       — recomendação de hoje (gera se não existir)
POST /api/recommendations/generate    — gera nova recomendação (force refresh)
PUT  /api/recommendations/{id}/feedback — registra feedback do atleta
GET  /api/recommendations/weekly-plan — plano semanal completo
"""
```

### 3.16 `backend/scripts/daily_update.py`

```python
"""
Script de rotina diária — executar via cron, APScheduler, ou Claude Code.

Fluxo:
1. Para cada atleta com conexão Strava ativa:
   a. Sincronizar atividades das últimas 24h via Strava API
   b. Recalcular CTL/ATL/TSB com os dados atualizados
2. Verificar se métricas do dia foram inseridas (se não, alertar)
3. Gerar recomendação de treino via IA (se ainda não gerada hoje)
4. Opcional: exportar treino planejado para TrainingPeaks via MCP
5. Log de execução com timestamp e métricas de performance

Executar com: python -m scripts.daily_update
Ou agendar via cron: 0 6 * * * cd /app && python -m scripts.daily_update
"""
```

---

## FASE 4 — FRONTEND (Next.js 14)

### 4.1 `frontend/package.json`

```json
{
  "name": "fitness-performance-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "next": "14.2.5",
    "react": "^18",
    "react-dom": "^18",
    "@supabase/supabase-js": "^2.44.2",
    "@supabase/ssr": "^0.3.0",
    "recharts": "^2.12.7",
    "axios": "^1.7.2",
    "date-fns": "^3.6.0",
    "zustand": "^4.5.4",
    "react-hook-form": "^7.52.1",
    "zod": "^3.23.8",
    "@hookform/resolvers": "^3.6.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.4.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "tailwindcss": "^3.4.1",
    "autoprefixer": "^10.0.1",
    "postcss": "^8",
    "eslint": "^8",
    "eslint-config-next": "14.2.5"
  }
}
```

### 4.2 `frontend/.env.example`

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4.3 `frontend/lib/types.ts`

Defina **todos** os tipos TypeScript do domínio:

```typescript
export type SportType = 
  | 'cycling' | 'running' | 'strength' | 'rest' | 'mobility' | 'other';

export type WorkoutSource = 'strava' | 'trainingpeaks' | 'garmin' | 'manual' | 'planned';

export interface Athlete {
  id: string;
  name: string;
  email: string;
  weight_kg: number;
  height_cm: number;
  ftp_watts: number;
  max_hr: number;
  goals: string;
  weekly_availability: WeeklyAvailability;
}

export interface WeeklyAvailability {
  cycling: string[];   // ['mon', 'wed', 'fri']
  strength: string[];
}

export interface Workout {
  id: string;
  athlete_id: string;
  source: WorkoutSource;
  sport_type: SportType;
  title: string;
  start_time: string;
  duration_seconds: number;
  distance_meters: number;
  avg_power_watts: number;
  normalized_power_watts: number;
  avg_heart_rate: number;
  tss: number;
  if_score: number;
  hr_zones: Record<string, number>;
  power_zones: Record<string, number>;
}

export interface StrengthSession {
  id: string;
  session_date: string;
  session_type: string;
  duration_minutes: number;
  rpe_overall: number;
  notes: string;
  exercises: StrengthExercise[];
}

export interface StrengthExercise {
  id: string;
  exercise_name: string;
  sets: number;
  reps: number;
  load_kg: number;
  rpe: number;
}

export interface DailyMetrics {
  metric_date: string;
  weight_kg: number;
  sleep_hours: number;
  sleep_quality: number;
  hrv_ms: number;
  resting_hr: number;
  fatigue_score: number;
  muscle_soreness: number;
  motivation_score: number;
  notes: string;
}

export interface TrainingLoad {
  load_date: string;
  ctl: number;
  atl: number;
  tsb: number;
  daily_tss: number;
  weekly_tss: number;
}

export interface AIRecommendation {
  id: string;
  recommendation_date: string;
  workout_type: string;
  title: string;
  recommendation_text: string;
  structured_plan: StructuredPlan;
  rationale: string;
  ai_provider: string;
  feedback_rating: number | null;
}

export interface StructuredPlan {
  duration_minutes: number;
  intensity: string;
  sections: TrainingSection[];
  exercises: ExerciseBlock[];
  key_metrics_considered: string[];
  cautions: string[];
}

export interface TrainingSection {
  name: string;
  duration_minutes: number;
  description: string;
  targets: {
    power_pct_ftp?: number;
    hr_zone?: number;
    rpe?: number;
  };
}

export interface ExerciseBlock {
  name: string;
  sets: number;
  reps: string;
  load: string;
  rest_seconds: number;
  notes: string;
}
```

### 4.4 `frontend/app/dashboard/page.tsx`

Dashboard principal com os seguintes widgets:
- **Card de CTL/ATL/TSB atual** com indicadores coloridos (verde/amarelo/vermelho por TSB)
- **Gráfico de linha** CTL/ATL/TSB dos últimos 60 dias (Recharts LineChart)
- **Card de recomendação de hoje** com botão "Gerar recomendação"
- **TSS semanal** em comparação à semana anterior (BarChart)
- **Últimos 5 treinos** como lista compacta com ícones por tipo
- **Métricas do dia** (fadiga, sono, HRV) em cards coloridos

### 4.5 `frontend/components/charts/CTLATLTSBChart.tsx`

```typescript
/**
 * Gráfico de linha triplo mostrando CTL (azul), ATL (laranja), TSB (verde/vermelho).
 * TSB positivo = verde, negativo = vermelho.
 * Linha de referência em TSB=0.
 * Tooltips com valores e data.
 * Período selecionável: 30/60/90 dias.
 */
```

### 4.6 `frontend/app/strength/new/page.tsx`

Formulário completo de registro de musculação:
- Campos: data, tipo de sessão, duração, RPE geral, notas
- Seção de exercícios com botão "Adicionar exercício"
- Cada exercício: nome (autocomplete), séries, reps, carga (kg), RPE
- Validação com react-hook-form + zod
- Submit para POST /api/strength

### 4.7 `frontend/app/metrics/page.tsx`

Formulário de registro diário de métricas + gráficos de tendência:
- Campos: peso, horas de sono, qualidade do sono (1-10), HRV, FC de repouso
- Escalas subjetivas: fadiga, dor muscular, motivação (sliders 1-10)
- Gráfico de linha: evolução do peso e HRV nos últimos 30 dias
- Gráfico de barras: qualidade do sono por semana

### 4.8 `frontend/app/recommendations/page.tsx`

- Card grande com recomendação do dia (título, tipo, duração, intensidade)
- Seções do treino expandíveis (warm-up, main set, cool-down)
- Para musculação: tabela com exercícios, séries, reps, carga
- Justificativa da IA (texto explicativo)
- Botão de feedback (estrelas 1-5) + campo de notas
- Histórico de últimas 10 recomendações

---

## FASE 5 — DOCUMENTAÇÃO

### 5.1 `docs/AI_PROMPTS.md`

Documente os prompts internos usados pelo sistema, incluindo:
- System prompt completo do agente de treino
- Exemplos de contextos de atleta formatados
- Exemplos de respostas JSON da IA
- Guia para ajustar os prompts

### 5.2 `docs/STRAVA_SETUP.md`

Passo a passo completo para:
1. Criar aplicativo no Strava Developers
2. Configurar Client ID e Secret no `.env`
3. Testar o fluxo OAuth localmente
4. Entender limitações do Single Player Mode

### 5.3 `docs/ARCHITECTURE.md`

Diagrama ASCII da arquitetura + descrição de cada componente + decisões técnicas.

### 5.4 `README.md` (raiz do projeto)

```markdown
# Fitness Performance App

Aplicação web de performance esportiva integrando ciclismo e musculação com análise via IA.

## Início rápido

### Requisitos
- Python 3.11+
- Node.js 20+
- Conta Supabase (gratuita)
- Chave API Anthropic e/ou OpenAI

### Backend
\`\`\`bash
cd backend
cp .env.example .env
# Preencher variáveis no .env
pip install -r requirements.txt
uvicorn app.main:app --reload
\`\`\`

### Frontend
\`\`\`bash
cd frontend
cp .env.example .env.local
# Preencher variáveis no .env.local
npm install
npm run dev
\`\`\`

### Banco de dados
Executar o arquivo \`supabase/migrations/001_initial_schema.sql\` no SQL Editor do Supabase.

## Rotina diária (automação)
\`\`\`bash
cd backend && python -m scripts.daily_update
\`\`\`

## Estrutura do projeto
[descrever estrutura]

## Roadmap
- [x] MVP: Strava + musculação manual + IA
- [ ] TrainingPeaks MCP integration
- [ ] Garmin Connect (pending approval)
- [ ] Mobile app (React Native)
- [ ] Multi-athlete support
```

---

## FASE 6 — CONFIGURAÇÃO DO AMBIENTE

### 6.1 `docker-compose.yml`

```yaml
version: '3.9'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app

  # Nota: PostgreSQL é gerenciado pelo Supabase (cloud)
  # Para desenvolvimento local, você pode adicionar um serviço PostgreSQL aqui
```

### 6.2 `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## FASE 7 — TESTES

### `backend/tests/test_calculations.py`

Implementar testes unitários para todas as funções em `utils/calculations.py`:
- TSS com e sem dados de potência
- CTL/ATL/TSB com séries conhecidas
- Cálculo de zonas de potência e FC

### `backend/tests/test_ai_service.py`

- Mock das APIs Anthropic e OpenAI
- Teste de parsing de resposta JSON
- Teste de fallback entre providers
- Teste com contexto de atleta real

---

## INSTRUÇÕES DE EXECUÇÃO PARA CLAUDE CODE

1. **Execute em ordem**: Fase 1 → 2 → 3 → 4 → 5 → 6 → 7
2. **Crie todos os arquivos** com implementação real e funcional — **não use `pass` ou placeholders** sem implementação
3. **Para o backend**: após criar os arquivos, execute `pip install -r requirements.txt` e verifique se a aplicação sobe sem erros (`uvicorn app.main:app --reload`)
4. **Para o frontend**: execute `npm install` e `npm run type-check` para verificar tipos TypeScript
5. **Para o banco**: verifique que o SQL de migração está sintaticamente correto
6. **Após cada arquivo criado**, confirme que imports e dependências estão corretos
7. **Testes**: execute `pytest backend/tests/` ao final e certifique-se que todos passam
8. **Variáveis de ambiente**: **nunca** hardcode chaves ou secrets — sempre usar `settings` do `config.py`
9. **Segurança**: tokens OAuth devem ser tratados como dados sensíveis — não logar em produção
10. **Async**: usar `async/await` em todos os handlers FastAPI e nas chamadas de banco/HTTP

---

## CONSIDERAÇÕES FINAIS

- **Strava API**: Registrar o app em https://developers.strava.com antes de executar o OAuth
- **TrainingPeaks**: Integração opcional via `trainingpeaks-mcp` (uso pessoal apenas, verificar ToS)
- **Garmin**: API oficial requer empresa registrada; usar Strava como relay por enquanto
- **AI tokens**: Claude Opus é mais caro — considere Claude Sonnet para recomendações de menor complexidade
- **Scheduler**: APScheduler roda dentro do processo FastAPI; para produção, migrar para Celery + Redis ou AWS EventBridge
- **Deploy sugerido**: Backend no Railway (simples, suporta Python), Frontend na Vercel (zero-config Next.js)
