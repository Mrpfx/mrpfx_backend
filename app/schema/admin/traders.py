from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TraderCreate(BaseModel):
    trader_id: str = Field(..., description="String identifier like 'managerC'")
    name: str = Field(..., description="Display name, e.g., 'Elite Trader C'")
    type: str = Field("Aggressive", description="Trading style type")
    strategy: str = Field(..., description="Description of the trading strategy")
    description: Optional[str] = Field(None, description="Detailed strategy description")
    profit_factor: str = Field("0.00", description="e.g., '2.14'")
    avg_trade_duration: str = Field("0", description="e.g., '4.2 Days'")
    best_trade: str = Field("$0", description="e.g., '+$1,450'")
    worst_trade: str = Field("$0", description="e.g., '-$320'")

class TraderUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    strategy: Optional[str] = None
    description: Optional[str] = None
    profit_factor: Optional[str] = None
    avg_trade_duration: Optional[str] = None
    best_trade: Optional[str] = None
    worst_trade: Optional[str] = None

class TraderPerformanceCreate(BaseModel):
    trader_id: str
    month: str = Field(..., description="Formatted month string, e.g., 'February 2026'")
    date_timestamp: datetime = Field(default_factory=datetime.now, description="Used for sorting descending")
    win_rate: str = Field(..., description="e.g., '72%'")
    monthly_roi: str = Field(..., description="e.g., '15-25%'")
    max_drawdown: str = Field(..., description="e.g., '15%'")
    total_trades: str = Field(..., description="e.g., '4,850'")

class TraderPerformanceUpdate(BaseModel):
    month: Optional[str] = None
    win_rate: Optional[str] = None
    monthly_roi: Optional[str] = None
    max_drawdown: Optional[str] = None
    total_trades: Optional[str] = None
