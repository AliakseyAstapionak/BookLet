from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from core import get_db
from services import AnnouncementService, UserService, BookingService, NotificationService
from sqlalchemy.ext.asyncio import AsyncSession
from utils import get_current_user
from typing import Annotated
from schemas import AnnouncementFiltersSchema
from sqlalchemy import select
router = APIRouter(prefix='/BookLet', tags=['Каталог'])

# TODO добавить в фильтры мо
@router.get('/catalog')
async def catalog(filters: Annotated[AnnouncementFiltersSchema, Query()],db=Depends(get_db)):
    result = await AnnouncementService.get_catalog(filters=filters, db=db)
    return {'announcements': result}

@router.post('/catalog/{anc_id}')
async def announcement(anc_id: int, db=Depends(get_db)):
    result = await AnnouncementService.get_announcement(id=anc_id, db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Данное обьявление не найдено')
    if result.status == 'archived' or result.status == 'booked':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Данное обьявление недоступно')
    return {'success': True, 'announcement': result}


#TODO сделать проверку на то чтобы нелья было лакать свои обьявления
@router.post('/catalog/{anc_id}/like')
async def like_anc(anc_id: int, request: Request, db: AsyncSession =Depends(get_db), current_data=Depends(get_current_user)):
    announcement = await AnnouncementService.get_announcement(id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    result = await UserService.like_announcement(uid=current_data['uid'], anc_id=anc_id, db=db)
    return result

#TODO подумать на каких условиях продавец может отменить бронь
#TODO подумать как лучще сделать проверку на второй раз подачи заявки, то есть что будет если продавец окажет бронировае, то тогда второй раз не сможет он отправить запрос на бронирование.
@router.post('/catalog/{anc_id}/book')
async def book_announcement(anc_id: int, request: Request, db: AsyncSession=Depends(get_db), current_data=Depends(get_current_user)):
    client_name = current_data['username']
    client_id = current_data['uid']
    booking = await BookingService.book_announcement(anc_id=anc_id, client_id=client_id, client_name=client_name, db=db)

    return {"success": True, "message": "Бронирование прошло успешно"}



    

