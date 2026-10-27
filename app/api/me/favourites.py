from typing import Annotated

from fastapi import APIRouter, Depends, Query

from schemas import MyAnnouncementFiltersSchema
from services import AnnouncementService
from core import get_db
from utils import get_current_user
from ..tags import TAG_FAVOURITES

router = APIRouter(prefix='/BookLet/me', tags=[TAG_FAVOURITES])


@router.get(
    '/my_favourites',
    summary='Мои избранные объявления',
    description='Объявления, которые я лайкнул. Поддерживает фильтры, сортировку и пагинацию. '
                'Поставить лайк можно в разделе «Каталог».',
    responses={401: {'description': 'Не авторизован'}},
)
async def my_favourites(filters: Annotated[MyAnnouncementFiltersSchema, Query()], current_data=Depends(get_current_user), db=Depends(get_db)):
    announcements = await AnnouncementService.get_liked_user_announcements(filters=filters, uid=current_data['uid'], db=db)
    return {'announcements': announcements, 'total': len(announcements)}
