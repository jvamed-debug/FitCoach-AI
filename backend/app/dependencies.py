import time

import httpx
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


# ── Verificação de JWT do Supabase ────────────────────────────────────────────
# O Supabase moderno assina os tokens de usuário com chaves ASSIMÉTRICAS (ES256,
# EC P-256) por padrão; projetos antigos usam o segredo HS256 compartilhado.
# Suportamos os dois: o `alg` do cabeçalho decide o caminho. Para ES256/RS256
# buscamos a chave pública no endpoint JWKS do projeto (cacheado); o `kid` diz
# qual chave usar, permitindo rotação sem downtime.

_JWKS_TTL_SECONDS = 3600
_jwks_cache: dict = {"keys": {}, "fetched_at": 0.0}


async def _get_jwks_key(kid: str) -> dict | None:
    """Retorna a JWK pública com o `kid` dado, buscando/refrescando o JWKS."""
    now = time.time()
    fresh = (now - _jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS
    if fresh and kid in _jwks_cache["keys"]:
        return _jwks_cache["keys"][kid]

    # kid desconhecido ou cache expirado → (re)buscar. Cobre rotação de chaves.
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível obter as chaves de verificação de token",
        ) from e

    _jwks_cache["keys"] = {k["kid"]: k for k in data.get("keys", []) if "kid" in k}
    _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"].get(kid)


async def _decode_supabase_jwt(token: str) -> dict:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise unauthorized

    alg = header.get("alg", "")
    try:
        if alg == "HS256":
            # Caminho legado (segredo compartilhado) — também usado nos testes.
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        if alg in ("ES256", "RS256"):
            kid = header.get("kid")
            jwk = await _get_jwks_key(kid) if kid else None
            if jwk is None:
                raise unauthorized
            return jwt.decode(
                token,
                jwk,
                algorithms=[alg],
                options={"verify_aud": False},
            )
        raise unauthorized
    except JWTError as e:
        raise unauthorized from e


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    payload = await _decode_supabase_jwt(credentials.credentials)
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
    payload = await _decode_supabase_jwt(credentials.credentials)
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
    payload = await _decode_supabase_jwt(credentials.credentials)
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
