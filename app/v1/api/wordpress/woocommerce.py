from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db.session import get_session
from app.repo.wordpress.woocommerce import (
    WCOrderRepository, WCCustomerRepository, WCProductRepository,
    WCProductCategoryRepository, WCCouponRepository
)
from app.model.wordpress.woocommerce import WCOrder, WCCustomerLookup
from app.schema.wordpress.woocommerce import (
    WCProductRead, WCProductCreate, WCProductUpdate, WCProductMeta,
    WCProductAttributeRead, WCProductFullRead, WCProductVariationRead,
    WCProductVariationCreate, WCProductVariationUpdate,
    WCProductCategoryRead, WCProductCategoryCreate,
    WCProductCategoryUpdate, WCProductTagRead,
    WCOrderFull, WCCustomerRead, WCOrderCreate, WCOrderUpdate,
    WCProductAddonField, WCProductAddonsCreate, WCProductAddonsRead,
    WCCouponRead, WCCouponCreate, WCCouponUpdate
)
from app.service.email import send_order_confirmation_email, send_order_status_update_email
from app.dependencies.auth import get_current_user, get_current_admin
from app.model.user import User

router = APIRouter()


# ============== Orders ==============

@router.get("/orders", response_model=List[WCOrder])
async def get_orders(
    skip: int = 0,
    limit: int = 10,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get list of WooCommerce orders"""
    repo = WCOrderRepository(session)
    return await repo.get_orders(limit=limit, offset=skip)


@router.get("/orders/{order_id}", response_model=WCOrderFull)
async def get_order(
    order_id: int,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a WooCommerce order by ID (with full details)"""
    repo = WCOrderRepository(session)
    order = await repo.get_order_full(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/orders", response_model=WCOrderFull)
async def create_order(
    order_data: WCOrderCreate,
    session: Session = Depends(get_session)
):
    """Create a new WooCommerce order"""
    repo = WCOrderRepository(session)
    order = await repo.create_order(order_data)

    # Send confirmation email
    if order.billing_email:
        await send_order_confirmation_email(
            email=order.billing_email,
            order_id=order.id,
            total=float(order.total_amount) if order.total_amount else 0.0,
            currency=order.currency or "USD",
            items=["Order Items"]  # Placeholder
        )

    return await repo.get_order_full(order.id)


@router.put("/orders/{order_id}", response_model=WCOrderFull)
async def update_order(
    order_id: int,
    order_data: WCOrderUpdate,
    session: Session = Depends(get_session)
):
    """Update an existing WooCommerce order"""
    repo = WCOrderRepository(session)
    order = await repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status
    updated_order = await repo.update_order(order, order_data)

    # Send status update email if status changed
    if old_status != updated_order.status and updated_order.billing_email:
        await send_order_status_update_email(
            email=updated_order.billing_email,
            order_id=updated_order.id,
            new_status=updated_order.status
        )

    return await repo.get_order_full(updated_order.id)


# ============== Customers ==============

@router.get("/customers", response_model=List[WCCustomerLookup])
async def get_customers(
    skip: int = 0,
    limit: int = 10,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get list of WooCommerce customers"""
    repo = WCCustomerRepository(session)
    return await repo.get_customers(limit=limit, offset=skip)


@router.get("/customers/{customer_id}", response_model=WCCustomerLookup)
async def get_customer(
    customer_id: int,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a WooCommerce customer by ID"""
    repo = WCCustomerRepository(session)
    customer = await repo.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


# ============== Products ==============

@router.get("/products", response_model=List[WCProductRead])
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: str = "publish",
    category: Optional[int] = None,
    tag: Optional[int] = None,
    search: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    on_sale: bool = False,
    featured: bool = False,
    session: Session = Depends(get_session)
):
    """Get list of WooCommerce products with filtering"""
    repo = WCProductRepository(session)
    return await repo.get_products(
        limit=limit,
        offset=skip,
        status=status,
        category_id=category,
        tag_id=tag,
        search=search,
        min_price=min_price,
        max_price=max_price,
        on_sale=on_sale,
        featured=featured
    )


@router.get("/products/search", response_model=List[WCProductRead])
async def search_products(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session)
):
    """Search for products by name or content"""
    repo = WCProductRepository(session)
    return await repo.get_products(limit=limit, search=q)


@router.get("/products/slug/{slug}", response_model=WCProductRead)
async def get_product_by_slug(
    slug: str,
    session: Session = Depends(get_session)
):
    """Get a WooCommerce product by slug"""
    repo = WCProductRepository(session)
    product = await repo.get_product_by_slug(slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/{product_id}/full", response_model=WCProductFullRead)
async def get_product_full(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Get full product details including variations and attributes"""
    repo = WCProductRepository(session)
    product = await repo.get_product_full(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/{product_id}", response_model=WCProductRead)
async def get_product(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Get a WooCommerce product by ID"""
    repo = WCProductRepository(session)
    product = await repo.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/{product_id}/meta", response_model=WCProductMeta)
async def get_product_meta(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Get product meta/lookup data"""
    repo = WCProductRepository(session)
    meta = await repo.get_product_meta(product_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Product meta not found")
    return meta


@router.post("/products", response_model=WCProductRead)
async def create_product(
    product_data: WCProductCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a new WooCommerce product"""
    repo = WCProductRepository(session)
    return await repo.create_product(product_data)


@router.put("/products/{product_id}", response_model=WCProductRead)
async def update_product(
    product_id: int,
    product_data: WCProductUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update an existing WooCommerce product"""
    repo = WCProductRepository(session)
    product = await repo.update_product(product_id, product_data)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    force: bool = False,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete (trash) or permanently delete a WooCommerce product"""
    repo = WCProductRepository(session)
    success = await repo.delete_product(product_id, force=force)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}


@router.post("/products/{product_id}/terms", tags=["WooCommerce Products"])
async def assign_product_terms(
    product_id: int,
    term_ids: List[int],
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Assign terms (categories/tags) to a product"""
    repo = WPTermRepository(session)
    await repo.assign_terms_to_post(product_id, term_ids)
    return {"message": "Terms assigned successfully"}


@router.delete("/products/{product_id}/terms", tags=["WooCommerce Products"])
async def remove_product_terms(
    product_id: int,
    term_ids: List[int],
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Remove terms (categories/tags) from a product"""
    repo = WPTermRepository(session)
    await repo.remove_terms_from_post(product_id, term_ids)
    return {"message": "Terms removed successfully"}


# ============== Product Variations ==============

@router.get("/products/{product_id}/variations", response_model=List[WCProductVariationRead])
async def get_product_variations(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Get variations for a product"""
    repo = WCProductRepository(session)
    return await repo.get_product_variations(product_id)


@router.post("/products/{product_id}/variations", response_model=WCProductVariationRead)
async def create_product_variation(
    product_id: int,
    variation_data: WCProductVariationCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a new variation for a product"""
    repo = WCProductRepository(session)
    variation = await repo.create_variation(product_id, variation_data)
    if not variation:
        raise HTTPException(status_code=400, detail="Could not create variation")
    return variation


@router.put("/products/{product_id}/variations/{variation_id}", response_model=WCProductVariationRead)
async def update_product_variation(
    product_id: int,
    variation_id: int,
    variation_data: WCProductVariationUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update an existing variation"""
    repo = WCProductRepository(session)
    variation = await repo.update_variation(variation_id, variation_data)
    if not variation:
        raise HTTPException(status_code=404, detail="Variation not found")
    return variation


@router.delete("/products/{product_id}/variations/{variation_id}")
async def delete_product_variation(
    product_id: int,
    variation_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete a product variation"""
    repo = WCProductRepository(session)
    success = await repo.delete_variation(variation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Variation not found")
    return {"message": "Variation deleted successfully"}


@router.get("/products/{product_id}/attributes", response_model=List[WCProductAttributeRead])
async def get_product_attributes(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Get attributes for a product"""
    repo = WCProductRepository(session)
    return await repo.get_product_attributes(product_id)


# ============== Product Addons (Custom Input Fields) ==============

@router.get("/products/{product_id}/addons", response_model=WCProductAddonsRead, tags=["WooCommerce Products"])
async def get_product_addons(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Get custom input fields for a product (e.g. Telegram Username)"""
    repo = WCProductRepository(session)
    addons = await repo.get_product_addons(product_id)
    return WCProductAddonsRead(product_id=product_id, addons=addons)


@router.put("/products/{product_id}/addons", response_model=WCProductAddonsRead, tags=["WooCommerce Products"])
async def set_product_addons(
    product_id: int,
    addons_data: WCProductAddonsCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Set/replace custom input fields for a product (admin only)"""
    repo = WCProductRepository(session)
    await repo.set_product_addons(product_id, addons_data.addons)
    return WCProductAddonsRead(product_id=product_id, addons=addons_data.addons)


@router.delete("/products/{product_id}/addons", tags=["WooCommerce Products"])
async def delete_product_addons(
    product_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Remove all custom input fields from a product (admin only)"""
    repo = WCProductRepository(session)
    success = await repo.delete_product_addons(product_id)
    if not success:
        raise HTTPException(status_code=404, detail="No addons found for this product")
    return {"message": "Product addons removed successfully"}


# ============== Product Categories ==============

@router.get("/products/categories", response_model=List[WCProductCategoryRead])
async def get_product_categories(
    parent: int = 0,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session)
):
    """List all product categories"""
    repo = WCProductCategoryRepository(session)
    return await repo.get_categories(parent=parent, limit=limit, offset=skip)


@router.get("/products/categories/{category_id}", response_model=WCProductCategoryRead)
async def get_product_category(
    category_id: int,
    session: Session = Depends(get_session)
):
    """Get a single product category"""
    repo = WCProductCategoryRepository(session)
    category = await repo.get_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/products/categories", response_model=WCProductCategoryRead)
async def create_product_category(
    category_data: WCProductCategoryCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a new product category"""
    repo = WCProductCategoryRepository(session)
    return await repo.create_category(category_data)


@router.put("/products/categories/{category_id}", response_model=WCProductCategoryRead)
async def update_product_category(
    category_id: int,
    category_data: WCProductCategoryUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update a product category"""
    repo = WCProductCategoryRepository(session)
    category = await repo.update_category(category_id, category_data)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.delete("/products/categories/{category_id}")
async def delete_product_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete a product category"""
    repo = WCProductCategoryRepository(session)
    success = await repo.delete_category(category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted successfully"}


@router.get("/products/tags", response_model=List[WCProductTagRead])
async def get_product_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session)
):
    """List all product tags"""
    repo = WCProductRepository(session)
    return await repo.list_all_tags(limit=limit, offset=skip)


# ============== Coupons ==============

@router.get("/coupons", response_model=List[WCCouponRead], tags=["WooCommerce Coupons"])
async def get_coupons(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """List all coupons (admin only)"""
    repo = WCCouponRepository(session)
    return await repo.get_coupons(limit=limit, offset=skip, search=search)


@router.get("/coupons/{coupon_id}", response_model=WCCouponRead, tags=["WooCommerce Coupons"])
async def get_coupon(
    coupon_id: int,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a single coupon by ID (admin only)"""
    repo = WCCouponRepository(session)
    coupon = await repo.get_coupon(coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


@router.post("/coupons", response_model=WCCouponRead, tags=["WooCommerce Coupons"])
async def create_coupon(
    data: WCCouponCreate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Create a new coupon (admin only)"""
    repo = WCCouponRepository(session)
    # Check if code already exists
    existing = await repo.get_coupon_by_code(data.code)
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists")

    return await repo.create_coupon(data)


@router.put("/coupons/{coupon_id}", response_model=WCCouponRead, tags=["WooCommerce Coupons"])
async def update_coupon(
    coupon_id: int,
    data: WCCouponUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update an existing coupon (admin only)"""
    repo = WCCouponRepository(session)
    coupon = await repo.update_coupon(coupon_id, data)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


@router.delete("/coupons/{coupon_id}", tags=["WooCommerce Coupons"])
async def delete_coupon(
    coupon_id: int,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete a coupon (admin only)"""
    repo = WCCouponRepository(session)
    success = await repo.delete_coupon(coupon_id)
    if not success:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return {"message": "Coupon deleted successfully"}


# ============== Shopping Cart ==============

from app.repo.wordpress.woocommerce import WCCartRepository, WCProductReviewRepository
from app.repo.wordpress.posts import WPTermRepository
from app.schema.wordpress.wc_cart import (
    WCCart, WCAddToCartRequest, WCUpdateCartItemRequest,
    WCApplyCouponRequest, WCCheckoutRequest, WCCheckoutResponse,
    WCProductReviewCreate, WCProductReviewRead, WCUserOrderSummary
)


@router.get("/cart", response_model=dict, tags=["WooCommerce Cart"])
async def get_cart(
    payment_method: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get the current user's shopping cart"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    return await repo.get_cart(user_id, payment_method=payment_method)


@router.post("/cart/add", response_model=dict, tags=["WooCommerce Cart"])
async def add_to_cart(
    request: WCAddToCartRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Add a product to the cart"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    try:
        await repo.add_to_cart(
            user_id=user_id,
            product_id=request.product_id,
            quantity=request.quantity,
            variation_id=request.variation_id,
            custom_fields=request.custom_fields
        )
        return await repo.get_cart(user_id) # Default get_cart
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/cart/update", response_model=dict, tags=["WooCommerce Cart"])
async def update_cart_item(
    request: WCUpdateCartItemRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update cart item quantity"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    await repo.update_cart_item(
        user_id=user_id,
        product_id=request.product_id,
        quantity=request.quantity,
        variation_id=request.variation_id
    )
    return await repo.get_cart(user_id)


@router.delete("/cart/remove/{product_id}", response_model=dict, tags=["WooCommerce Cart"])
async def remove_from_cart(
    product_id: int,
    variation_id: int = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Remove an item from the cart"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    await repo.remove_from_cart(
        user_id=user_id,
        product_id=product_id,
        variation_id=variation_id
    )
    return await repo.get_cart(user_id)


@router.delete("/cart/clear", response_model=dict, tags=["WooCommerce Cart"])
async def clear_cart(
    payment_method: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Clear all items from the cart"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    return await repo.clear_cart(user_id, payment_method=payment_method)


@router.post("/cart/coupon", response_model=dict, tags=["WooCommerce Cart"])
async def apply_coupon(
    request: WCApplyCouponRequest,
    payment_method: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Apply a coupon code to the cart"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    return await repo.apply_coupon(user_id, request.coupon_code, payment_method=payment_method)


@router.delete("/cart/coupon/{coupon_code}", response_model=dict, tags=["WooCommerce Cart"])
async def remove_coupon(
    coupon_code: str,
    payment_method: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Remove a coupon from the cart"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    return await repo.remove_coupon(user_id, coupon_code, payment_method=payment_method)


# ============== Checkout ==============

@router.post("/checkout", response_model=WCCheckoutResponse, tags=["WooCommerce Checkout"])
async def checkout(
    request: WCCheckoutRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create an order from the current cart"""
    user_id = current_user.ID
    repo = WCCartRepository(session)

    billing = request.billing_address.model_dump()
    shipping = None
    if not request.use_same_for_shipping and request.shipping_address:
        shipping = request.shipping_address.model_dump()

    try:
        result = await repo.checkout(
            user_id=user_id,
            billing_address=billing,
            shipping_address=shipping,
            payment_method=request.payment_method,
            payment_method_title=request.payment_method_title or request.payment_method,
            customer_note=request.customer_note,
            custom_fields=request.custom_fields
        )
        return WCCheckoutResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== User Orders ==============

@router.get("/my-orders", response_model=List[WCOrder], tags=["WooCommerce User"])
async def get_my_orders(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get the current user's orders"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    return await repo.get_user_orders(user_id, limit=limit, offset=skip)


@router.get("/my-orders/summary", response_model=WCUserOrderSummary, tags=["WooCommerce User"])
async def get_my_order_summary(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get order summary for the current user"""
    user_id = current_user.ID
    repo = WCCartRepository(session)
    return await repo.get_user_order_summary(user_id)


@router.get("/my-orders/digital-assets", response_model=List[WCProductRead], tags=["WooCommerce User"])
async def get_my_digital_assets(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get all products with access links from the current user's completed orders"""
    user_id = current_user.ID
    order_repo = WCOrderRepository(session)
    return await order_repo.get_user_digital_assets(user_id)


@router.get("/my-orders/{order_id}", response_model=WCOrderFull, tags=["WooCommerce User"])
async def get_my_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific order for the current user"""
    user_id = current_user.ID
    order_repo = WCOrderRepository(session)
    order = await order_repo.get_order_full(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.customer_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return order


# ============== Product Reviews ==============

@router.get("/products/{product_id}/reviews", response_model=List[dict], tags=["WooCommerce Reviews"])
async def get_product_reviews(
    product_id: int,
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session)
):
    """Get reviews for a product"""
    repo = WCProductReviewRepository(session)
    return await repo.get_product_reviews(product_id, limit=limit, offset=skip)


@router.post("/products/{product_id}/reviews", response_model=dict, tags=["WooCommerce Reviews"])
async def create_product_review(
    product_id: int,
    review_data: WCProductReviewCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Submit a review for a product"""
    from fastapi import Request

    user_id = current_user.ID
    reviewer_name = current_user.display_name or (current_user.user_email.split("@")[0] if current_user.user_email else "Guest")
    reviewer_email = current_user.user_email

    repo = WCProductReviewRepository(session)
    try:
        return await repo.create_review(
            product_id=product_id,
            user_id=user_id,
            reviewer_name=reviewer_name,
            reviewer_email=reviewer_email,
            review=review_data.review,
            rating=review_data.rating
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== Product Images ==============

from pydantic import BaseModel


class ProductImageRequest(BaseModel):
    attachment_id: int


class ProductGalleryRequest(BaseModel):
    image_ids: List[int]


@router.get("/products/{product_id}/images", tags=["WooCommerce Products"])
async def get_product_images(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Get product featured image and gallery images"""
    repo = WCProductRepository(session)
    return await repo.get_product_images(product_id)


@router.put("/products/{product_id}/featured-image", tags=["WooCommerce Products"])
async def set_product_featured_image(
    product_id: int,
    image_data: ProductImageRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Set the featured/main image for a product"""
    repo = WCProductRepository(session)
    success = await repo.set_product_featured_image(product_id, image_data.attachment_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set featured image. Check product and attachment IDs.")
    return {"message": "Product featured image set successfully"}


@router.put("/products/{product_id}/gallery", tags=["WooCommerce Products"])
async def set_product_gallery(
    product_id: int,
    request: ProductGalleryRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Set product gallery images (replaces existing gallery)"""
    repo = WCProductRepository(session)
    success = await repo.set_product_gallery(product_id, request.image_ids)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product gallery updated successfully"}


@router.post("/products/{product_id}/gallery", tags=["WooCommerce Products"])
async def add_product_gallery_image(
    product_id: int,
    image_data: ProductImageRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Add a single image to the product gallery"""
    repo = WCProductRepository(session)
    success = await repo.add_product_gallery_image(product_id, image_data.attachment_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add image to gallery")
    return {"message": "Image added to product gallery"}


@router.delete("/products/{product_id}/gallery/{attachment_id}", tags=["WooCommerce Products"])
async def remove_product_gallery_image(
    product_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Remove a single image from the product gallery"""
    repo = WCProductRepository(session)
    success = await repo.remove_product_gallery_image(product_id, attachment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Image not found in gallery")
    return {"message": "Image removed from product gallery"}
