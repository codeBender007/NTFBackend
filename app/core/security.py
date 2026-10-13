import bcrypt

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