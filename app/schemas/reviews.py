from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateReviewSchema(BaseModel):
    rating: int = Field(ge=1, le=5, description='Оценка от 1 до 5', examples=[5])
    text: str | None = Field(default=None, max_length=1000, description='Текст отзыва (необязательно)',
                             examples=['Всё отлично, мастер пришёл вовремя'])
    booking_id: int | None = Field(
        default=None,
        description='Бронь, к которой относится отзыв. Если не указана — берётся ваша самая ранняя '
                    'завершённая бронь на это объявление, по которой отзыв ещё не оставлен.')

    @field_validator('text')
    @classmethod
    def clean_text(cls, value: str | None):
        if value is None:
            return None
        value = value.strip()
        return value or None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    announcement_id: int
    booking_id: int
    author_id: int
    author_username: str
    provider_id: int
    rating: int
    text: str | None
    created_at: datetime


class ReviewResponseSchema(BaseModel):
    success: bool = True
    review: ReviewOut


class ReviewsResponseSchema(BaseModel):
    reviews: list[ReviewOut]
    total: int
    average_rating: float | None = Field(description='Средняя оценка, округлённая до 0.01. null, если отзывов нет')
