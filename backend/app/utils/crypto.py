"""
Field-level encryption helpers using pgcrypto (PostgreSQL-side).
The actual encrypt/decrypt runs inside SQL so the plaintext never
travels over the wire unencrypted after the initial INSERT/UPDATE.

For Python-side use (token generation, invite tokens), we use
HMAC-SHA256 via the standard library.
"""

import hashlib
import hmac
import secrets
import base64
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


# ── Invite token (stateless, signed) ─────────────────────────────────────────

def _sign(payload: str) -> str:
    return hmac.new(
        settings.secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_invite_token(athlete_id: str, expires_in_days: int = 7) -> str:
    """Returns a URL-safe signed token: base64(athlete_id|expiry|signature)."""
    expiry = int((datetime.now(timezone.utc) + timedelta(days=expires_in_days)).timestamp())
    payload = f"{athlete_id}|{expiry}"
    sig = _sign(payload)
    raw = f"{payload}|{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_invite_token(token: str) -> str | None:
    """Returns athlete_id if valid and not expired, else None."""
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        athlete_id, expiry_str, sig = raw.rsplit("|", 2)
        payload = f"{athlete_id}|{expiry_str}"
        expected_sig = _sign(payload)
        if not hmac.compare_digest(sig, expected_sig):
            return None
        if int(expiry_str) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return athlete_id
    except Exception:
        return None


# ── pgcrypto: anamnese encryption (SQL-side) ──────────────────────────────────

async def encrypt_anamnese(db: AsyncSession, plaintext: str) -> str:
    """Encrypts text using pgp_sym_encrypt (AES-256) inside PostgreSQL."""
    result = await db.execute(
        text("SELECT pgp_sym_encrypt(:data, :key) AS enc"),
        {"data": plaintext, "key": settings.db_encryption_key},
    )
    row = result.fetchone()
    # pgp_sym_encrypt returns bytea; asyncpg gives bytes — encode as hex
    enc_bytes: bytes = row.enc
    return enc_bytes.hex()


# ── OAuth token encryption (Python-side, Fernet AES-128) ─────────────────────

import base64 as _b64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_fernet_instance: "Fernet | None" = None


def _get_fernet() -> "Fernet":
    global _fernet_instance
    if _fernet_instance is None:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"fitcoachai_oauth",
            iterations=100_000,
        )
        key = _b64.urlsafe_b64encode(kdf.derive(settings.db_encryption_key.encode()))
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_token(plaintext: str) -> str:
    """Encrypts an OAuth token string with Fernet (AES-128-CBC + HMAC)."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypts a Fernet-encrypted OAuth token string."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


async def decrypt_anamnese(db: AsyncSession, hex_ciphertext: str) -> str:
    """Decrypts hex-encoded pgcrypto ciphertext inside PostgreSQL."""
    cipher_bytes = bytes.fromhex(hex_ciphertext)
    result = await db.execute(
        text("SELECT pgp_sym_decrypt(:data, :key) AS plain"),
        {"data": cipher_bytes, "key": settings.db_encryption_key},
    )
    row = result.fetchone()
    return row.plain
