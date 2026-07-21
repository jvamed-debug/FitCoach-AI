from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError
from datetime import datetime, timezone

from app.database import get_db
from app.config import settings
from app.models.admin import AdminUser
from app.models.athlete import Athlete
from app.models.lgpd import LGPDConsent

bearer_scheme = HTTPBearer()


def _decode_supabase_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    payload = _decode_supabase_jwt(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem subject")

    result = await db.execute(
        select(AdminUser).where(AdminUser.user_id == user_id, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return admin


async def get_current_athlete(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    payload = _decode_supabase_jwt(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem subject")

    result = await db.execute(
        select(Athlete).where(Athlete.user_id == user_id, Athlete.is_active == True)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Atleta não encontrado")
    return athlete


async def require_lgpd_consent(
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    result = await db.execute(
        select(LGPDConsent).where(
            LGPDConsent.athlete_id == athlete.id,
            LGPDConsent.revoked_at == None,
        )
    )
    consent = result.scalar_one_or_none()
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consentimento LGPD necessário. Acesse /onboarding para aceitar os termos.",
        )
    return athlete


async def get_current_user_either(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns {'role': 'admin'|'athlete', 'user': AdminUser|Athlete}"""
    payload = _decode_supabase_jwt(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem subject")

    admin_result = await db.execute(
        select(AdminUser).where(AdminUser.user_id == user_id, AdminUser.is_active == True)
    )
    admin = admin_result.scalar_one_or_none()
    if admin:
        return {"role": "admin", "user": admin}

    athlete_result = await db.execute(
        select(Athlete).where(Athlete.user_id == user_id, Athlete.is_active == True)
    )
    athlete = athlete_result.scalar_one_or_none()
    if athlete:
        return {"role": "athlete", "user": athlete}

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não encontrado")
