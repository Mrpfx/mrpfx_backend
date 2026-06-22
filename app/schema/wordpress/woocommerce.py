"""
WooCommerce Pydantic Schemas for API responses and requests.
"""
from typing import Optional, List, Dict
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schema.wordpress.post import WPImageRead


# ============== Product Sub-Schemas ==============

class WCProductCategoryRead(BaseModel):
    """Product category schema"""
    id: int = Field(..., description="Category term ID")
    name: str = Field("", description="Category name")
    slug: str = Field("", description="Category slug")
    parent: Optional[int] = Field(0, description="Parent category ID")
    description: Optional[str] = Field("", description="Category description")
    count: Optional[int] = Field(0, description="Number of products in category")

    class Config:
        from_attributes = True


class WCProductTagRead(BaseModel):
    """Product tag schema"""
    id: int = Field(..., description="Tag term ID")
    name: str = Field("", description="Tag name")
    slug: str = Field("", description="Tag slug")
    count: Optional[int] = Field(0, description="Number of products with tag")

    class Config:
        from_attributes = True


class WCProductAttributeRead(BaseModel):
    """Product attribute schema"""
    id: int = Field(0, description="Attribute ID (0 for local attributes)")
    name: str = Field("", description="Attribute name")
    slug: Optional[str] = Field("", description="Attribute taxonomy slug")
    position: int = Field(0, description="Attribute display position")
    visible: bool = Field(True, description="Whether visible on product page")
    variation: bool = Field(False, description="Whether used for variations")
    options: List[str] = Field(default_factory=list, description="Attribute options/values")

    class Config:
        from_attributes = True


class WCProductDimensions(BaseModel):
    """Product dimensions"""
    length: Optional[str] = Field(None, description="Length")
    width: Optional[str] = Field(None, description="Width")
    height: Optional[str] = Field(None, description="Height")


class WCProductAddonField(BaseModel):
    """A single custom input field for a product (e.g. Telegram Username)"""
    name: str = Field(..., description="Field name/label, e.g. 'Telegram Username'")
    type: str = Field("text", description="Field type: text, textarea, select, checkbox, radio, number, email")
    required: bool = Field(False, description="Whether the field is required")
    placeholder: Optional[str] = Field(None, description="Placeholder text for input fields")
    description: Optional[str] = Field(None, description="Help text shown below the field")
    options: List[str] = Field(default_factory=list, description="Options for select/radio/checkbox fields")
    position: int = Field(0, description="Display order position")
    max_length: Optional[int] = Field(None, description="Max character length for text fields")


class WCProductAddonsCreate(BaseModel):
    """Request to set custom input fields on a product"""
    addons: List[WCProductAddonField] = Field(..., description="List of custom input fields")


class WCProductAddonsRead(BaseModel):
    """Response with product custom input fields"""
    product_id: int
    addons: List[WCProductAddonField] = Field(default_factory=list)


class WCProductVariationRead(BaseModel):
    """Product variation schema"""
    id: int = Field(..., description="Variation ID")
    sku: Optional[str] = Field(None, description="SKU")
    price: Optional[Decimal] = Field(None, description="Active price")
    regular_price: Optional[Decimal] = Field(None, description="Regular price")
    sale_price: Optional[Decimal] = Field(None, description="Sale price")
    stock_quantity: Optional[int] = Field(None, description="Stock quantity")
    stock_status: Optional[str] = Field("instock", description="Stock status")
    manage_stock: bool = Field(False, description="Whether stock is managed")
    weight: Optional[str] = Field(None, description="Weight")
    dimensions: Optional[WCProductDimensions] = None
    image: Optional[WPImageRead] = None
    attributes: List[dict] = Field(default_factory=list, description="Variation attribute values")
    date_created: Optional[datetime] = None
    date_modified: Optional[datetime] = None
    description: Optional[str] = Field(None, description="Variation description")
    status: Optional[str] = Field("publish", description="Variation status")

    class Config:
        from_attributes = True


class WCProductVariationCreate(BaseModel):
    """Schema for creating a product variation"""
    sku: Optional[str] = None
    regular_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    stock_quantity: Optional[int] = None
    stock_status: Optional[str] = "instock"
    manage_stock: bool = False
    weight: Optional[str] = None
    length: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = "publish"
    attributes: List[dict] = Field(default_factory=list, description="e.g. [{'name': 'Color', 'option': 'Red'}]")


class WCProductVariationUpdate(BaseModel):
    """Schema for updating a product variation"""
    sku: Optional[str] = None
    regular_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    stock_quantity: Optional[int] = None
    stock_status: Optional[str] = None
    manage_stock: Optional[bool] = None
    weight: Optional[str] = None
    length: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    attributes: Optional[List[dict]] = None


