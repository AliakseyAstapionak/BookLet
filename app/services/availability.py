from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import AvailabilityRuleModel
from schemas import CreateAvailabilityRuleSchema


class AvailabilityRuleService:

    @staticmethod
    async def create_operating_mode(rule: CreateAvailabilityRuleSchema, user_id: int,
                                    db: AsyncSession) -> AvailabilityRuleModel:
        query = (
            insert(AvailabilityRuleModel)
            .values(user_id=user_id, weekday=rule.weekday,
                    start_time=rule.start_time, end_time=rule.end_time)
            .on_conflict_do_update(
                index_elements=['user_id', 'weekday'],
                set_={'start_time': rule.start_time, 'end_time': rule.end_time},
            )
            .returning(AvailabilityRuleModel)
        )
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one()

    @staticmethod
    async def get_operating_mode(user_id: int, db: AsyncSession) -> list[AvailabilityRuleModel]:
        query = (select(AvailabilityRuleModel)
                 .where(AvailabilityRuleModel.user_id == user_id)
                 .order_by(AvailabilityRuleModel.weekday.asc()))
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def delete_operating_mode(weekday: int, user_id: int, db: AsyncSession) -> bool:
        query = delete(AvailabilityRuleModel).where(
            AvailabilityRuleModel.user_id == user_id,
            AvailabilityRuleModel.weekday == weekday,
        )
        result = await db.execute(query)
        await db.commit()
        return result.rowcount > 0