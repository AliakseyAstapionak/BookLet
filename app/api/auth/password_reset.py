from fastapi import APIRouter, status, Depends, HTTPException, BackgroundTasks

from schemas import UserForgotPasswordSchema, ResetPasswordSchema
from services.email import EmailService
from services.users import UserService
from core import get_db
from utils import hash_password, create_reset_pwd_token, check_reset_pwd_token, _fp_password
from ..tags import TAG_PASSWORD_RESET

router = APIRouter(prefix='/BookLet', tags=[TAG_PASSWORD_RESET])


@router.post(
    '/forgot_password',
    summary='Запросить сброс пароля',
    description='Отправляет на почту ссылку для сброса пароля. Нужно указать логин и почту аккаунта.',
    responses={400: {'description': 'Данные не совпали или аккаунт неактивен'}},
)
async def forgot_password(user: UserForgotPasswordSchema, background_tasks: BackgroundTasks, db=Depends(get_db)):
    existing_user = await UserService.get_user_by_username(username=user.username, db=db)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Произошла ошибка, проверьте данные.')
    if existing_user.email != user.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Произошла ошибка, проверьте данные.')
    if not existing_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Аккаунт неактивен.')
    reset_token = create_reset_pwd_token(uid=existing_user.id, hashed_pwd=existing_user.hashed_pwd)
    reset_link = f"http://localhost:8000/reset_password?reset_token={reset_token}"
    background_tasks.add_task(EmailService.send_reset_password_email, email_to=existing_user.email, reset_link=reset_link)
    return {'success': True, "msg": f"Инструкция по сбросу пароля отправлена на ваш email."}


@router.post(
    '/reset_password',
    summary='Установить новый пароль',
    description='Принимает токен из ссылки в письме и новый пароль. Токен одноразовый: после смены пароля он перестаёт работать.',
    responses={400: {'description': 'Токен недействителен или данные неверны'},
               404: {'description': 'Пользователь не найден'}},
)
async def reset_password(data: ResetPasswordSchema, db=Depends(get_db)):
    payload = check_reset_pwd_token(data.token)
    user = await UserService.get_user_by_id(id=payload['uid'], db=db)
    if not user or not user.is_active or payload['fp'] != _fp_password(user.hashed_pwd):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Произошла ошибка. Проверьте данные")
    new_hashed_pwd = await hash_password(data.new_password)
    result = await UserService.reset_password(uid=payload['uid'], old_hash=user.hashed_pwd, new_hashed_pwd=new_hashed_pwd, db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не удалось поменять пароль, пользователь не найден.")
    return {'success': True, 'msg': 'Пароль успешно изменен'}
