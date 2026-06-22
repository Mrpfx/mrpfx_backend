from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Optional

from app.db.session import get_session
from app.model.traders import Trader, TraderPerformance
from app.repo.traders import TraderRepository
from app.schema.admin.traders import (
    TraderCreate, TraderUpdate,
    TraderPerformanceCreate, TraderPerformanceUpdate
)
from app.schema.traders import TraderInfo, TraderPerformanceRecord, TraderPerformanceResponse

router = APIRouter()

@router.post("", response_model=TraderInfo)
async def create_trader(
    trader_data: TraderCreate,
    session: AsyncSession = Depends(get_session)
):
    repo = TraderRepository(session)
    # Check if trader_id already exists
    existing = await repo.get_trader_by_id(trader_data.trader_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trader with ID '{trader_data.trader_id}' already exists."
        )

    trader = Trader(**trader_data.dict())
    created = await repo.create_trader(trader)

    return TraderInfo(
        trader_id=created.trader_id,
        name=created.name,
        type=created.type,
        strategy=created.strategy,
        description=created.description,
        profitFactor=created.profit_factor,
        avgTradeDuration=created.avg_trade_duration,
        bestTrade=created.best_trade,
        worstTrade=created.worst_trade
    )

@router.put("/{trader_id}", response_model=TraderInfo)
async def update_trader(
    trader_id: str,
    trader_data: TraderUpdate,
    session: AsyncSession = Depends(get_session)
):
    repo = TraderRepository(session)
    existing = await repo.get_trader_by_id(trader_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trader with ID '{trader_id}' not found."
        )

    update_dict = trader_data.dict(exclude_unset=True)
    updated = await repo.update_trader(trader_id, update_dict)

    return TraderInfo(
        trader_id=updated.trader_id,
        name=updated.name,
        type=updated.type,
        strategy=updated.strategy,
        description=updated.description,
        profitFactor=updated.profit_factor,
        avgTradeDuration=updated.avg_trade_duration,
        bestTrade=updated.best_trade,
        worstTrade=updated.worst_trade
    )

@router.delete("/{trader_id}")
async def delete_trader(
    trader_id: str,
    session: AsyncSession = Depends(get_session)
):
    repo = TraderRepository(session)
    existing = await repo.get_trader_by_id(trader_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trader with ID '{trader_id}' not found."
        )

    await repo.delete_trader(trader_id)
    return {"message": f"Trader '{trader_id}' and all associated performance records deleted."}

@router.post("/{trader_id}/performance", response_model=TraderPerformanceRecord)
async def add_performance(
    trader_id: str,
    perf_data: TraderPerformanceCreate,
    session: AsyncSession = Depends(get_session)
):
    repo = TraderRepository(session)
    existing = await repo.get_trader_by_id(trader_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trader with ID '{trader_id}' not found."
        )

    # Ensure trader_id in body matches path if provided, or set it
    perf_data.trader_id = trader_id

    performance = TraderPerformance(**perf_data.dict())
    created = await repo.create_performance(performance)

    return TraderPerformanceRecord(
        performance_id=created.id,
        month=created.month,
        winRate=created.win_rate,
        monthlyRoi=created.monthly_roi,
        maxDrawdown=created.max_drawdown,
        totalTrades=created.total_trades
    )

@router.put("/performance/{performance_id}", response_model=TraderPerformanceRecord)
async def update_performance(
    performance_id: int,
    perf_data: TraderPerformanceUpdate,
    session: AsyncSession = Depends(get_session)
):
    repo = TraderRepository(session)
    update_dict = perf_data.dict(exclude_unset=True)
    updated = await repo.update_performance(performance_id, update_dict)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Performance record with ID {performance_id} not found."
        )

    return TraderPerformanceRecord(
        performance_id=updated.id,
        month=updated.month,
        winRate=updated.win_rate,
        monthlyRoi=updated.monthly_roi,
        maxDrawdown=updated.max_drawdown,
        totalTrades=updated.total_trades
    )

@router.delete("/performance/{performance_id}")
async def delete_performance(
    performance_id: int,
    session: AsyncSession = Depends(get_session)
):
    repo = TraderRepository(session)
    await repo.delete_performance(performance_id)
    return {"message": f"Performance record with ID {performance_id} deleted."}
