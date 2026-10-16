from core import redis_client, get_db
import hashlib
from fastapi import Response, Request, BackgroundTasks, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from services.email import EmailService
from services.users import UserService
from utils.tokens import set_2fa_cookie, create_2fa, check_access_token
import random
from settings import jwtsettings
import hmac

SEND_COOLDOWN = 60
MAX_LOGIN_FAILS=5
LOGIN_FAIL_WINDOW=300

def _hash_code(code: str) -> str:
    return hmac.new(jwtsettings.JWT_SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()

async def can_send_2fa_code(user, response: Response, background_tasks: BackgroundTasks) -> bool:
    """True, если новый код отправлен. False, если сработал cooldown."""
    cd_key = f"2fa_cd:{user.id}"
    # если только что он создался то вернет True
    if not await redis_client.set(cd_key, 1, nx=True, ex=SEND_COOLDOWN):
        return False
    code = f'{random.randint(100000, 999999)}'   
    key = f"2fa_code:{user.id}"
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.hset(key, mapping={"hashed_code": _hash_code(code), "attempts": 3})
        pipe.expire(key, 300)
        await pipe.execute()

    await set_2fa_cookie(response=response, token=create_2fa(uid=user.id, username=user.username))
    background_tasks.add_task(EmailService.send_mail_code, email_to=user.email, code=code)
    return True


async def check_login_limit(request: Request):
    key = f"login_fail:{request.client.host}"
    fails = await redis_client.get(key)
    if fails and int(fails) >= MAX_LOGIN_FAILS:
        ttl = await redis_client.ttl(key)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f'Слишком много попыток. Повторите через {max(ttl, 1)} сек.')
    return key

async def register_login_fail(key: str):
    n = await redis_client.incr(key)
    if n == 1:
        await redis_client.expire(key, LOGIN_FAIL_WINDOW)

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    data = check_access_token(request=request)
    user = await UserService.get_user_by_username(username=data['username'], db=db)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Аккаунт неактивен')
    return data
    
