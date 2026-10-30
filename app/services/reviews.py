from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import AnnouncementModel, BookingModel, BookingStatus, ReviewModel, UserModel
from services.notifications import NotificationService
from services.slots import SERVICE_TZ


REVIEWABLE_STATUSES = (BookingStatus.CONFIRMED, BookingStatus.COMPLETED)


def _review_out(review: ReviewModel, author_username: str) -> dict:
    return {
        'id': review.id, 'announcement_id': review.announcement_id, 'booking_id': review.booking_id,
        'author_id': review.author_id, 'author_username': author_username,
        'provider_id': review.provider_id, 'rating': review.rating, 'text': review.text,
        'created_at': review.created_at,
    }


class ReviewService:

    @staticmethod
    async def _get_announcement(anc_id: int, db: AsyncSession) -> AnnouncementModel:
        announcement = (await db.execute(
            select(AnnouncementModel).where(AnnouncementModel.id == anc_id))).scalar()
        if announcement is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Данное обьявление не найдено')
        return announcement

    @staticmethod
    async def create_review(anc_id: int, author_id: int, author_name: str, rating: int, text: str | None,
                            booking_id: int | None, db: AsyncSession) -> dict:
        announcement = await ReviewService._get_announcement(anc_id=anc_id, db=db)
        if announcement.user_id == author_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Нельзя оставить отзыв на своё объявление')

        now = datetime.now(SERVICE_TZ)
        own = [BookingModel.announcement_id == anc_id, BookingModel.client_id == author_id]
        if booking_id is not None:
            own.append(BookingModel.id == booking_id)

        booking = (await db.execute(
            select(BookingModel)
            .outerjoin(ReviewModel, ReviewModel.booking_id == BookingModel.id)
            .where(*own, ReviewModel.id.is_(None),
                   BookingModel.status.in_(REVIEWABLE_STATUSES), BookingModel.end_at <= now)
            .order_by(BookingModel.end_at.asc(), BookingModel.id.asc())
            .limit(1)
        )).scalar()

        if booking is None:
            await ReviewService._raise_not_reviewable(own=own, now=now, db=db)

        review = ReviewModel(announcement_id=anc_id, booking_id=booking.id, author_id=author_id,
                             provider_id=booking.provider_id, rating=rating, text=text)
        db.add(review)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Отзыв по этой брони уже оставлен')

        await NotificationService.send_book_message(
            to_user_id=booking.provider_id, sender_id=author_id, title='Новый отзыв',
            msg_text=f'Пользователь {author_name} оценил «{announcement.name}» на {rating} из 5.',
            notif_type='review', booking_id=booking.id, commit=False, db=db)
        await db.commit()
        await db.refresh(review)
        return _review_out(review, author_name)

    @staticmethod
    async def _raise_not_reviewable(own: list, now: datetime, db: AsyncSession) -> None:
        mine = (await db.execute(select(BookingModel).where(*own))).scalars().all()
        if not mine:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail='Оставить отзыв можно только после записи на эту услугу')
        done = [b for b in mine if b.status in REVIEWABLE_STATUSES and b.end_at <= now]
        if not done:
            if all(b.status == BookingStatus.CANCELLED for b in mine):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail='Нельзя оставить отзыв по отменённой брони')
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail='Отзыв можно оставить после того, как услуга будет оказана')
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail='Отзыв по этой услуге уже оставлен')

    @staticmethod
    async def get_reviews(anc_id: int, limit: int, offset: int, db: AsyncSession) -> dict:
        await ReviewService._get_announcement(anc_id=anc_id, db=db)

        total, avg = (await db.execute(
            select(func.count(ReviewModel.id), func.avg(ReviewModel.rating))
            .where(ReviewModel.announcement_id == anc_id))).one()

        rows = (await db.execute(
            select(ReviewModel, UserModel.username)
            .join(UserModel, UserModel.id == ReviewModel.author_id)
            .where(ReviewModel.announcement_id == anc_id)
            .order_by(ReviewModel.created_at.desc(), ReviewModel.id.desc())
            .limit(limit).offset(offset))).all()

        return {
            'reviews': [_review_out(review, username) for review, username in rows],
            'total': total,
            'average_rating': round(float(avg), 2) if avg is not None else None,
        }