class WCProductCategoryCreate(BaseModel):
    """Schema for creating a product category"""
    name: str = Field(..., description="Category name")
    slug: Optional[str] = Field(None, description="Category slug (auto-generated if omitted)")
    parent: Optional[int] = Field(0, description="Parent category term ID")
    description: Optional[str] = Field("", description="Category description")


class WCProductCategoryUpdate(BaseModel):
    """Schema for updating a product category"""
    name: Optional[str] = None
    slug: Optional[str] = None
    parent: Optional[int] = None
    description: Optional[str] = None


# ============== Product Schemas ==============

class WCProductBase(BaseModel):
    """Base product schema"""
    name: str = Field(..., description="Product name")
    type: Optional[str] = Field("simple", description="Product type: simple, variable, grouped, external")
    sku: Optional[str] = Field(None, max_length=100, description="Stock keeping unit")
    price: Optional[Decimal] = Field(None, description="Product price")
    regular_price: Optional[Decimal] = Field(None, description="Regular price")
    sale_price: Optional[Decimal] = Field(None, description="Sale price")
    description: Optional[str] = Field(None, description="Product description")
    short_description: Optional[str] = Field(None, description="Short description")
    status: Optional[str] = Field("publish", description="Product status")
    manage_stock: Optional[bool] = Field(False, description="Whether stock is managed at product level")
    stock_quantity: Optional[int] = Field(None, description="Stock quantity")
    stock_status: Optional[str] = Field("instock", description="Stock status")
    weight: Optional[str] = Field(None, description="Product weight")
    virtual: Optional[bool] = Field(False, description="Is virtual product")
    downloadable: Optional[bool] = Field(False, description="Is downloadable")
    seller_payment_link: Optional[str] = Field(None, description="External seller payment link")
    whop_payment_link: Optional[str] = Field(None, description="Whop payment link")
    signal_link: Optional[str] = Field(None, description="Signal access link")
    telegram_link: Optional[str] = Field(None, description="Telegram group link")
    vip_group: Optional[str] = Field(None, description="VIP group name/link")


class WCProductCreate(WCProductBase):
    """Schema for creating a new product"""
    categories: Optional[List[int]] = Field(None, description="Category term IDs to assign")
    tags: Optional[List[int]] = Field(None, description="Tag term IDs to assign")
    attributes: Optional[List[dict]] = Field(None, description="Product attributes")
    dimensions: Optional[WCProductDimensions] = None
    addons: Optional[List[WCProductAddonField]] = Field(None, description="Custom input fields (e.g. Telegram Username)")


class WCProductUpdate(BaseModel):
    """Schema for updating a product"""
    name: Optional[str] = None
    type: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[Decimal] = None
    regular_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    status: Optional[str] = None
    manage_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    stock_status: Optional[str] = None
    weight: Optional[str] = None
    virtual: Optional[bool] = None
    downloadable: Optional[bool] = None
    categories: Optional[List[int]] = None
    tags: Optional[List[int]] = None
    attributes: Optional[List[dict]] = None
    dimensions: Optional[WCProductDimensions] = None
    seller_payment_link: Optional[str] = None
    whop_payment_link: Optional[str] = None
    signal_link: Optional[str] = None
    telegram_link: Optional[str] = None
    vip_group: Optional[str] = None
    addons: Optional[List[WCProductAddonField]] = None


class WCProductRead(WCProductBase):
    """Schema for reading a product"""
    id: int
    slug: str
    date_created: Optional[datetime] = None
    date_modified: Optional[datetime] = None
    dimensions: Optional[WCProductDimensions] = None
    average_rating: Optional[Decimal] = None
    rating_count: Optional[int] = 0
    total_sales: Optional[int] = 0
    featured_image: Optional[WPImageRead] = None
    gallery_images: List[dict] = Field(default_factory=list, description="Gallery images")
    categories: List[WCProductCategoryRead] = Field(default_factory=list)
    tags: List[WCProductTagRead] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WCProductFullRead(WCProductRead):
    """Extended product with attributes, variations, and related products"""
    attributes: List[WCProductAttributeRead] = Field(default_factory=list)
    variations: List[WCProductVariationRead] = Field(default_factory=list)
    addons: List[WCProductAddonField] = Field(default_factory=list, description="Custom input fields")
    related_ids: List[int] = Field(default_factory=list, description="Related product IDs")
    upsell_ids: List[int] = Field(default_factory=list, description="Upsell product IDs")
    cross_sell_ids: List[int] = Field(default_factory=list, description="Cross-sell product IDs")

    class Config:
        from_attributes = True


