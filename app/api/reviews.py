from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import get_db
from schemas import CreateReviewSchema, ReviewResponseSchema, ReviewsResponseSchema
from services import ReviewService
from utils import get_current_user
from .tags import TAG_REVIEWS

router = APIRouter(prefix='/BookLet/catalog/{anc_id}/reviews', tags=[TAG_REVIEWS])


@router.get(
    '',
    response_model=ReviewsResponseSchema,
    summary='Отзывы об объявлении',
    description='Публичный список отзывов (новые сверху) со средней оценкой и общим количеством. '
                'Работает и для архивных объявлений.',
    responses={404: {'description': 'Объявление не найдено'}},
)
async def get_reviews(anc_id: int, limit: int = Query(default=20, ge=1, le=150), offset: int = Query(default=0, ge=0),
                      db: AsyncSession = Depends(get_db)):
    return await ReviewService.get_reviews(anc_id=anc_id, limit=limit, offset=offset, db=db)


@router.post(
    '',
    response_model=ReviewResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary='Оставить отзыв',
    description='Отзыв можно оставить только клиенту, который записывался на эту услугу, '
                'после того как время записи прошло. По одной брони — один отзыв. '
                'Свои объявления оценивать нельзя. Мастеру приходит уведомление.\n\n'
                'Если у вас несколько завершённых броней на это объявление, передайте `booking_id`, '
                'иначе отзыв привяжется к самой ранней брони без отзыва.',
    responses={401: {'description': 'Не авторизован'},
               403: {'description': 'Вы не записывались на эту услугу'},
               404: {'description': 'Объявление не найдено'},
               409: {'description': 'Услуга ещё не оказана, отзыв уже оставлен или это ваше объявление'}},
)
async def create_review(anc_id: int, review: CreateReviewSchema, db: AsyncSession = Depends(get_db),
                        current_user=Depends(get_current_user)):
    created = await ReviewService.create_review(
        anc_id=anc_id, author_id=current_user['uid'], author_name=current_user['username'],
        rating=review.rating, text=review.text, booking_id=review.booking_id, db=db)
    return {'success': True, 'review': created}
