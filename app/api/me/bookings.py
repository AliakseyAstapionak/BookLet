from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from schemas import MyBookingsResponseSchema
from services import BookingService, BookingStatus
from core import get_db
from utils import get_current_user
from ..tags import TAG_MY_BOOKINGS

router = APIRouter(prefix='/BookLet/me/my_bookings', tags=[TAG_MY_BOOKINGS])


@router.get(
    '',
    response_model=MyBookingsResponseSchema,
    summary='Мои брони',
    description='Услуги, которые я забронировал как клиент. Можно отфильтровать по статусу (`status`) '
                'и использовать пагинацию. Забронировать услугу можно в разделе «Каталог».',
    responses={401: {'description': 'Не авторизован'}},
)
async def get_my_bookings(status_filter: Optional[BookingStatus] = Query(default=None, alias='status'), limit: int = Query(default=20, ge=1, le=150),
                          offset: int = Query(default=0, ge=0),
                          db: AsyncSession = Depends(get_db),
                          current_user=Depends(get_current_user)):
    return await BookingService.get_my_bookings(status='as_client', user_id=current_user['uid'], status_filter=status_filter, limit=limit, offset=offset, db=db)


# #TODO сказать что нельзя отменить бронь если уже за определенное время до начала услуги, если нет то бронь отменить нельзя или только по заявке
# @router.post(
#     '/{anc_id}/cancel',
#     summary='Отменить бронь',
#     description='Отменяет мою бронь объявления: объявление снова становится активным, '
#                 'продавцу приходит уведомление.',
#     responses={401: {'description': 'Не авторизован'},
#                404: {'description': 'У вас нет активной брони на это объявление'},
#                409: {'description': 'Бронь уже отменена'}},
# )
# async def cancel_my_booking(anc_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
#     if await BookingService.cancel_my_booking(anc_id=anc_id, client_id=current_user['uid'], client_name=current_user['username'], db=db):
#         return {'success': True, 'msg': 'Бронь отменена'}
#     else:
#         return {'success': False, 'msg': 'Бронь не отменена, произошла ошибка'}
