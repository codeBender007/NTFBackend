import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, List, Optional, Union
import bcrypt
import jwt

from app.core.config import settings

logger = logging.getLogger("ntf_backend.security")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Password compare karne ke liye (Login ke waqt use hoga)"""
    if not plain_password or not hashed_password:
        return False
    pwd_bytes = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Plain password ko hash karne ke liye (Max 72 bytes safe truncate)"""
    pwd_bytes = (password or "Welcome@123").encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate a signed JWT token containing user identity and role payload.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": now
    })
    
    secret_key = settings.JWT_SECRET_KEY or settings.SECRET_KEY
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a signed JWT token.
    Automatically strips accidental 'Bearer ' prefixes, enclosing quotes, and extra whitespace.
    Returns payload dictionary or None if invalid or expired.
    """
    if not token or not isinstance(token, str):
        return None

    clean_token = token.strip().strip('"').strip("'")
    while clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip().strip('"').strip("'")

    secret_key = settings.JWT_SECRET_KEY or settings.SECRET_KEY
    try:
        payload = jwt.decode(clean_token, secret_key, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Access token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid access token: {str(e)}")
        return None


def parse_dob_string(value: Any) -> Optional[date]:
    """
    Parse a Date of Birth value (date object, datetime object, or formatted string)
    into a standard datetime.date.
    Supports formats: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, YYYY/MM/DD, DDMMYYYY, YYYYMMDD, DD.MM.YYYY, etc.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    val = value.strip()
    if not val:
        return None

    date_formats = [
        "%Y-%m-%d",   # 1995-08-25
        "%d-%m-%Y",   # 25-08-1995
        "%d/%m/%Y",   # 25/08/1995
        "%Y/%m/%d",   # 1995/08/25
        "%d.%m.%Y",   # 25.08.1995
        "%d%m%Y",     # 25081995 (default used in bulk Excel employee import)
        "%Y%m%d",     # 19950825
        "%d-%m-%y",   # 25-08-95
        "%d/%m/%y",   # 25/08/95
        "%d-%b-%Y",   # 25-Aug-1995
        "%d-%B-%Y",   # 25-August-1995
        "%d %b %Y",   # 25 Aug 1995
        "%d %B %Y",   # 25 August 1995
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def get_dob_candidates(dob: date) -> List[str]:
    """
    Generate standardized candidate string representations of a Date of Birth.
    Covers the default Excel import format (DDMMYYYY) and all common user entry formats.
    """
    if not dob:
        return []
    formats = [
        "%d%m%Y",     # DDMMYYYY: Default bulk Excel import format (_dob_password)
        "%Y-%m-%d",   # YYYY-MM-DD: ISO standard format
        "%d-%m-%Y",   # DD-MM-YYYY: Common Indian / European format
        "%d/%m/%Y",   # DD/MM/YYYY: Common slash separated format
        "%Y/%m/%d",   # YYYY/MM/DD: Slash separated ISO format
        "%Y%m%d",     # YYYYMMDD: ISO compact format
        "%d.%m.%Y",   # DD.MM.YYYY: Dot separated format
    ]
    candidates = []
    for fmt in formats:
        formatted = dob.strftime(fmt)
        if formatted not in candidates:
            candidates.append(formatted)
    return candidates


def verify_employee_password(
    plain_password: str,
    stored_hash: Optional[str],
    employee_dob: Optional[Union[date, datetime, str]] = None
) -> bool:
    """
    Verify the submitted password against the stored password hash.
    Also handles default password logic for employees imported via bulk Excel,
    where default passwords are set to the employee's Date of Birth (DOB).
    Handles format parsing/matching properly (e.g. 'YYYY-MM-DD', 'DD-MM-YYYY', 'DDMMYYYY', 'DD/MM/YYYY').
    """
    if not plain_password:
        return False

    # 1. Direct bcrypt verification (covers users with custom passwords or exact match)
    if stored_hash and verify_password(plain_password, stored_hash):
        return True

    # 2. Check if the submitted password is an alternative representation of a DOB
    # that matches the stored bcrypt hash (e.g., hash was generated as DDMMYYYY, but user entered YYYY-MM-DD)
    parsed_input_dob = parse_dob_string(plain_password)
    if parsed_input_dob and stored_hash:
        for candidate in get_dob_candidates(parsed_input_dob):
            if verify_password(candidate, stored_hash):
                return True

    # 3. If employee record has a DOB in the database
    if employee_dob:
        actual_dob = parse_dob_string(employee_dob)
        if actual_dob:
            dob_candidates = get_dob_candidates(actual_dob)
            # Check if the stored hash is indeed based on the employee's DOB
            is_dob_hash = False
            if stored_hash:
                for candidate in dob_candidates:
                    if verify_password(candidate, stored_hash):
                        is_dob_hash = True
                        break
                    if stored_hash.strip() == candidate:
                        is_dob_hash = True
                        break
            else:
                # If stored hash is None/empty, default DOB is accepted
                is_dob_hash = True

            # If the account password is set to DOB, accept submitted password if it matches actual DOB
            if is_dob_hash:
                if plain_password in dob_candidates:
                    return True
                if parsed_input_dob and parsed_input_dob == actual_dob:
                    return True

    return False