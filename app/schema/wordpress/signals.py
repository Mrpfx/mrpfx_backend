from typing import Optional, List
from datetime import datetime
from pydantic import Field, BaseModel, field_validator
from .post import WPPostRead, WPPostBase

class SignalBase(BaseModel):
    instrument: str = Field(..., description="Trading instrument (e.g., EURUSD)")
    signal_type: str = Field(..., description="Signal type (vip or free)")
    entry: str = Field(..., description="Entry price")
    sl: str = Field(..., description="Stop Loss")
    tp1: str = Field(..., description="Take Profit 1")
    tp2: Optional[str] = Field(None, description="Take Profit 2")
    price: Optional[float] = Field(0.0, description="Signal price")
    image_url: Optional[str] = Field(None, description="Image URL")

    @field_validator('price', mode='before')
    @classmethod
    def parse_price(cls, v):
        if v == "":
            return 0.0
        return v

class SignalCreate(SignalBase):
    title: str = Field(..., description="Signal title")
    status: Optional[str] = Field("publish", description="Post status")

class SignalUpdate(BaseModel):
    title: Optional[str] = None
    instrument: Optional[str] = None
    signal_type: Optional[str] = None
    entry: Optional[str] = None
    sl: Optional[str] = None
    tp1: Optional[str] = None
    tp2: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    status: Optional[str] = None

class SignalRead(SignalBase):
    id: int
    title: str
    date: datetime
    status: str

    class Config:
        from_attributes = True

class SignalPagination(BaseModel):
    items: List[SignalRead]
    total: int
    page: int
    pageSize: int
