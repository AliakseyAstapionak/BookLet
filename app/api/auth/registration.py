import hmac

from fastapi import APIRouter, status, Depends, HTTPException, BackgroundTasks, Response, Request

from schemas import UserRegistrationSchema, UserPublicActionSchema, VerifyCodeSchema
from services.users import UserService
from core import get_db, redis_client
from utils import (_hash_code, hash_password, create_reg_token, set_reg_cookie, check_reg_token,
                   check_limit, register_fail, can_send_registration_code, can_resend_registration_code)
from ..tags import TAG_REGISTRATION

router = APIRouter(prefix='/BookLet', tags=[TAG_REGISTRATION])


@router.post(
    '/registration',
    summary='Шаг 1. Заявка на регистрацию',
    description='Проверяет, что имя и почта свободны, и отправляет на почту код подтверждения. '
                'Аккаунт на этом шаге **ещё не создаётся**. В ответ ставится cookie `reg_token`, '
                'она нужна для следующего шага.',
    responses={400: {'description': 'Имя или почта уже заняты'},
               429: {'description': 'Слишком много попыток регистрации'}},
)
async def registration(newuser: UserRegistrationSchema, request: Request, background_tasks: BackgroundTasks, response: Response, db=Depends(get_db)):
    fail_key = await check_limit('registration', request)
    if await UserService.existing_username(username=newuser.username, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Данное имя уже занято')
    if await UserService.existing_email(email=newuser.email, db=db):
        await register_fail(fail_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Данная почта уже занята')
    hashed_pwd = await hash_password(newuser.password)
    await set_reg_cookie(response=response, token=create_reg_token(username=newuser.username, email=newuser.email))
    if not await can_send_registration_code(newuser.username, newuser.email, hashed_pwd, background_tasks):
        return {'success': True, 'msg': 'Код уже отправлен, проверьте почту'}
    return {'success': True, 'msg': 'Подтвердите регистрацию. Инструкция указана на данную почту'}


@router.post(
    '/registration/verify_email',
    response_model=UserPublicActionSchema,
    status_code=status.HTTP_201_CREATED,
    summary='Шаг 2. Подтверждение почты',
    description='Принимает код из письма и создаёт аккаунт. Требуется cookie `reg_token` из шага 1. '
                'Количество попыток ограничено.',
    responses={401: {'description': 'Код неверный или истёк'},
               429: {'description': 'Попытки закончились'}},
)
async def verify_email(usercode: VerifyCodeSchema, request: Request, response: Response, db=Depends(get_db)):
    data = check_reg_token(request)
    key = f'reg_code:{data["email"]}'
    stored_code = await redis_client.hget(key, 'hashed_code')
    if stored_code is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Код истёк, запросите новый')
    attempts_left = await redis_client.hincrby(key, 'attempts', -1)
    if attempts_left < 0:
        await redis_client.delete(key)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Вы сделали слишком много попыток')
    if not hmac.compare_digest(_hash_code(code=str(usercode.usercode)), stored_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Неверный код. Осталось попыток: {attempts_left}')
    newuser = await redis_client.hgetall(key)
    await redis_client.delete(key)
    response.delete_cookie('reg_token')
    new_user = await UserService.create_user(username=newuser['username'], email=newuser['email'], hashed_pwd=newuser['hashed_pwd'], db=db)
    return {'success': True, 'user': new_user}


@router.post(
    '/registration/verify_email/resend_code',
    summary='Повторно отправить код подтверждения',
    description='Отправляет код ещё раз. Требуется cookie `reg_token`. Между отправками действует пауза.',
)
async def resend_email_code(request: Request, background_tasks: BackgroundTasks):
    data = check_reg_token(request)
    await can_resend_registration_code(email=data['email'], background_tasks=background_tasks)
    return {'success': True, 'msg': 'Код отправлен повторно'}
