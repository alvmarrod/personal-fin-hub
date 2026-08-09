import base64
import hashlib
import hmac
import logging
import os

from db import queries
from db.connection import get_db
from models import ProfileCreate, ProfileResponse

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 600_000
_SALT_LEN = 16

# Child-first deletion order so foreign-key references are removed before
# their parents (fees/taxes/occurrences -> transactions/schedules, etc.).
_PROFILE_DELETE_ORDER = [
    "schedule_occurrences",
    "transaction_fees",
    "transaction_taxes",
    "manual_values",
    "balance_snapshots",
    "schedules",
    "transactions",
    "portfolio_assets",
    "entities",
    "fiscal_exemptions",
]


class ProfileError(Exception):
    pass


class ProfileNotFound(ProfileError):
    pass


class ProfileNameTaken(ProfileError):
    pass


class InvalidPassword(ProfileError):
    pass


class LastProfileError(ProfileError):
    pass


class InvalidProfileName(ProfileError):
    pass


def _hash_password(password: str) -> str:
    """Hash a password with pbkdf2_hmac(sha256) and a per-password random salt.

    Format: ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``
    """
    salt = os.urandom(_SALT_LEN)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}"
        f"${base64.b64encode(salt).decode('ascii')}"
        f"${base64.b64encode(dk).decode('ascii')}"
    )


def _verify_password(password: str, stored: str | None) -> bool:
    """Constant-time password verification. Returns False for malformed hashes."""
    if not stored:
        return False
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.b64decode(salt_b64),
            int(iterations),
        )
        return hmac.compare_digest(base64.b64encode(dk).decode("ascii"), hash_b64)
    except Exception:
        return False


def _to_response(profile: dict) -> ProfileResponse:
    return ProfileResponse(
        id=profile["id"],
        name=profile["name"],
        has_password=profile["password_hash"] is not None,
        created_at=profile["created_at"],
    )


def list_profiles() -> list[ProfileResponse]:
    conn = get_db()
    return [_to_response(p) for p in queries.get_all_profiles(conn)]


def get(profile_id: int) -> ProfileResponse:
    conn = get_db()
    profile = queries.get_profile(conn, profile_id)
    if profile is None:
        raise ProfileNotFound(f"Profile {profile_id} not found")
    return _to_response(profile)


def create(body: ProfileCreate) -> ProfileResponse:
    name = body.name.strip()
    if not name:
        raise InvalidProfileName("Profile name cannot be empty")
    conn = get_db()
    if queries.get_profile_by_name(conn, name):
        raise ProfileNameTaken(f"Profile '{name}' already exists")
    password_hash = _hash_password(body.password) if body.password else None
    profile_id = queries.create_profile(conn, name, password_hash)
    conn.commit()
    profile = queries.get_profile(conn, profile_id)
    assert profile is not None
    return _to_response(profile)


def rename(profile_id: int, name: str) -> ProfileResponse:
    name = name.strip()
    if not name:
        raise InvalidProfileName("Profile name cannot be empty")
    conn = get_db()
    existing = queries.get_profile(conn, profile_id)
    if existing is None:
        raise ProfileNotFound(f"Profile {profile_id} not found")
    if name != existing["name"] and queries.get_profile_by_name(conn, name):
        raise ProfileNameTaken(f"Profile '{name}' already exists")
    queries.rename_profile(conn, profile_id, name)
    conn.commit()
    profile = queries.get_profile(conn, profile_id)
    assert profile is not None
    return _to_response(profile)


def unlock(profile_id: int, password: str | None) -> ProfileResponse:
    conn = get_db()
    profile = queries.get_profile(conn, profile_id)
    if profile is None:
        raise ProfileNotFound(f"Profile {profile_id} not found")
    if profile["password_hash"] is not None:
        if not password or not _verify_password(password, profile["password_hash"]):
            raise InvalidPassword("Incorrect password for profile")
    return _to_response(profile)


def delete(profile_id: int) -> None:
    conn = get_db()
    if queries.get_profile(conn, profile_id) is None:
        raise ProfileNotFound(f"Profile {profile_id} not found")
    if queries.count_profiles(conn) <= 1:
        raise LastProfileError("Cannot delete the last remaining profile")
    for table in _PROFILE_DELETE_ORDER:
        conn.execute(f"DELETE FROM {table} WHERE profile_id = ?", (profile_id,))
    queries.delete_profile(conn, profile_id)
    conn.commit()
    logger.info("Deleted profile %s and all its data", profile_id)
