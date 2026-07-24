from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
import httpx
import logging

from app.database import get_db
from app.config import settings
from app.dependencies import get_current_admin, get_current_athlete, get_current_user_either
from app.models.admin import AdminUser
from app.models.athlete import Athlete
from app.models.lgpd import LGPDConsent, AuditLog

router = APIRouter()
logger = logging.getLogger(__name__)

from app.utils.crypto import verify_invite_token

SUPABASE_AUTH_URL = f"{settings.supabase_url}/auth/v1"


# ── Request / Response schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    email_confirmation_required: bool
    role: str = "admin"
    detail: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    crm: str | None = None
    ftp_watts: int | None = None
    max_hr: int | None = None
    resting_hr: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    goal: str | None = None
    weekly_availability: dict | None = None
    auto_report_enabled: bool | None = None


# ── Supabase Auth helpers ─────────────────────────────────────────────────────

async def _supabase_sign_in(email: str, password: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_AUTH_URL}/token?grant_type=password",
            headers={
                "apikey": settings.supabase_anon_key,
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password},
            timeout=10,
        )
    if resp.status_code != 200:
        error = resp.json().get("error_description", "Credenciais inválidas")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error)
    return resp.json()


async def _supabase_sign_up(email: str, password: str, name: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_AUTH_URL}/signup",
            headers={
                "apikey": settings.supabase_anon_key,
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password, "data": {"name": name}},
            timeout=10,
        )
    if resp.status_code not in (200, 201):
        body = resp.json() if resp.content else {}
        detail = body.get("msg") or body.get("error_description") or "Não foi possível concluir o cadastro"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    return resp.json()


async def _supabase_refresh(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_AUTH_URL}/token?grant_type=refresh_token",
            headers={
                "apikey": settings.supabase_anon_key,
                "Content-Type": "application/json",
            },
            json={"refresh_token": refresh_token},
            timeout=10,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")
    return resp.json()


async def _supabase_sign_out(access_token: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SUPABASE_AUTH_URL}/logout",
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=10,
        )