class WCProductMeta(BaseModel):
    """Product meta lookup schema"""
    product_id: int
    sku: Optional[str] = None
    virtual: bool = False
    downloadable: bool = False
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    onsale: bool = False
    stock_quantity: Optional[float] = None
    stock_status: Optional[str] = "instock"
    rating_count: int = 0
    average_rating: Optional[Decimal] = None
    total_sales: int = 0
    tax_status: Optional[str] = "taxable"
    tax_class: Optional[str] = ""

    class Config:
        from_attributes = True


# ============== Order Schemas ==============

class WCOrderAddress(BaseModel):
    """Order address schema"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    address_1: Optional[str] = None
    address_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class WCOrderItemRead(BaseModel):
    """Order item read schema with metadata"""
    order_item_id: int
    order_item_name: str
    order_item_type: str
    order_id: int
    product_id: Optional[int] = None
    quantity: Optional[int] = None
    line_total: Optional[Decimal] = None
    meta: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True


class WCOrderItemCreate(BaseModel):
    """Schema for creating an order item"""
    product_id: int
    product_name: str
    quantity: int = 1
    price: Decimal = Decimal("0.00")


class WCOrderCreate(BaseModel):
    """Schema for creating a new order"""
    status: Optional[str] = "pending"
    currency: Optional[str] = "USD"
    total_amount: Optional[Decimal] = None
    customer_id: Optional[int] = None
    billing_email: Optional[str] = None
    payment_method: Optional[str] = None
    payment_method_title: Optional[str] = None
    customer_note: Optional[str] = None
    items: List[WCOrderItemCreate] = []


class WCOrderUpdate(BaseModel):
    """Schema for updating an existing order"""
    status: Optional[str] = None
    total_amount: Optional[Decimal] = None
    billing_email: Optional[str] = None
    customer_note: Optional[str] = None


class WCOrderRead(BaseModel):
    """Schema for reading an order (simplified)"""
    id: int
    status: Optional[str] = "pending"
    currency: Optional[str] = "USD"
    total_amount: Optional[Decimal] = None
    customer_id: Optional[int] = None
    billing_email: Optional[str] = None
    payment_method: Optional[str] = None
    payment_method_title: Optional[str] = None
    date_created_gmt: Optional[datetime] = None
    date_updated_gmt: Optional[datetime] = None

    class Config:
        from_attributes = True


class WCOrderFull(BaseModel):
    """Complete order schema with all details"""
    id: int
    status: Optional[str] = None
    currency: Optional[str] = None
    type: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    customer_id: Optional[int] = None
    billing_email: Optional[str] = None
    date_created_gmt: Optional[datetime] = None
    date_updated_gmt: Optional[datetime] = None
    parent_order_id: Optional[int] = None
    payment_method: Optional[str] = None
    payment_method_title: Optional[str] = None
    transaction_id: Optional[str] = None
    ip_address: Optional[str] = None
    customer_note: Optional[str] = None
    billing_address: Optional[WCOrderAddress] = None
    shipping_address: Optional[WCOrderAddress] = None
    items: List[WCOrderItemRead] = []

    class Config:
        from_attributes = True


class WCOrderStats(BaseModel):
    """Order statistics schema"""
    order_id: int
    parent_id: int = 0
    date_created: datetime
    num_items_sold: int = 0
    total_sales: float = 0
    tax_total: float = 0
    shipping_total: float = 0
    net_total: float = 0
    status: str = ""
    customer_id: int = 0
    date_paid: Optional[datetime] = None
    date_completed: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Customer Schemas ==============

class WCCustomerBase(BaseModel):
    """Base customer schema"""
    username: str = Field(..., max_length=60)
    first_name: str = Field("", max_length=255)
    last_name: str = Field("", max_length=255)
    email: Optional[str] = Field(None, max_length=100)
    country: str = Field("", max_length=2)
    state: str = Field("", max_length=100)
    city: str = Field("", max_length=100)
    postcode: str = Field("", max_length=20)


class WCCustomerCreate(WCCustomerBase):
    """Schema for creating a customer"""
    user_id: Optional[int] = None


class WCCustomerUpdate(BaseModel):
    """Schema for updating a customer"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None


class WCCustomerRead(WCCustomerBase):
    """Schema for reading a customer"""
    customer_id: int
    user_id: Optional[int] = None
    date_last_active: Optional[datetime] = None
    date_registered: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Shipping Schemas ==============

class WCShippingZoneRead(BaseModel):
    """Shipping zone schema"""
    zone_id: int
    zone_name: str = ""
    zone_order: int = 0

    class Config:
        from_attributes = True


class WCShippingZoneLocation(BaseModel):
    """Shipping zone location schema"""
    location_id: int
    zone_id: int
    location_code: str = ""
    location_type: str = ""

    class Config:
        from_attributes = True


