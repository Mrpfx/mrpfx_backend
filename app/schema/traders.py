from pydantic import BaseModel, Field
from typing import List, Optional

class TraderPerformanceRecord(BaseModel):
    performance_id: Optional[int] = Field(None, alias="performance_id")
    month: str = Field(..., alias="month")
    winRate: str = Field(..., alias="winRate")
    monthlyRoi: str = Field(..., alias="monthlyRoi")
    maxDrawdown: str = Field(..., alias="maxDrawdown")
    totalTrades: str = Field(..., alias="totalTrades")

class TraderInfo(BaseModel):
    trader_id: str
    name: str
    type: str
    strategy: str
    description: Optional[str] = None
    profit_factor: str = Field(..., alias="profitFactor")
    avg_trade_duration: str = Field(..., alias="avgTradeDuration")
    best_trade: str = Field(..., alias="bestTrade")
    worst_trade: str = Field(..., alias="worstTrade")

class TraderPerformanceResponse(TraderInfo):
    performance: List[TraderPerformanceRecord]

class TraderListResponse(BaseModel):
    traders: List[TraderInfo]
