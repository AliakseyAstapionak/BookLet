from fastapi import APIRouter, status, Depends, HTTPException, BackgroundTasks, Response, Request
from schemas import UserRegistrationSchema, UserPublicActionSchema, UserLoginSchema, UserForgotPasswordSchema, ResetPasswordSchema
from services.email import EmailService 
from services.users import UserService
from core import get_db, redis_client
from utils import (hash_password, verify_password, create_jwt, set_auth_cookie, set_2fa_cookie, create_2fa,
can_send_2fa_code, check_login_limit, register_login_fail, _hash_code, check_2fa_token, create_reset_pwd_token, check_reset_pwd_token,
_fp_password, create_reg_token, set_reg_cookie, check_reg_token, register_reg_fail, check_registration_limit, can_send_registration_code)
import hmac

import random

router = APIRouter(prefix='/BookLet', tags=["Авторизация и регистрация"])




@router.post('/registration')
async def registration(newuser: UserRegistrationSchema, request: Request, background_tasks: BackgroundTasks, response: Response, db=Depends(get_db)):
    """Регистрация нового пользователя в системе.
      1. Проверяет, не занято ли указанное имя пользователя (`username`).
      2. Проверяет, не зарегистрирована ли уже такая электронная почта (`email`).
      3. Хеширует переданный пароль в целях безопасности.
      4. Создает запись пользователя в базе данных и возвращает статус успеха."""
    fail_key = await check_registration_limit(request)
    if await UserService.existing_username(username=newuser.username, db=db):
        await register_reg_fail(fail_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Данное имя уже занято')
    if await UserService.existing_email(email=newuser.email, db=db):
        await register_reg_fail(fail_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Данная почта уже занята')
    hashed_pwd = await hash_password(newuser.password)
    await set_reg_cookie(response=response, token=create_reg_token(username=newuser.username, email=newuser.email))
    if not await can_send_registration_code(newuser.username, newuser.email, hashed_pwd, background_tasks):
        return {'success': True, 'msg': 'Код уже отправлен, проверьте почту'}
    return {'success': True, 'msg': 'Подтвердите регистрацию. Инструкция указана на данную почту'}

@router.post('/registration/verify_email', response_model=UserPublicActionSchema, status_code=status.HTTP_201_CREATED)
async def verify_email(usercode: str, request: Request, response: Response, db=Depends(get_db)):
    data = check_reg_token(request)
    key = f'reg_code:{data["email"]}'
    stored_code = await redis_client.hget(key, 'hashed_code')
    if stored_code is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Код истёк, запросите новый')
    attempts_left = await redis_client.hincrby(key, 'attempts', -1)
    if attempts_left < 0:
        await redis_client.delete(key)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Вы сделали слишком много попыток')
    if not hmac.compare_digest(_hash_code(code=str(usercode)), stored_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Неверный код. Осталось попыток: {attempts_left}')
    newuser = await redis_client.hgetall(key)
    await redis_client.delete(key)
    response.delete_cookie('reg_token')
    new_user = await UserService.create_user(username=newuser['username'], email=newuser['email'], hashed_pwd=newuser['hashed_pwd'], db=db)
    return {'success': True, 'user': new_user}


@router.post('/login')
async def login(user: UserLoginSchema, background_tasks: BackgroundTasks, response: Response, request: Request, db=Depends(get_db),):
    """Аутентификация пользователя и инициализация сессии или двухфакторной аутентификации (2FA).
  Логика работы эндпоинта:
    1. **Rate Limiting:** Проверяет количество неудачных попыток входа с текущего
    IP-адреса (`check_login_limit`).
    2. **Проверка учетных данных:** Ищет пользователя в базе и сверяет хеш
    пароля. При ошибке фиксирует неудачную попытку в Redis и возвращает статус
    400.
    3. **Сценарий без 2FA:** Выпускает постоянный access-токен (с типом `access`
    в payload), записывает его в куки и завершает вход.
    4. **Сценарий с 2FA:**
       - Сразу устанавливает временный `2fa_token` через `set_2fa_cookie`.
       *Важно:* Установка токена происходит до проверки кулдауна отправки кода.
       Это критически важно, чтобы при входе с другого устройства или новой
       вкладки у клиента гарантированно сохранился актуальный токен с типом
       `2fa` в полезной нагрузке. Поскольку access и 2fa токены содержат похожие
       данные (uid, username), валидация поля `type` исключает подмену контекста
       безопасности.
       - Проверяет кулдаун отправки (`can_send_2fa_code`) и отправляет
       одноразовый код на email через фоновые задачи (`BackgroundTasks`), если
       лимит времени исчерпан."""
    fail_key = await check_login_limit(request)
    data = await UserService.get_user_by_username(username=user.username, db=db)
    if not (data and await verify_password(user.password, data.hashed_pwd)):
        await register_login_fail(fail_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный логин или пароль')
    if data.is_active is False:
        await register_login_fail(fail_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Аккаунт неактивен')
    if not data._2fa: 
        await set_auth_cookie(response=response, token=create_jwt(uid=data.id, username=data.username))
        return {'success': True, 'msg': 'Вход успешно выполнен'}
    else:
        await set_2fa_cookie(response=response, token=create_2fa(uid=data.id, username=data.username))
        if await can_send_2fa_code(data, response, background_tasks):
            return {'success': True, 'msg': 'Код отправлен на почту'}
        return {'success': True, 'msg': 'Код уже отправлен, проверьте почту'}


@router.post('/login/2fa')
async def _2falogin(usercode: int, request: Request, response: Response):
    """Подтверждение двухфакторной аутентификации (2FA) по одноразовому коду.
    Этапы выполнения:
        1. Получает данные пользователя из временного токена 2FA в куках через запрос.
        2. Проверяет наличие и срок действия хэшированного кода в Redis.
        3. Уменьшает счетчик оставшихся попыток ввода.
        4. Сравнивает хэш введенного кода с эталонным с помощью безопасного сравнения.
        5. При успехе удаляет временные данные из Redis, очищает временную куку и устанавливает постоянный JWT-токен авторизации."""
    data = check_2fa_token(request=request)
    key = f"2fa_code:{data['uid']}"
    stored_code = await redis_client.hget(key, 'hashed_code')
    if stored_code is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Код истёк, запросите новый')
    attempts_left = await redis_client.hincrby(key, 'attempts', -1)
    if attempts_left < 0:
        await redis_client.delete(key)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Попытки закончились, запросите новый код')
    if not hmac.compare_digest(_hash_code(code=str(usercode)), stored_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Неверный код. Осталось попыток: {attempts_left}')
    await redis_client.delete(key)
    response.delete_cookie('2fa_token')
    await redis_client.delete(key, f"2fa_cd:{data['uid']}")
    await set_auth_cookie(response=response, token=create_jwt(uid=data['uid'], username=data['username']))
    return {'success': True, 'msg': 'Вход успешно выполнен'}


@router.post('/login/2fa/resend')
async def resend_2fa(request: Request, response: Response, background_tasks: BackgroundTasks, db=Depends(get_db)):
    """Повторная отправка кода двухфакторной аутентификации (2FA).
    Этапы выполнения:
        - Проверяет валидность временного токена 2FA из кук запроса и извлекает данные сессии.
        - Получает информацию о пользователе из базы данных по имени пользователя.
        - Проверяет наличие активного кулдауна на отправку нового кода.
        - Генерирует и отправляет новый код (через фоновые задачи), если кулдаун истек."""
    data = check_2fa_token(request=request)
    user = await UserService.get_user_by_username(username=data['username'], db=db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Сессия входа недействительна')
    if not await can_send_2fa_code(user, response, background_tasks):
        ttl = await redis_client.ttl(f"2fa_cd:{user.id}")
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f'Повторить можно через {max(ttl, 1)} сек.')
    return {'success': True, 'msg': 'Код отправлен повторно'}


@router.post('/logout')
async def logout(request: Request, response: Response):
    access_token = request.cookies.get('access_token')
    if not access_token:
        return {'success': False, 'msg': "Вы уже вышли"}
    response.delete_cookie(key='access_token')
    return {'success': True, 'msg': 'Вы вышли из аккаунта'}

    
@router.post('/forgot_password')
async def forgot_password(user: UserForgotPasswordSchema,background_tasks: BackgroundTasks, db=Depends(get_db)):
    """Инициирует процесс восстановления доступа (сброса пароля).
        1. Находит пользователя в базе данных по `username`.
        2. Сравнивает переданный `email` с email пользователя из базы.
        3. Проверяет активность аккаунта (`is_active`).
        4. Генерирует одноразовый `reset_token` на основе ID и хэша пароля.
        5. Формирует ссылку для восстановления доступа.
        6. Добавляет задачу отправки письма с ссылкой в фоновый режим.
        7. Возвращает подтверждение об отправке инструкции."""
    existing_user = await UserService.get_user_by_username(username=user.username, db=db)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Произошла ошибка, проверьте данные.')
    if existing_user.email != user.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail= 'Произошла ошибка, проверьте данные.')
    if not existing_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Аккаунт неактивен.')
    reset_token = create_reset_pwd_token(uid=existing_user.id, hashed_pwd=existing_user.hashed_pwd)
    reset_link = f"http://BookLet/reset_password?reset_token={reset_token}"
    background_tasks.add_task(EmailService.send_reset_password_email, email_to=existing_user.email, reset_link=reset_link)
    return {'success': True, "msg": f"Инструкция по сбросу пароля отправлена на ваш email: {existing_user.email}."}

@router.post('/reset_password')
async def reset_password(data: ResetPasswordSchema, db=Depends(get_db)):
    """Инициирует процедуру установки нового пароля по токену восстановления.

    Порядок выполнения:
        1. Проверяет и расшифровывает токен сброса пароля из запроса (`data.token`).
        2. Получает пользователя из базы данных по ID (`uid`) из полезной нагрузки токена.
        3. Проверяет валидность:
            - Существует ли активный пользователь.
            - Соответствует ли хэш текущего пароля отпечатку (`fp`) в токене
              (гарантирует, что токен одноразовый и станет недействительным
              после смены пароля).
        4. Хэширует новый пароль пользователя.
        5. Обновляет пароль в базе данных с проверкой старого хэша.
        6. Возвращает статус успешного изменения пароля."""
    payload = check_reset_pwd_token(data.token)
    user = await UserService.get_user_by_id(id=payload['uid'], db=db)        
    if not user or not user.is_active or payload['fp'] != _fp_password(user.hashed_pwd):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Произошла ошибка. Проверьте данные")  
    new_hashed_pwd = await hash_password(data.new_password)
    result = await UserService.reset_password(uid=payload['uid'], old_hash=user.hashed_pwd, new_hashed_pwd=new_hashed_pwd, db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не удалось поменять пароль, пользователь не найден.")
    return {'success': True, 'msg': 'Пароль успешно изменен'}





                                     