class WCShippingZoneMethod(BaseModel):
    """Shipping zone method schema"""
    instance_id: int
    zone_id: int
    method_id: str = ""
    method_order: int = 0
    is_enabled: bool = True

    class Config:
        from_attributes = True


# ============== Tax Schemas ==============

class WCTaxRateRead(BaseModel):
    """Tax rate schema"""
    tax_rate_id: int
    tax_rate_country: str = ""
    tax_rate_state: str = ""
    tax_rate: str = ""
    tax_rate_name: str = ""
    tax_rate_priority: int = 0
    tax_rate_compound: int = 0
    tax_rate_shipping: int = 1
    tax_rate_order: int = 0
    tax_rate_class: str = ""

    class Config:
        from_attributes = True


# ============== Payment Token Schemas ==============

class WCPaymentTokenRead(BaseModel):
    """Payment token schema"""
    token_id: int
    gateway_id: str = ""
    token: str = ""
    user_id: int = 0
    type: str = ""
    is_default: bool = False

    class Config:
        from_attributes = True


# ============== Webhook Schemas ==============

class WCWebhookBase(BaseModel):
    """Base webhook schema"""
    name: str
    delivery_url: str
    topic: str = ""
    status: str = "active"


class WCWebhookCreate(WCWebhookBase):
    """Schema for creating webhook"""
    secret: str = ""


class WCWebhookRead(WCWebhookBase):
    """Schema for reading webhook"""
    webhook_id: int
    user_id: int
    date_created: Optional[datetime] = None
    date_modified: Optional[datetime] = None
    api_version: int = 0
    failure_count: int = 0
    pending_delivery: bool = False

    class Config:
        from_attributes = True


# ============== Coupon Lookup Schemas ==============

class WCOrderCouponLookup(BaseModel):
    """Order coupon lookup schema"""
    order_id: int
    coupon_id: int
    date_created: datetime
    discount_amount: float = 0

    class Config:
        from_attributes = True


# ============== Download Schemas ==============

class WCDownloadPermission(BaseModel):
    """Download permission schema"""
    permission_id: int
    download_id: str = ""
    product_id: int = 0
    order_id: int = 0
    order_key: str = ""
    user_email: str = ""
    user_id: Optional[int] = None
    downloads_remaining: Optional[str] = None
    access_granted: datetime
    access_expires: Optional[datetime] = None
    download_count: int = 0

    class Config:
        from_attributes = True


# ============== Coupon Schemas ==============

class WCCouponBase(BaseModel):
    """Base coupon schema"""
    code: str = Field(..., description="Coupon code")
    amount: Decimal = Field(Decimal("0.00"), description="Coupon amount")
    discount_type: str = Field("fixed_cart", description="Discount type: fixed_cart, percentage, fixed_product, percentage_product")
    description: Optional[str] = Field(None, description="Coupon description")
    date_expires: Optional[datetime] = Field(None, description="Expiry date")
    usage_limit: Optional[int] = Field(None, description="Overall usage limit")
    usage_limit_per_user: Optional[int] = Field(None, description="Usage limit per user")
    limit_usage_to_x_items: Optional[int] = Field(None, description="Limit usage to X items")
    free_shipping: bool = Field(False, description="Whether coupon grants free shipping")
    product_ids: List[int] = Field(default_factory=list, description="Products this coupon applies to")
    excluded_product_ids: List[int] = Field(default_factory=list, description="Products this coupon does NOT apply to")
    exclude_sale_items: bool = Field(False, description="Whether to exclude items on sale")
    minimum_amount: Decimal = Field(Decimal("0.00"), description="Minimum spend required")
    maximum_amount: Decimal = Field(Decimal("0.00"), description="Maximum spend allowed")
    individual_use: bool = Field(False, description="Whether coupon cannot be used with other coupons")


class WCCouponCreate(WCCouponBase):
    """Schema for creating a coupon"""
    pass


class WCCouponUpdate(BaseModel):
    """Schema for updating a coupon"""
    code: Optional[str] = None
    amount: Optional[Decimal] = None
    discount_type: Optional[str] = None
    description: Optional[str] = None
    date_expires: Optional[datetime] = None
    usage_limit: Optional[int] = None
    usage_limit_per_user: Optional[int] = None
    limit_usage_to_x_items: Optional[int] = None
    free_shipping: Optional[bool] = None
    product_ids: Optional[List[int]] = None
    excluded_product_ids: Optional[List[int]] = None
    exclude_sale_items: Optional[bool] = None
    minimum_amount: Optional[Decimal] = None
    maximum_amount: Optional[Decimal] = None
    individual_use: Optional[bool] = None


class WCCouponRead(WCCouponBase):
    """Schema for reading a coupon"""
    id: int
    usage_count: int = 0
    date_created: datetime
    date_modified: datetime

    class Config:
        from_attributes = True
