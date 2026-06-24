import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Union
from app.config import settings

def hash_password(password: str) -> str:
    """
    Hashes a plain password using bcrypt directly.
    """
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a bcrypt hash using bcrypt directly.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

def create_access_token(subject: Union[str, Any], system_role: str) -> str:
    """
    Creates a JWT access token containing subject (username/id), role, and expiration.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": str(subject),
        "system_role": system_role,
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes a JWT access token. Raises jwt.PyJWTError on invalid signatures/expired tokens.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
