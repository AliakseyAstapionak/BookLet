from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from utils import verify_password, hash_password, get_current_user
from schemas import ChangePasswordSchema, Change2FASchema, ChangeShowEmailSchema
from services import UserService
from core import get_db
from ..tags import TAG_SECURITY

router = APIRouter(prefix='/BookLet/me/account/settings/security', tags=[TAG_SECURITY])


async def check_password(data: Change2FASchema, userdata: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hash_password = await UserService.get_password_by_username(username=userdata['username'], db=db)
    if not hash_password:
        return False
    return await verify_password(password=data.password, hashed_password=hash_password)


@router.post(
    '/2fa',
    response_model=None,
    summary='Включить или выключить 2FA',
    description='Переключает двухфакторную аутентификацию на противоположное значение. '
                'Требуется текущий пароль.',
    responses={400: {'description': 'Неверный пароль'},
               401: {'description': 'Не авторизован'}},
)
async def change_2fa(data: Change2FASchema, request: Request, db=Depends(get_db), current_data=Depends(get_current_user), check_pass=Depends(check_password)):
    if not check_pass:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный пароль')
    result = await UserService.change_2fa(user_id=current_data['uid'], db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Не удалось поменять значение 2fa')
    return {'success': True, 'msg': 'Данные изменены успешно'}


@router.post(
    '/show_email',
    response_model=None,
    summary='Включить или выключить показ email',
    description='Переключает показ вышей почты другим пользователям на противоположное значение. '
                'Требуется текущий пароль.',
    responses={400: {'description': 'Неверный пароль'},
               401: {'description': 'Не авторизован'}},
)
async def change_show_email(data: Change2FASchema, request: Request, db=Depends(get_db), current_data=Depends(get_current_user), check_pass=Depends(check_password)):
    if not check_pass:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный пароль')
    result = await UserService.change_show_email(user_id=current_data['uid'], db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Не удалось поменять значение показа почты')
    return {'success': True, 'msg': 'Данные изменены успешно'}



@router.post(
    '/change_password',
    summary='Сменить пароль',
    description='Требуется текущий пароль и новый пароль.',
    responses={400: {'description': 'Неверный текущий пароль'},
               401: {'description': 'Не авторизован'},
               404: {'description': 'Не удалось поменять пароль'}},
)
async def change_password(data: ChangePasswordSchema, db=Depends(get_db), current_data=Depends(get_current_user)):
    if not await check_password(data, current_data, db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный пароль')
    new_hash_password = await hash_password(data.new_password)
    result = await UserService.change_password(user_id=current_data['uid'], new_hash_password=new_hash_password, db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не удалось поменять пароль")
    return {'success': True, 'msg': 'Пароль успешно изменен'}
