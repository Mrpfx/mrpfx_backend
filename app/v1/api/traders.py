from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.db.session import get_session
from app.model.traders import Trader, TraderPerformance
from app.schema.traders import TraderPerformanceResponse, TraderPerformanceRecord, TraderListResponse, TraderInfo

from app.dependencies.auth import get_current_user

router = APIRouter(tags=["Traders"], dependencies=[Depends(get_current_user)])

@router.get("/traders", response_model=TraderListResponse)
async def list_traders(
    session: AsyncSession = Depends(get_session)
):
    """
    Retrieve a list of all available traders.
    """
    try:
        stmt = select(Trader)
        result = await session.exec(stmt)
        traders = result.all()

        return TraderListResponse(
            traders=[
                TraderInfo(
                    trader_id=t.trader_id,
                    name=t.name,
                    type=t.type,
                    strategy=t.strategy,
                    description=t.description,
                    profitFactor=t.profit_factor,
                    avgTradeDuration=t.avg_trade_duration,
                    bestTrade=t.best_trade,
                    worstTrade=t.worst_trade
                )
                for t in traders
            ]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing traders: {str(e)}"
        )

@router.get("/traders/{trader_id}/performance", response_model=TraderPerformanceResponse)
async def get_trader_performance(
    trader_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Retrieve up to 12 months of historical performance data for a specific trader.
    """
    try:
        # Fetch the trader details
        trader_stmt = select(Trader).where(Trader.trader_id == trader_id)
        trader_result = await session.exec(trader_stmt)
        trader = trader_result.first()

        if not trader:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trader with ID '{trader_id}' not found."
            )

        # Fetch the historical performance records
        perf_stmt = (
            select(TraderPerformance)
            .where(TraderPerformance.trader_id == trader_id)
            .order_by(TraderPerformance.date_timestamp.desc())
            .limit(12)
        )
        perf_result = await session.exec(perf_stmt)
        performances = perf_result.all()

        # Map to the response schema
        performance_records = [
            TraderPerformanceRecord(
                performance_id=perf.id,
                month=perf.month,
                winRate=perf.win_rate,
                monthlyRoi=perf.monthly_roi,
                maxDrawdown=perf.max_drawdown,
                totalTrades=perf.total_trades
            )
            for perf in performances
        ]

        return TraderPerformanceResponse(
            trader_id=trader.trader_id,
            name=trader.name,
            type=trader.type,
            strategy=trader.strategy,
            description=trader.description,
            profitFactor=trader.profit_factor,
            avgTradeDuration=trader.avg_trade_duration,
            bestTrade=trader.best_trade,
            worstTrade=trader.worst_trade,
            performance=performance_records
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving trader performance: {str(e)}"
        )
