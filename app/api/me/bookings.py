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


@router.post(
    '/{booking_id}/cancel',
    summary='Отменить бронь',
    description='Клиент может отменить бронь не позднее чем за `cancel_before_hours` часов до начала услуги '
                '(срок зафиксирован в брони при записи). Время снова становится свободным, '
                'мастеру приходит уведомление.',
    responses={**{401: {'description': 'Не авторизован'}},
               404: {'description': 'Бронь не найдена'},
               409: {'description': 'Бронь уже отменена, услуга началась или срок отмены прошёл'}},
)
async def cancel_my_booking(booking_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    await BookingService.cancel_booking(booking_id=booking_id, user_id=current_user['uid'],
                                        username=current_user['username'], role='client', db=db)
    return {'success': True, 'msg': 'Бронь отменена'}
