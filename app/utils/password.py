import asyncio
import bcrypt


BCRYPT_ROUNDS = 12
MAX_PASSWORD_BYTES = 72 

async def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
    salt = await asyncio.to_thread(bcrypt.gensalt, rounds=BCRYPT_ROUNDS)
    hashed = await asyncio.to_thread(bcrypt.hashpw, password_bytes, salt)
    return hashed.decode("utf-8")

async def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
    try:
        return await asyncio.to_thread(bcrypt.checkpw, password_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False