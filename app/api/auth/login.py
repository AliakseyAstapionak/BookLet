import hmac

from fastapi import APIRouter, status, Depends, HTTPException, BackgroundTasks, Response, Request

from schemas import UserLoginSchema, VerifyCodeSchema
from services.users import UserService
from core import get_db, redis_client
from utils import (verify_password, create_jwt, set_auth_cookie, set_2fa_cookie, create_2fa,
                   can_send_2fa_code, check_limit, _hash_code, check_2fa_token, register_fail)
from ..tags import TAG_LOGIN

router = APIRouter(prefix='/BookLet', tags=[TAG_LOGIN])


@router.post(
    '/login',
    summary='Вход по логину и паролю',
    description='Если 2FA выключена — сразу ставит cookie `access_token`. '
                'Если включена — отправляет код на почту и ставит cookie `2fa_token`; '
                'вход нужно завершить через `/login/2fa`.',
    responses={400: {'description': 'Неверный логин или пароль / аккаунт неактивен'},
               429: {'description': 'Слишком много неудачных попыток входа'}},
)
async def login(user: UserLoginSchema, background_tasks: BackgroundTasks, response: Response, request: Request, db=Depends(get_db)):
    fail_key = await check_limit('login', request)
    data = await UserService.get_user_by_username(username=user.username, db=db, with_settings=True)
    if not (data and await verify_password(user.password, data.hashed_pwd)):
        await register_fail(fail_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный логин или пароль')
    if data.is_active is False:
        await register_fail(fail_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Аккаунт неактивен')
    if not data.settings.two_factor_enabled:
        await set_auth_cookie(response=response, token=create_jwt(uid=data.id, username=data.username))
        return {'success': True, 'msg': 'Вход успешно выполнен'}
    else:
        await set_2fa_cookie(response=response, token=create_2fa(uid=data.id, username=data.username))
        if await can_send_2fa_code(data, response, background_tasks):
            return {'success': True, 'msg': 'Код отправлен на почту'}
        return {'success': True, 'msg': 'Код уже отправлен, проверьте почту'}


@router.post(
    '/login/2fa',
    summary='Подтверждение входа кодом 2FA',
    description='Принимает код из письма и ставит cookie `access_token`. Требуется cookie `2fa_token` из `/login`.',
    responses={401: {'description': 'Код неверный или истёк'},
               429: {'description': 'Попытки закончились, запросите новый код'}},
)
async def _2falogin(usercode: VerifyCodeSchema, request: Request, response: Response):
    data = check_2fa_token(request=request)
    key = f"2fa_code:{data['uid']}"
    stored_code = await redis_client.hget(key, 'hashed_code')
    if stored_code is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Код истёк, запросите новый')
    attempts_left = await redis_client.hincrby(key, 'attempts', -1)
    if attempts_left < 0:
        await redis_client.delete(key)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Попытки закончились, запросите новый код')
    if not hmac.compare_digest(_hash_code(code=str(usercode.usercode)), stored_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Неверный код. Осталось попыток: {attempts_left}')
    await redis_client.delete(key)
    response.delete_cookie('2fa_token')
    await redis_client.delete(key, f"2fa_cd:{data['uid']}")
    await set_auth_cookie(response=response, token=create_jwt(uid=data['uid'], username=data['username']))
    return {'success': True, 'msg': 'Вход успешно выполнен'}


@router.post(
    '/login/2fa/resend',
    summary='Повторно отправить код 2FA',
    description='Отправляет новый код на почту. Требуется cookie `2fa_token`. Между отправками действует пауза.',
    responses={401: {'description': 'Сессия входа недействительна'},
               429: {'description': 'Повторить можно позже'}},
)
async def resend_2fa(request: Request, response: Response, background_tasks: BackgroundTasks, db=Depends(get_db)):
    data = check_2fa_token(request=request)
    user = await UserService.get_user_by_username(username=data['username'], db=db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Сессия входа недействительна')
    if not await can_send_2fa_code(user, response, background_tasks):
        ttl = await redis_client.ttl(f"2fa_cd:{user.id}")
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f'Повторить можно через {max(ttl, 1)} сек.')
    return {'success': True, 'msg': 'Код отправлен повторно'}


@router.post(
    '/logout',
    summary='Выход из аккаунта',
    description='Удаляет cookie `access_token`.',
)
async def logout(request: Request, response: Response):
    access_token = request.cookies.get('access_token')
    if not access_token:
        return {'success': False, 'msg': "Вы уже вышли"}
    response.delete_cookie(key='access_token')
    return {'success': True, 'msg': 'Вы вышли из аккаунта'}
