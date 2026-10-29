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
                index_elements=['user_id', 'weekday'],          # та самая пара из UniqueConstraint
                set_={'start_time': rule.start_time, 'end_time': rule.end_time},
            )
            .returning(AvailabilityRuleModel)
        )
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one()