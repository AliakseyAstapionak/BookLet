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

@router.post('/catalog/{anc_id}/like')
async def like_anc(anc_id: int, request: Request, db: AsyncSession =Depends(get_db), current_data=Depends(get_current_user)):
    announcement = await AnnouncementService.get_announcement(id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    result = await UserService.like_announcement(uid=current_data['uid'], anc_id=anc_id, db=db)
    return result


"""клиент отправляет запрос  →  бронь создаётся со статусом pending
                          →  провайдеру приходит уведомление
провайдер подтверждает    →  confirmed  (клиенту уведомление)
провайдер отклоняет       →  cancelled  (клиенту уведомление)"""


"""2. Уведомления в приложении. Таблица notifications и эндпоинт, который их отдаёт:

python
class NotificationModel(Base):
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    text: Mapped[str] = mapped_column(String(300))
    booking_id: Mapped[Optional[int]] = mapped_column(ForeignKey('bookings.id'))
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_col"""


#TODO подумать как лучще сделать проверку на второй раз подачи заявки, то есть что будет если продавец окажет бронировае, то тогда второй раз не сможет он отправить запрос на бронирование.
@router.post('/catalog/{anc_id}/book')
async def book_announcement(anc_id: int, request: Request, db: AsyncSession=Depends(get_db), current_data=Depends(get_current_user)):
    data = await BookingService.book_announcement(anc_id=anc_id, client_id=current_data['uid'], db=db)
    client_name = current_data['username']
    anc_name = await AnnouncementService.get_announcement_name(id=anc_id, db=db)
    msg_title = "🔔 Новый запрос на бронирование"
    msg_text = (
        f"Пользователь @{client_name} оставил заявку на бронирование "
        f"вашего объявления «{anc_name}».\n\n"
        f"📌 Статус: Ожидает подтверждения ⏳\n"
        f"Перейдите в личный кабинет, чтобы подтвердить или отклонить заявку."
    )
    success = await NotificationService.send_book_message(to_user_id=data['provider_id'], sender_id=current_data['uid'], title=msg_title, msg_text=msg_text, db=db)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Произошла ошибка, заявка не добавлена, попробуйте позже')
    
    
    return {"success": True, "message": "Запрос на бронирование успешно отправлен"}



    

