from typing import List, Optional, Type
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, update, delete
from app.model.traders import Trader, TraderPerformance

class TraderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_traders(self) -> List[Trader]:
        stmt = select(Trader)
        result = await self.session.exec(stmt)
        return result.all()

    async def get_trader_by_id(self, trader_id: str) -> Optional[Trader]:
        stmt = select(Trader).where(Trader.trader_id == trader_id)
        result = await self.session.exec(stmt)
        return result.first()

    async def create_trader(self, trader: Trader) -> Trader:
        self.session.add(trader)
        await self.session.commit()
        await self.session.refresh(trader)
        return trader

    async def update_trader(self, trader_id: str, data: dict) -> Optional[Trader]:
        stmt = update(Trader).where(Trader.trader_id == trader_id).values(**data)
        await self.session.exec(stmt)
        await self.session.commit()
        return await self.get_trader_by_id(trader_id)

    async def delete_trader(self, trader_id: str) -> bool:
        # First delete performance records to avoid foreign key constraint issues
        perf_stmt = delete(TraderPerformance).where(TraderPerformance.trader_id == trader_id)
        await self.session.exec(perf_stmt)

        # Then delete the trader record
        stmt = delete(Trader).where(Trader.trader_id == trader_id)
        await self.session.exec(stmt)

        await self.session.commit()
        return True

    async def get_trader_performance(self, trader_id: str, limit: int = 12) -> List[TraderPerformance]:
        stmt = (
            select(TraderPerformance)
            .where(TraderPerformance.trader_id == trader_id)
            .order_by(TraderPerformance.date_timestamp.desc())
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return result.all()

    async def create_performance(self, performance: TraderPerformance) -> TraderPerformance:
        self.session.add(performance)
        await self.session.commit()
        await self.session.refresh(performance)
        return performance

    async def update_performance(self, performance_id: int, data: dict) -> Optional[TraderPerformance]:
        stmt = update(TraderPerformance).where(TraderPerformance.id == performance_id).values(**data)
        await self.session.exec(stmt)
        await self.session.commit()

        # Fetch and return the updated record
        fetch_stmt = select(TraderPerformance).where(TraderPerformance.id == performance_id)
        result = await self.session.exec(fetch_stmt)
        return result.first()

    async def delete_performance(self, performance_id: int) -> bool:
        stmt = delete(TraderPerformance).where(TraderPerformance.id == performance_id)
        await self.session.exec(stmt)
        await self.session.commit()
        return True
