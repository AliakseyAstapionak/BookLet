from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from utils import verify_password, hash_password
from schemas import ChangePasswordSchema, CreateAnnouncementSchema, AnnouncementResponseSchema
from services import UserService, AnnouncementService
from core import get_db
from utils import get_current_user


router = APIRouter(prefix='/BookLet', tags=['Функции пользователя'])

async def check_password(password, userdata: dict=Depends(get_current_user), db: AsyncSession=Depends(get_db)):
    hash_password = await UserService.get_password_by_username(username=userdata['username'], db=db)
    if not hash_password:
        return False
    return await verify_password(password=password ,hashed_password=hash_password)

#TODO попросить пароль для подтверждения
@router.post('/account/settings/security/2fa', response_model=None)
async def change_2fa(password: str, request: Request, db=Depends(get_db), current_data=Depends(get_current_user), check_pass=Depends(check_password)):
    if not check_pass:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный пароль')  
    result = await UserService.change_2fa(user_id=current_data['uid'], db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Не удалось поменять значение 2fa')
    return {'success': True, 'msg': 'Данные изменены успешно'}

@router.post('/account/settings/security/change_password')
async def change_password(data: ChangePasswordSchema, request: Request, db=Depends(get_db), current_data=Depends(get_current_user)):
    if not await check_password(data.password, current_data, db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный пароль') 
    new_hash_password = await hash_password(data.new_password)
    result = await UserService.change_password(user_id=current_data['uid'], new_hash_password=new_hash_password, db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не удалось поменять пароль")
    return {'success': True, 'msg': 'Пароль успешно изменен'}


@router.post('/my_announcements/create')
async def create_announcement(anc: CreateAnnouncementSchema, db=Depends(get_db), current_data=Depends(get_current_user)):
    user_id = current_data['uid']
    new_announcement = await AnnouncementService.create_announcement(user_id=current_data['uid'], name=anc.name, status=anc.status, type=anc.type,
                                                                    price=anc.price, description=anc.description, db=db)
    return {'success': True, 'new_announcement': new_announcement}

#TODO добавить фильтры 
@router.post('/my_announcements', response_model=AnnouncementResponseSchema)
async def my_anniouncemets(request: Request, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcements = await AnnouncementService.get_my_announcements(user_id=user_id, db=db)
    return {'announcements': announcements}


#TODO подумать а можно ли удалять вообщще забронированные(пока что нельзя)
@router.post('/my_announcements/{anc_id}/archive')
async def delete_annoncement(anc_id: int, request: Request, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    anc_user = await AnnouncementService.get_announcement_user(id=anc_id, db=db)
    if anc_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    if user_id != anc_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')   # см. ниже
    if not await AnnouncementService.delete_announcement(id=anc_id, db=db):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail='Нельзя удалить забронированное или уже архивированное объявление')
    return {'success': True, 'msg': 'Объявление занесено в архив'}
