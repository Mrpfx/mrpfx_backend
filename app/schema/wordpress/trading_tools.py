from typing import Optional, List
from pydantic import Field, BaseModel, field_validator

class TradingToolBase(BaseModel):
    tool_type: str = Field(..., description="Tool type (bot or indicator)")
    category: str = Field(..., description="Category (vip or free)")
    description: Optional[str] = Field("", description="Tool description")
    price: Optional[float] = Field(0.0, description="Tool price")
    image_url: Optional[str] = Field(None, description="Image URL")
    download_url: Optional[str] = Field(None, description="Download URL")
    purchase_url: Optional[str] = Field(None, description="Purchase URL")
    seller_payment_link: Optional[str] = Field(None, description="Selar payment link")
    whop_payment_link: Optional[str] = Field(None, description="Whop payment link")

    @field_validator('price', mode='before')
    @classmethod
    def parse_price(cls, v):
        if v == "":
            return 0.0
        return v

class TradingToolCreate(TradingToolBase):
    title: str = Field(..., description="Tool title")
    status: Optional[str] = Field("publish", description="Post status")

class TradingToolUpdate(BaseModel):
    title: Optional[str] = None
    tool_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    download_url: Optional[str] = None
    purchase_url: Optional[str] = None
    seller_payment_link: Optional[str] = None
    whop_payment_link: Optional[str] = None
    status: Optional[str] = None

class TradingToolRead(TradingToolBase):
    id: int
    title: str
    status: str

    class Config:
        from_attributes = True

class TradingToolPagination(BaseModel):
    items: List[TradingToolRead]
    total: int
    page: int
    pageSize: int