async def _log_action(db: AsyncSession, actor_id, actor_type: str, action: str,
                      resource_type: str, resource_id=None, ip: str | None = None):
    log = AuditLog(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip,
    )
    db.add(log)
    await db.commit()


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.post("/admin/login", response_model=TokenResponse, summary="Login do administrador")
async def admin_login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tokens = await _supabase_sign_in(body.email, body.password)

    user_id = tokens["user"]["id"]
    result = await db.execute(
        select(AdminUser).where(AdminUser.user_id == user_id, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não é administrador")

    await _log_action(db, admin.id, "admin", "login", "admin_users",
                      resource_id=admin.id, ip=request.client.host)

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens.get("expires_in", 3600),
        role="admin",
    )


@router.post("/admin/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED,
             summary="Cadastro de treinador (admin)")
async def admin_register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Auto-cadastro de treinador: cria o usuário no Supabase Auth, provisiona a
    linha em admin_users e uma assinatura trial. Se o projeto Supabase exigir
    confirmação de e-mail, a resposta pede a confirmação antes do login.
    """
    if len(body.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="A senha deve ter ao menos 6 caracteres")

    signup = await _supabase_sign_up(body.email, body.password, body.name)

    # A resposta do GoTrue traz o usuário em "user" (autoconfirm) ou na raiz
    # (quando exige confirmação). Sessão presente => sem confirmação.
    user = signup.get("user") or signup
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Resposta de cadastro inválida do provedor de auth")
    confirmation_required = "access_token" not in signup

    # Provisiona o admin (idempotente) + assinatura trial.
    existing = await db.execute(select(AdminUser).where(AdminUser.user_id == user_id))
    admin = existing.scalar_one_or_none()
    if admin is None:
        admin = AdminUser(user_id=user_id, name=body.name, email=body.email, is_active=True)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

    from app.services.billing_service import get_or_create_subscription
    await get_or_create_subscription(db, str(admin.id))

    await _log_action(db, admin.id, "admin", "register", "admin_users",
                      resource_id=admin.id, ip=request.client.host)

    if confirmation_required:
        return RegisterResponse(
            email_confirmation_required=True,
            detail="Cadastro criado. Confirme seu e-mail para poder entrar.",
        )
    return RegisterResponse(
        email_confirmation_required=False,
        detail="Cadastro concluído. Você já pode entrar.",
    )


@router.post("/refresh", response_model=TokenResponse, summary="Renovar access token")
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    tokens = await _supabase_refresh(body.refresh_token)

    user_id = tokens["user"]["id"]

    # Determine role from DB
    admin_result = await db.execute(
        select(AdminUser).where(AdminUser.user_id == user_id, AdminUser.is_active == True)
    )
    admin = admin_result.scalar_one_or_none()
    role = "admin" if admin else "athlete"

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens.get("expires_in", 3600),
        role=role,
    )


@router.post("/logout", summary="Logout (invalida sessão no Supabase)")
async def logout(
    request: Request,
    current: dict = Depends(get_current_user_either),
    db: AsyncSession = Depends(get_db),
):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    await _supabase_sign_out(token)

    user = current["user"]
    actor_type = current["role"]
    await _log_action(db, user.id, actor_type, "logout", actor_type + "s",
                      resource_id=user.id, ip=request.client.host)

    return {"detail": "Logout realizado com sucesso"}


@router.get("/me", summary="Perfil do usuário autenticado")
async def get_me(current: dict = Depends(get_current_user_either)):
    user = current["user"]
    role = current["role"]

    if role == "admin":
        return {
            "role": "admin",
            "id": str(user.id),
            "user_id": str(user.user_id),
            "name": user.name,
            "email": user.email,
            "crm": user.crm,
            "stripe_account_id": user.stripe_account_id,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
    return {
        "role": "athlete",
        "id": str(user.id),
        "user_id": str(user.user_id),
        "admin_id": str(user.admin_id),
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "birth_date": user.birth_date,
        "gender": user.gender,
        "height_cm": float(user.height_cm) if user.height_cm else None,
        "weight_kg": float(user.weight_kg) if user.weight_kg else None,
        "sport_modalities": user.sport_modalities,
        "primary_modality": user.primary_modality,
        "fitness_level": user.fitness_level,
        "ftp_watts": user.ftp_watts,
        "max_hr": user.max_hr,
        "resting_hr": user.resting_hr,
        "onboarding_complete": user.onboarding_complete,
        "auto_report_enabled": user.auto_report_enabled,
        # A tela de configurações do atleta exibe este token para montar o
        # atalho do iOS; sem ele o campo aparecia sempre vazio.
        "apple_health_token": str(user.apple_health_token) if user.apple_health_token else None,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


@router.put("/me", summary="Atualiza perfil do usuário autenticado")
async def update_me(
    body: ProfileUpdateRequest,
    request: Request,
    current: dict = Depends(get_current_user_either),
    db: AsyncSession = Depends(get_db),
):
    user = current["user"]
    role = current["role"]

    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum campo para atualizar")

    # Only apply fields that exist on the model
    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    await _log_action(db, user.id, role, "profile_update", role + "s",
                      resource_id=user.id, ip=request.client.host)

    return {"detail": "Perfil atualizado com sucesso"}


# ── Athlete login ─────────────────────────────────────────────────────────────

@router.post("/athlete/login", response_model=TokenResponse, summary="Login do atleta")
async def athlete_login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tokens = await _supabase_sign_in(body.email, body.password)

    user_id = tokens["user"]["id"]
    result = await db.execute(
        select(Athlete).where(Athlete.user_id == user_id, Athlete.is_active == True)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Atleta não encontrado")

    await _log_action(db, athlete.id, "athlete", "login", "athletes",
                      resource_id=athlete.id, ip=request.client.host)

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens.get("expires_in", 3600),
        role="athlete",
    )


# ── Onboarding invite flow (T02.5) ────────────────────────────────────────────

class ValidateInviteResponse(BaseModel):
    valid: bool
    athlete_id: str | None = None
    name: str | None = None
    email: str | None = None


class SetPasswordRequest(BaseModel):
    invite_token: str
    password: str
    confirm_password: str


@router.get("/onboarding/validate", response_model=ValidateInviteResponse,
            summary="Valida token de convite")
async def validate_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    athlete_id = verify_invite_token(token)
    if not athlete_id:
        return ValidateInviteResponse(valid=False)

    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.is_active == True)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        return ValidateInviteResponse(valid=False)

    return ValidateInviteResponse(
        valid=True,
        athlete_id=str(athlete.id),
        name=athlete.name,
        email=athlete.email,
    )


@router.post("/athlete/set-password", response_model=TokenResponse,
             summary="Define senha no primeiro acesso via link de convite")
async def set_password(
    body: SetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Senhas não conferem")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Senha deve ter no mínimo 8 caracteres")

    athlete_id = verify_invite_token(body.invite_token)
    if not athlete_id:
        raise HTTPException(status_code=400, detail="Token de convite inválido ou expirado")

    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.is_active == True)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    # Create (or update) Supabase Auth user with the real password
    async with httpx.AsyncClient() as client:
        # Use admin API to create the user
        resp = await client.post(
            f"{SUPABASE_AUTH_URL}/admin/users",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Content-Type": "application/json",
            },
            json={
                "email": athlete.email,
                "password": body.password,
                "email_confirm": True,
            },
            timeout=10,
        )

    if resp.status_code not in (200, 201):
        # User may already exist — try updating password instead
        async with httpx.AsyncClient() as client:
            # Find user by email first
            users_resp = await client.get(
                f"{SUPABASE_AUTH_URL}/admin/users",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                },
                params={"email": athlete.email},
                timeout=10,
            )
        if users_resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Erro ao criar usuário no Supabase")

    supabase_user_id = resp.json().get("id") or resp.json().get("user", {}).get("id")
    if not supabase_user_id:
        raise HTTPException(status_code=500, detail="Erro ao obter ID do usuário Supabase")

    # Update athlete row with the real Supabase user_id
    import uuid as _uuid
    athlete.user_id = _uuid.UUID(supabase_user_id)
    db.add(athlete)
    await db.commit()

    # Sign in to get tokens
    tokens = await _supabase_sign_in(athlete.email, body.password)

    await _log_action(db, athlete.id, "athlete", "set_password", "athletes",
                      resource_id=athlete.id, ip=request.client.host)

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens.get("expires_in", 3600),
        role="athlete",
    )
