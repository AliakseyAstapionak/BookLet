import jwt
from fastapi import Response, HTTPException, status, Request
from settings import jwtsettings
import datetime
from datetime import datetime, timedelta, timezone
import hmac
import hashlib

_2FA_TTL=300
RESET_PWD_TIME=300
REGISTRARION_CHECK_EXPIRE_SECONDS=300

def _fp_password(hashed_pwd):
    return hmac.new(jwtsettings.JWT_SECRET_KEY.encode(), hashed_pwd.encode(), hashlib.sha256).hexdigest()[:16]

def _make_token(uid: int, username: str, token_type: str, ttl: int) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl)
    payload = {'uid': uid, 'username': username, 'type': token_type, 'exp': expire}
    return jwt.encode(payload, jwtsettings.JWT_SECRET_KEY, algorithm=jwtsettings.JWT_ALGORITHM)

def create_jwt(uid: int, username: str) -> str:
    return _make_token(uid, username, 'access', jwtsettings.JWT_EXPIRE_SECONDS)

def create_reg_token(username: str, email: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(seconds=REGISTRARION_CHECK_EXPIRE_SECONDS)
    payload = {'username': username, 'email': email ,'type': 'registration', 'exp': expire}
    return jwt.encode(payload, jwtsettings.JWT_SECRET_KEY, algorithm=jwtsettings.JWT_ALGORITHM)


def create_2fa(uid: int, username: str) -> str:
    return _make_token(uid, username, '2fa', _2FA_TTL)

def create_reset_pwd_token(uid: int, hashed_pwd: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(seconds=RESET_PWD_TIME)
    fp = _fp_password(hashed_pwd)
    payload = {'uid': uid, 'fp': fp, 'type': 'reset_pwd', 'exp': expire}
    return jwt.encode(payload, jwtsettings.JWT_SECRET_KEY, algorithm=jwtsettings.JWT_ALGORITHM)

def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, jwtsettings.JWT_SECRET_KEY, algorithms=[jwtsettings.JWT_ALGORITHM])
    if payload.get('type') != expected_type:
        raise jwt.InvalidTokenError('Неверный токен')
    return payload

async def set_auth_cookie(response: Response, token: str):
    response.set_cookie(key='access_token',value=token,httponly=True,    
        secure=False,       
        samesite='lax',     
        max_age=3600,
        path='/',
    )

async def set_2fa_cookie(response: Response, token: str):
    response.set_cookie(key='2fa_token', value=token, httponly=True,    
        secure=False,       
        samesite='lax',     
        max_age=3600,
        path='/', #TODO отправить потом на нужный адрес
    )

async def set_reg_cookie(response: Response, token: str):
    response.set_cookie(key='reg_token', value=token, httponly=True,    
        secure=False,       
        samesite='lax',     
        max_age=3600,
        path='/',
    )

def check_reset_pwd_token(token: str) -> dict:
    try:
        data = decode_token(token=token, expected_type='reset_pwd')  
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Сессия входа истекла')    
    uid: int = data.get("uid")
    fp: str = data.get('fp')
    if not uid or not fp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверные данные')
    return data
    
def check_reg_token(request: Request):
    _reg_token = request.cookies.get('reg_token')
    if not _reg_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Сессия входа не найдена')
    try:
        data = decode_token(_reg_token, 'registration')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Сессия входа истекла')    
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Невалидный токен')  
    return data 



def check_2fa_token(request: Request) -> dict:
    _2fa_token = request.cookies.get('2fa_token')
    if not _2fa_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Сессия входа не найдена')
    try:
        data = decode_token(_2fa_token, '2fa')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Сессия входа истекла')    
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Невалидный токен')  
    return data 

def check_access_token(request: Request) -> dict:
    access_token = request.cookies.get('access_token')
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Сессия входа не найдена. Войдите в аккаунт')
    try:
        data = decode_token(access_token, 'access')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Сессия входа истекла')    
    if not data or not data['uid'] or not data['username']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Невалидный токен')  
    return data 

