from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from core import get_db
from services import AnnouncementService, UserService
from sqlalchemy.ext.asyncio import AsyncSession
from utils import get_current_user
from typing import Annotated
from schemas import AnnouncementFiltersSchema
from models import UserModel
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

@router.post('/catalog/{anc_id}/like')
async def like_anc(anc_id: int, request: Request, db: AsyncSession =Depends(get_db), current_data=Depends(get_current_user)):
    announcement = await AnnouncementService.get_announcement(id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    result = await UserService.like_announcement(uid=current_data['uid'], anc_id=anc_id, db=db)
    return result




    

