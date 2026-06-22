from typing import Optional, List
from pydantic import Field, BaseModel, field_validator

class BookBase(BaseModel):
    is_free: bool = Field(default=True, description="Whether the book is free")
    description: Optional[str] = Field("", description="Book description")
    price: Optional[float] = Field(0.0, description="Book price")
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

class BookCreate(BookBase):
    title: str = Field(..., description="Book title")
    status: Optional[str] = Field("publish", description="Post status")

class BookUpdate(BaseModel):
    title: Optional[str] = None
    is_free: Optional[bool] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    download_url: Optional[str] = None
    purchase_url: Optional[str] = None
    seller_payment_link: Optional[str] = None
    whop_payment_link: Optional[str] = None
    status: Optional[str] = None

class BookRead(BookBase):
    id: int
    title: str
    status: str

    class Config:
        from_attributes = True

class BookPagination(BaseModel):
    items: List[BookRead]
    total: int
    page: int
    pageSize: int
