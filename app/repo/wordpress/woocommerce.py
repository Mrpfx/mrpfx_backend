from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import or_, func, and_
from app.model.wordpress.woocommerce import (
    WCOrder, WCOrderMeta, WCOrderAddress, WCOrderItem, WCOrderItemMeta,
    WCCustomerLookup, WCProductMetaLookup, WCProductAttributeLookup,
    WCAttributeTaxonomy
)
from app.model.wordpress.core import (
    WPPost, WPPostMeta, WPTerm, WPTermTaxonomy, WPTermRelationship
)
from app.schema.wordpress.woocommerce import (
    WCProductCreate, WCProductUpdate, WCProductRead, WCProductMeta,
    WCProductFullRead, WCProductCategoryRead, WCProductTagRead,
    WCProductAttributeRead, WCProductDimensions, WCProductVariationRead,
    WCProductVariationCreate, WCProductVariationUpdate,
    WCProductCategoryCreate, WCProductCategoryUpdate,
    WCOrderFull, WCOrderAddress as WCOrderAddressSchema, WCOrderItemRead,
    WCOrderCreate, WCOrderUpdate,
    WCProductAddonField, WCProductAddonsRead,
    WCCouponRead, WCCouponCreate, WCCouponUpdate
)
from fastapi import HTTPException


class WCOrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_order(self, order_id: int) -> Optional[WCOrder]:
        return await self.session.get(WCOrder, order_id)

    async def get_orders(self, limit: int = 10, offset: int = 0) -> List[WCOrder]:
        statement = select(WCOrder).limit(limit).offset(offset)
        result = await self.session.exec(statement)
        return result.all()

    async def get_customer_orders(self, customer_id: int) -> List[WCOrder]:
        statement = select(WCOrder).where(WCOrder.customer_id == customer_id)
        result = await self.session.exec(statement)
        return result.all()

    async def get_user_digital_assets(self, user_id: int) -> List[WCProductRead]:
        """Get all products with access links from a user's completed orders"""
        # 1. Get all completed orders for the user
        stmt_orders = select(WCOrder.id).where(
            WCOrder.customer_id == user_id,
            WCOrder.status == "completed"
        )
        result_orders = await self.session.exec(stmt_orders)
        order_ids = result_orders.all()
        if not order_ids:
            return []

        # 2. Get all order items for those orders to extract product IDs
        stmt_assets = (
            select(WCOrderItemMeta.meta_value)
            .join(WCOrderItem, WCOrderItem.order_item_id == WCOrderItemMeta.order_item_id)
            .where(
                WCOrderItem.order_id.in_(order_ids),
                WCOrderItemMeta.meta_key == "_product_id"
            )
            .distinct()
        )
        result_assets = await self.session.exec(stmt_assets)
        product_ids = [int(val) for val in result_assets.all() if val and str(val).isdigit()]

        if not product_ids:
            return []

        # 3. Fetch product details and filter for those with access links
        from app.repo.wordpress.woocommerce import WCProductRepository
        product_repo = WCProductRepository(self.session)
        digital_assets = []
        for pid in product_ids:
            p = await product_repo.get_product(pid)
            if p and (p.telegram_link or p.signal_link or p.vip_group):
                digital_assets.append(p)

        return digital_assets

    async def get_order_full(self, order_id: int) -> Optional[WCOrderFull]:
        """Get order with all related data (addresses, items)"""
        order = await self.session.get(WCOrder, order_id)
        if not order:
            return None

        # Get addresses
        addr_stmt = select(WCOrderAddress).where(WCOrderAddress.order_id == order_id)
        addr_result = await self.session.exec(addr_stmt)
        addresses = addr_result.all()

        billing_address = None
        shipping_address = None
        for addr in addresses:
            addr_schema = WCOrderAddressSchema(
                first_name=addr.first_name,
                last_name=addr.last_name,
                company=addr.company,
                address_1=addr.address_1,
                address_2=addr.address_2,
                city=addr.city,
                state=addr.state,
                postcode=addr.postcode,
                country=addr.country,
                email=addr.email,
                phone=addr.phone
            )
            if addr.address_type == "billing":
                billing_address = addr_schema
            elif addr.address_type == "shipping":
                shipping_address = addr_schema

        # Get items
        items_stmt = select(WCOrderItem).where(WCOrderItem.order_id == order_id)
        items_result = await self.session.exec(items_stmt)
        db_items = items_result.all()

        items = []
        for item in db_items:
            # Get meta for this item
            meta_stmt = select(WCOrderItemMeta).where(WCOrderItemMeta.order_item_id == item.order_item_id)
            meta_result = await self.session.exec(meta_stmt)
            meta_data = {m.meta_key: m.meta_value for m in meta_result.all()}

            items.append(
                WCOrderItemRead(
                    order_item_id=item.order_item_id,
                    order_item_name=item.order_item_name,
                    order_item_type=item.order_item_type,
                    order_id=item.order_id,
                    product_id=int(meta_data.get("_product_id", 0)) if meta_data.get("_product_id") else None,
                    quantity=int(meta_data.get("_qty", 0)) if meta_data.get("_qty") else None,
                    line_total=Decimal(meta_data.get("_line_total", "0.00")) if meta_data.get("_line_total") else None,
                    meta={k: v for k, v in meta_data.items() if not k.startswith("_") or k == "telegram_username"} # Include custom fields
                )
            )

        return WCOrderFull(
            id=order.id,
            status=order.status,
            currency=order.currency,
            type=order.type,
            tax_amount=order.tax_amount,
            total_amount=order.total_amount,
            customer_id=order.customer_id,
            billing_email=order.billing_email,
            date_created_gmt=order.date_created_gmt,
            date_updated_gmt=order.date_updated_gmt,
            parent_order_id=order.parent_order_id,
            payment_method=order.payment_method,
            payment_method_title=order.payment_method_title,
            transaction_id=order.transaction_id,
            ip_address=order.ip_address,
            customer_note=order.customer_note,
            billing_address=billing_address,
            shipping_address=shipping_address,
            items=items
        )


    async def get_orders_by_status(self, status: str, limit: int = 10, offset: int = 0) -> List[WCOrder]:
        statement = select(WCOrder).where(WCOrder.status == status).limit(limit).offset(offset)
        result = await self.session.exec(statement)
        return result.all()

    async def create_order(self, order_data: WCOrderCreate) -> WCOrder:
        # 1. Create Order (exclude items as it's not in the DB model)
        data = order_data.model_dump(exclude={"items"})
        db_order = WCOrder(**data)

        if not db_order.date_created_gmt:
            db_order.date_created_gmt = datetime.now()
        if not db_order.date_updated_gmt:
            db_order.date_updated_gmt = datetime.now()

        db_order.type = "shop_order"

        self.session.add(db_order)
        await self.session.flush() # Get the ID without committing yet

        order_id = db_order.id

        # 2. Add Items
        for item in order_data.items:
            order_item = WCOrderItem(
                order_id=order_id,
                order_item_name=item.product_name,
                order_item_type="line_item"
            )
            self.session.add(order_item)
            await self.session.flush() # Get order_item_id

            item_id = order_item.order_item_id

            # Add Item Meta (Association Glue)
            item_meta = [
                ("_product_id", str(item.product_id)),
                ("_qty", str(item.quantity)),
                ("_line_total", str(item.price * item.quantity)),
                ("_line_subtotal", str(item.price * item.quantity))
            ]
            for meta_key, meta_value in item_meta:
                meta = WCOrderItemMeta(
                    order_item_id=item_id,
                    meta_key=meta_key,
                    meta_value=meta_value
                )
                self.session.add(meta)

        await self.session.commit()
        await self.session.refresh(db_order)
        return db_order

    async def update_order(self, order: WCOrder, order_data: WCOrderUpdate) -> WCOrder:
        update_data = order_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(order, key, value)

        order.date_updated_gmt = datetime.now()
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order


class WCProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_product(self, product_id: int) -> Optional[WCProductRead]:
        """Get a product by ID with full metadata"""
        statement = select(WPPost).where(
            WPPost.ID == product_id,
            WPPost.post_type.in_(["product", "signal", "trading_tool", "forex_book"])
        )
        result = await self.session.exec(statement)
        post = result.first()

        if not post:
            return None

        # Get product meta lookup
        meta_stmt = select(WCProductMetaLookup).where(
            WCProductMetaLookup.product_id == product_id
        )
        meta_result = await self.session.exec(meta_stmt)
        meta = meta_result.first()

        # Get values from post meta
        meta_keys = [
            "_price", "_regular_price", "_sale_price", "_sku",
            "_weight", "_length", "_width", "_height", "_manage_stock",
            "_seller_payment_link", "_whop_payment_link",
            "_selar_url", "selar_url", "_whop_url", "whop_url",
            "_signal_link", "signal_link", "_telegram_link", "telegram_link", "_vip_group", "vip_group",
            # Dynamic content meta
            "_signal_price", "_tool_price", "_book_price",
            "_signal_category", "_tool_category", "_book_is_free"
        ]
        price_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key.in_(meta_keys)
        )
        meta_rows = await self.session.exec(price_stmt)
        post_meta = {m.meta_key: m.meta_value for m in meta_rows.all()}

        # Get categories and tags
        categories = await self.get_product_categories(product_id)
        tags = await self.get_product_tags(product_id)

        # Get type
        product_type = await self.get_product_type(product_id)

        product_read = WCProductRead(
            id=post.ID,
            name=post.post_title,
            slug=post.post_name,
            type=product_type,
            description=post.post_content,
            short_description=post.post_excerpt,
            status=post.post_status,
            sku=post_meta.get("_sku", meta.sku if meta else ""),
            price=Decimal(post_meta.get("_sale_price") or post_meta.get("_price") or post_meta.get("_signal_price") or post_meta.get("_tool_price") or post_meta.get("_book_price") or "0"),
            regular_price=Decimal(post_meta.get("_regular_price") or post_meta.get("_price") or "0"),
            sale_price=Decimal(post_meta.get("_sale_price") or "0") if post_meta.get("_sale_price") else None,
            manage_stock=post_meta.get("_manage_stock") == "yes",
            stock_quantity=int(meta.stock_quantity) if meta and meta.stock_quantity is not None else None,
            stock_status=meta.stock_status if meta else "instock",
            weight=post_meta.get("_weight"),
            dimensions=WCProductDimensions(
                length=post_meta.get("_length"),
                width=post_meta.get("_width"),
                height=post_meta.get("_height")
            ),
            virtual=meta.virtual if meta else True, # Default to True for dynamic content
            downloadable=meta.downloadable if meta else True,
            date_created=post.post_date,
            date_modified=post.post_modified,
            average_rating=meta.average_rating if meta else None,
            rating_count=meta.rating_count if meta else 0,
            total_sales=meta.total_sales if meta else 0,
            categories=categories,
            tags=tags,
            seller_payment_link=post_meta.get("_seller_payment_link") or post_meta.get("selar_url") or post_meta.get("_selar_url"),
            whop_payment_link=post_meta.get("_whop_payment_link") or post_meta.get("whop_url") or post_meta.get("_whop_url"),
            signal_link=post_meta.get("_signal_link") or post_meta.get("signal_link"),
            telegram_link=post_meta.get("_telegram_link") or post_meta.get("telegram_link"),
            vip_group=post_meta.get("_vip_group") or post_meta.get("vip_group")
        )

        # Attach images
        images = await self.get_product_images(product_id)
        if images.get("featured_image"):
            from app.schema.wordpress.post import WPImageRead
            product_read.featured_image = WPImageRead(**images["featured_image"])

        product_read.gallery_images = images.get("gallery_images", [])

        return product_read

    async def get_product_by_slug(self, slug: str) -> Optional[WCProductRead]:
        """Get product by slug with numeric ID fallback"""
        if slug.isdigit():
            return await self.get_product(int(slug))

        slug_variants = list(dict.fromkeys([
            slug,
            slug.replace(" ", "-"),
            slug.replace("-", " "),
            slug.lower().replace(" ", "-"),
            slug.lower().replace("-", " "),
        ]))

        statement = select(WPPost).where(
            or_(*[WPPost.post_name == v for v in slug_variants]),
            WPPost.post_type.in_(["product", "signal", "trading_tool", "forex_book"]),
            WPPost.post_status == "publish"
        )
        result = await self.session.exec(statement)
        post = result.first()
        if not post:
            return None
        return await self.get_product(post.ID)

    async def get_product_type(self, product_id: int) -> str:
        """Get product type from taxonomy, with fallback variation detection"""
        terms = await self._get_product_terms(product_id, "product_type")
        taxonomy_type = terms[0]["slug"] if terms else "simple"

        # If taxonomy says "simple", double-check for variation children
        # (some WP sites have mismatched taxonomy but real variations)
        if taxonomy_type == "simple":
            var_stmt = select(WPPost.ID).where(
                WPPost.post_parent == product_id,
                WPPost.post_type == "product_variation",
                WPPost.post_status == "publish"
            ).limit(1)
            result = await self.session.exec(var_stmt)
            if result.first():
                return "variable"

        return taxonomy_type

    async def get_product_categories(self, product_id: int) -> List[WCProductCategoryRead]:
        """Get product categories"""
        terms = await self._get_product_terms(product_id, "product_cat")
        return [WCProductCategoryRead(id=t["term_id"], **t) for t in terms]

    async def get_product_tags(self, product_id: int) -> List[WCProductTagRead]:
        """Get product tags"""
        terms = await self._get_product_terms(product_id, "product_tag")
        return [WCProductTagRead(id=t["term_id"], **t) for t in terms]

    async def _get_product_terms(self, product_id: int, taxonomy: str) -> List[dict]:
        """Internal helper to get terms for a product"""
        stmt = (
            select(WPTerm, WPTermTaxonomy)
            .join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id)
            .join(WPTermRelationship, WPTermTaxonomy.term_taxonomy_id == WPTermRelationship.term_taxonomy_id)
            .where(
                WPTermRelationship.object_id == product_id,
                WPTermTaxonomy.taxonomy == taxonomy
            )
        )
        result = await self.session.exec(stmt)
        return [
            {
                "term_id": term.term_id,
                "name": term.name,
                "slug": term.slug,
                "description": tax.description,
                "parent": tax.parent,
                "count": tax.count
            }
            for term, tax in result.all()
        ]

    async def get_product_attributes(self, product_id: int) -> List[WCProductAttributeRead]:
        """Get product attributes from meta"""
        import phpserialize

        stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key == "_product_attributes"
        )
        result = await self.session.exec(stmt)
        meta = result.first()
        if not meta or not meta.meta_value:
            return []

        try:
            # WooCommerce stores attributes as serialized PHP
            # The format is a bit complex, we'll try to parse it
            data = phpserialize.loads(meta.meta_value.encode(), decode_strings=True)
            attributes = []

            for attr_slug, attr_data in data.items():
                is_taxonomy = bool(attr_data.get('is_taxonomy', 0))
                name = attr_data.get('name', attr_slug)

                options = []
                if is_taxonomy:
                    # If it's a taxonomy, we need to fetch the terms
                    terms = await self._get_product_terms(product_id, name)
                    options = [t['name'] for t in terms]
                else:
                    # If it's a local attribute, options are pipe-separated string
                    value = attr_data.get('value', '')
                    options = [o.strip() for o in value.split('|') if o.strip()]

                attributes.append(WCProductAttributeRead(
                    id=0, # Local attributes don't have ID in this meta
                    name=name,
                    slug=attr_slug if is_taxonomy else None,
                    position=int(attr_data.get('position', 0)),
                    visible=bool(attr_data.get('is_visible', 1)),
                    variation=bool(attr_data.get('is_variation', 0)),
                    options=options
                ))
            return attributes
        except Exception:
            return []
    async def get_product_variations(self, product_id: int) -> List[WCProductVariationRead]:
        """Get variations for a product"""
        stmt = select(WPPost).where(
            WPPost.post_parent == product_id,
            WPPost.post_type == "product_variation",
            WPPost.post_status == "publish"
        )
        result = await self.session.exec(stmt)
        posts = result.all()

        variations = []
        for post in posts:
            # Fetch variation meta
            meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == post.ID)
            meta_result = await self.session.exec(meta_stmt)
            meta = {m.meta_key: m.meta_value for m in meta_result.all()}

            # Attributes for variations are stored like 'attribute_pa_color' or 'attribute_color'
            variation_attrs = []
            for key, val in meta.items():
                if key.startswith("attribute_"):
                    attr_name = key.replace("attribute_", "")
                    variation_attrs.append({"name": attr_name, "option": val})

            variations.append(WCProductVariationRead(
                id=post.ID,
                sku=meta.get("_sku"),
                price=Decimal(meta.get("_price", "0")) if meta.get("_price") else None,
                regular_price=Decimal(meta.get("_regular_price", "0")) if meta.get("_regular_price") else None,
                sale_price=Decimal(meta.get("_sale_price", "0")) if meta.get("_sale_price") else None,
                stock_quantity=int(meta.get("_stock")) if meta.get("_stock") else None,
                stock_status=meta.get("_stock_status", "instock"),
                manage_stock=meta.get("_manage_stock") == "yes",
                weight=meta.get("_weight"),
                dimensions=WCProductDimensions(
                    length=meta.get("_length"),
                    width=meta.get("_width"),
                    height=meta.get("_height")
                ),
                attributes=variation_attrs,
                date_created=post.post_date,
                date_modified=post.post_modified,
                description=post.post_content,
                status=post.post_status
            ))
        return variations

    async def get_product_full(self, product_id: int) -> Optional[WCProductFullRead]:
        """Get product with all details — OPTIMIZED: ~4 DB queries instead of 15+"""
        import phpserialize
        import json

        # ── Query 1: Get the product post ──
        post_stmt = select(WPPost).where(
            WPPost.ID == product_id,
            WPPost.post_type.in_(["product", "signal", "trading_tool", "forex_book"])
        )
        post_result = await self.session.exec(post_stmt)
        post = post_result.first()
        if not post:
            return None

        # ── Query 2: Get ALL postmeta in one shot ──
        all_meta_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id
        )
        all_meta_result = await self.session.exec(all_meta_stmt)
        all_meta_rows = all_meta_result.all()
        # Build dict (some keys may have multiple values, use first occurrence)
        post_meta = {}
        for m in all_meta_rows:
            if m.meta_key not in post_meta:
                post_meta[m.meta_key] = m.meta_value

        # ── Query 3: Get ALL taxonomy terms (type + categories + tags) in one query ──
        terms_stmt = (
            select(WPTerm, WPTermTaxonomy)
            .join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id)
            .join(WPTermRelationship, WPTermTaxonomy.term_taxonomy_id == WPTermRelationship.term_taxonomy_id)
            .where(WPTermRelationship.object_id == product_id)
        )
        terms_result = await self.session.exec(terms_stmt)
        all_terms = terms_result.all()

        # Separate by taxonomy type
        product_type = "simple"
        categories = []
        tags = []
        for term, tax in all_terms:
            if tax.taxonomy == "product_type":
                product_type = term.slug
            elif tax.taxonomy == "product_cat":
                categories.append(WCProductCategoryRead(
                    id=term.term_id, name=term.name, slug=term.slug,
                    description=tax.description, parent=tax.parent, count=tax.count
                ))
            elif tax.taxonomy == "product_tag":
                tags.append(WCProductTagRead(
                    id=term.term_id, name=term.name, slug=term.slug,
                    description=tax.description, count=tax.count
                ))

        # ── Query 4: Get product_meta_lookup ──
        meta_lookup_stmt = select(WCProductMetaLookup).where(
            WCProductMetaLookup.product_id == product_id
        )
        meta_lookup_result = await self.session.exec(meta_lookup_stmt)
        meta = meta_lookup_result.first()

        # ── Query 5: Get variations + their meta (2 queries batched) ──
        var_stmt = select(WPPost).where(
            WPPost.post_parent == product_id,
            WPPost.post_type == "product_variation",
            WPPost.post_status == "publish"
        )
        var_result = await self.session.exec(var_stmt)
        var_posts = var_result.all()

        variations = []
        if var_posts:
            # If taxonomy says "simple" but has variations, override
            if product_type == "simple":
                product_type = "variable"

            # Batch-fetch ALL variation meta in one query
            var_ids = [v.ID for v in var_posts]
            var_meta_stmt = select(WPPostMeta).where(
                WPPostMeta.post_id.in_(var_ids)
            )
            var_meta_result = await self.session.exec(var_meta_stmt)
            var_meta_all = var_meta_result.all()

            # Group meta by variation post_id
            var_meta_map = {}
            for vm in var_meta_all:
                if vm.post_id not in var_meta_map:
                    var_meta_map[vm.post_id] = {}
                var_meta_map[vm.post_id][vm.meta_key] = vm.meta_value

            for vp in var_posts:
                vm = var_meta_map.get(vp.ID, {})
                variation_attrs = []
                for key, val in vm.items():
                    if key.startswith("attribute_"):
                        attr_name = key.replace("attribute_", "")
                        variation_attrs.append({"name": attr_name, "option": val})

                variations.append(WCProductVariationRead(
                    id=vp.ID,
                    sku=vm.get("_sku"),
                    price=Decimal(vm.get("_price", "0")) if vm.get("_price") else None,
                    regular_price=Decimal(vm.get("_regular_price", "0")) if vm.get("_regular_price") else None,
                    sale_price=Decimal(vm.get("_sale_price", "0")) if vm.get("_sale_price") else None,
                    stock_quantity=int(vm.get("_stock")) if vm.get("_stock") else None,
                    stock_status=vm.get("_stock_status", "instock"),
                    manage_stock=vm.get("_manage_stock") == "yes",
                    weight=vm.get("_weight"),
                    dimensions=WCProductDimensions(
                        length=vm.get("_length"),
                        width=vm.get("_width"),
                        height=vm.get("_height")
                    ),
                    attributes=variation_attrs,
                    date_created=vp.post_date,
                    date_modified=vp.post_modified,
                    description=vp.post_content,
                    status=vp.post_status
                ))
        elif product_type == "simple":
            # Double-check for variation children (handles taxonomy mismatch)
            var_check = select(WPPost.ID).where(
                WPPost.post_parent == product_id,
                WPPost.post_type == "product_variation",
                WPPost.post_status == "publish"
            ).limit(1)
            chk = await self.session.exec(var_check)
            if chk.first():
                product_type = "variable"

        # ── Build attributes from postmeta (already fetched) ──
        attributes = []
        raw_attrs = post_meta.get("_product_attributes")
        if raw_attrs:
            try:
                attr_data = phpserialize.loads(raw_attrs.encode(), decode_strings=True)
                for attr_slug, attr_info in attr_data.items():
                    is_taxonomy = bool(attr_info.get('is_taxonomy', 0))
                    name = attr_info.get('name', attr_slug)
                    options = []
                    if is_taxonomy:
                        # Get options from terms already fetched or do a targeted query
                        for term, tax in all_terms:
                            if tax.taxonomy == name:
                                options.append(term.name)
                        if not options:
                            # Fallback: query taxonomy terms
                            t_terms = await self._get_product_terms(product_id, name)
                            options = [t['name'] for t in t_terms]
                    else:
                        value = attr_info.get('value', '')
                        options = [o.strip() for o in value.split('|') if o.strip()]

                    attributes.append(WCProductAttributeRead(
                        id=0, name=name, slug=attr_slug if is_taxonomy else None,
                        position=int(attr_info.get('position', 0)),
                        visible=bool(attr_info.get('is_visible', 1)),
                        variation=bool(attr_info.get('is_variation', 0)),
                        options=options
                    ))
            except Exception:
                pass

        # ── Build addons from postmeta (already fetched) ──
        addons = []

        # 1) Official WooCommerce Product Add-Ons: fields stored inline
        official_raw = post_meta.get("_product_addons")
        if official_raw:
            try:
                addon_data = json.loads(official_raw)
            except (json.JSONDecodeError, ValueError):
                try:
                    addon_data = phpserialize.loads(official_raw.encode(), decode_strings=True)
                    if isinstance(addon_data, dict):
                        addon_data = list(addon_data.values())
                except Exception:
                    addon_data = None
            if isinstance(addon_data, list):
                for i, ad in enumerate(addon_data):
                    if isinstance(ad, dict):
                        options = ad.get("options", [])
                        if isinstance(options, list) and options and isinstance(options[0], dict):
                            options = [o.get("label", o.get("value", "")) for o in options]
                        addons.append(WCProductAddonField(
                            name=ad.get("name") or ad.get("label") or ad.get("field_name") or f"Field {i}",
                            type=ad.get("type") or ad.get("field_type") or "text",
                            required=bool(ad.get("required", False)),
                            placeholder=ad.get("placeholder"),
                            description=ad.get("description"),
                            options=options if isinstance(options, list) else [],
                            position=int(ad.get("position", i)),
                            max_length=int(ad.get("max_length")) if ad.get("max_length") else None
                        ))

        # 2) WCPA (Acowebs) plugin: _wcpa_product_meta contains form post IDs,
        #    actual field definitions are in _wcpa_fb-editor-data on those form posts
        wcpa_raw = post_meta.get("_wcpa_product_meta")
        if wcpa_raw:
            form_ids = []
            try:
                wcpa_data = phpserialize.loads(wcpa_raw.encode(), decode_strings=True)
                if isinstance(wcpa_data, dict):
                    form_ids = [int(v) for v in wcpa_data.values()]
                elif isinstance(wcpa_data, list):
                    form_ids = [int(v) for v in wcpa_data]
            except Exception:
                pass

            if form_ids:
                # Fetch the form editor data from the WCPA form posts
                form_meta_stmt = select(WPPostMeta).where(
                    WPPostMeta.post_id.in_(form_ids),
                    WPPostMeta.meta_key == "_wcpa_fb-editor-data"
                )
                form_meta_result = await self.session.exec(form_meta_stmt)
                for fm in form_meta_result.all():
                    if not fm.meta_value:
                        continue
                    try:
                        fields = json.loads(fm.meta_value)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if not isinstance(fields, list):
                        continue
                    for i, field in enumerate(fields):
                        if not isinstance(field, dict):
                            continue
                        # WCPA radio-group stores options as "values" [{label, value}]
                        options = field.get("options", [])
                        if not options:
                            values = field.get("values", [])
                            if values and isinstance(values, list):
                                options = [v.get("label", v.get("value", "")) for v in values if isinstance(v, dict)]
                        addons.append(WCProductAddonField(
                            name=field.get("label") or field.get("name") or f"Field {i}",
                            type=field.get("type") or "text",
                            required=bool(field.get("required", False)),
                            placeholder=field.get("placeholder"),
                            description=field.get("description"),
                            options=options if isinstance(options, list) else [],
                            position=int(field.get("position", i)),
                            max_length=int(field.get("maxlength")) if field.get("maxlength") else None
                        ))

        # ── Build related/upsell/cross-sell from postmeta (already fetched) ──
        def parse_ids(val):
            if not val: return []
            try:
                decoded = phpserialize.loads(val.encode(), decode_strings=True)
                if isinstance(decoded, dict):
                    return [int(v) for v in decoded.values()]
                return [int(i) for i in decoded] if isinstance(decoded, list) else []
            except Exception:
                return [int(i.strip()) for i in val.split(",") if i.strip()]

        # ── Build featured image (one extra query only if thumbnail exists) ──
        featured_image = None
        gallery_images = []
        thumb_id_str = post_meta.get("_thumbnail_id")
        gallery_str = post_meta.get("_product_image_gallery", "")
        all_img_ids = []
        if thumb_id_str:
            try:
                all_img_ids.append(int(thumb_id_str))
            except (ValueError, TypeError):
                pass
        if gallery_str:
            all_img_ids.extend([int(x) for x in gallery_str.split(",") if x.strip()])

        if all_img_ids:
            # ── Query 6: Batch-fetch all image attachments + alt text ──
            img_stmt = select(WPPost).where(WPPost.ID.in_(all_img_ids))
            img_result = await self.session.exec(img_stmt)
            img_posts = {p.ID: p for p in img_result.all()}

            img_alt_stmt = select(WPPostMeta).where(
                WPPostMeta.post_id.in_(all_img_ids),
                WPPostMeta.meta_key == "_wp_attachment_alt_text"
            )
            img_alt_result = await self.session.exec(img_alt_stmt)
            img_alts = {m.post_id: m.meta_value for m in img_alt_result.all()}

            if thumb_id_str:
                tid = int(thumb_id_str)
                if tid in img_posts:
                    att = img_posts[tid]
                    featured_image = {
                        "id": att.ID, "url": att.guid, "title": att.post_title,
                        "alt_text": img_alts.get(tid, ""), "caption": att.post_excerpt
                    }

            if gallery_str:
                for gid in [int(x) for x in gallery_str.split(",") if x.strip()]:
                    if gid in img_posts:
                        att = img_posts[gid]
                        gallery_images.append({
                            "id": att.ID, "url": att.guid, "title": att.post_title,
                            "alt_text": img_alts.get(gid, ""), "caption": att.post_excerpt
                        })

        # ── Assemble the final response ──
        from app.schema.wordpress.post import WPImageRead
        return WCProductFullRead(
            id=post.ID,
            name=post.post_title,
            slug=post.post_name,
            type=product_type,
            description=post.post_content,
            short_description=post.post_excerpt,
            status=post.post_status,
            sku=post_meta.get("_sku", meta.sku if meta else ""),
            price=Decimal(post_meta.get("_sale_price") or post_meta.get("_price") or post_meta.get("_signal_price") or post_meta.get("_tool_price") or post_meta.get("_book_price") or "0"),
            regular_price=Decimal(post_meta.get("_regular_price") or post_meta.get("_price") or "0"),
            sale_price=Decimal(post_meta.get("_sale_price") or "0") if post_meta.get("_sale_price") else None,
            manage_stock=post_meta.get("_manage_stock") == "yes",
            stock_quantity=int(meta.stock_quantity) if meta and meta.stock_quantity is not None else None,
            stock_status=meta.stock_status if meta else "instock",
            weight=post_meta.get("_weight"),
            dimensions=WCProductDimensions(
                length=post_meta.get("_length"),
                width=post_meta.get("_width"),
                height=post_meta.get("_height")
            ),
            virtual=meta.virtual if meta else True,
            downloadable=meta.downloadable if meta else True,
            date_created=post.post_date,
            date_modified=post.post_modified,
            average_rating=meta.average_rating if meta else None,
            rating_count=meta.rating_count if meta else 0,
            total_sales=meta.total_sales if meta else 0,
            categories=categories,
            tags=tags,
            seller_payment_link=post_meta.get("_seller_payment_link") or post_meta.get("selar_url") or post_meta.get("_selar_url"),
            whop_payment_link=post_meta.get("_whop_payment_link") or post_meta.get("whop_url") or post_meta.get("_whop_url"),
            signal_link=post_meta.get("_signal_link") or None,
            telegram_link=post_meta.get("_telegram_link") or None,
            vip_group=post_meta.get("_vip_group") or None,
            featured_image=WPImageRead(**featured_image) if featured_image else None,
            gallery_images=gallery_images,
            attributes=attributes,
            variations=variations,
            addons=addons,
            cross_sell_ids=parse_ids(post_meta.get("_crosssell_ids")),
            upsell_ids=parse_ids(post_meta.get("_upsell_ids"))
        )

    async def get_products(
        self,
        limit: int = 10,
        offset: int = 0,
        status: str = "publish",
        category_id: Optional[int] = None,
        tag_id: Optional[int] = None,
        search: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        on_sale: bool = False,
        featured: bool = False
    ) -> List[WCProductRead]:
        """Get list of products — OPTIMIZED: ~5 queries total instead of 7N+1"""
        statement = select(WPPost).where(
            WPPost.post_type == "product"
        )

        if status != "any":
            statement = statement.where(WPPost.post_status == status)

        # Apply search
        if search:
            statement = statement.where(
                or_(
                    WPPost.post_title.ilike(f"%{search}%"),
                    WPPost.post_content.ilike(f"%{search}%")
                )
            )

        # Apply term filtering (category/tag)
        if category_id or tag_id:
            statement = statement.join(
                WPTermRelationship, WPPost.ID == WPTermRelationship.object_id
            ).join(
                WPTermTaxonomy, WPTermRelationship.term_taxonomy_id == WPTermTaxonomy.term_taxonomy_id
            )

            conditions = []
            if category_id:
                conditions.append(WPTermTaxonomy.term_id == category_id)
            if tag_id:
                conditions.append(WPTermTaxonomy.term_id == tag_id)

            if len(conditions) > 1:
                statement = statement.where(and_(*conditions))
            elif conditions:
                statement = statement.where(conditions[0])

        # Apply price and status filtering
        if min_price or max_price or on_sale or featured:
            statement = statement.join(
                WCProductMetaLookup, WPPost.ID == WCProductMetaLookup.product_id
            )

            if min_price:
                statement = statement.where(WCProductMetaLookup.min_price >= min_price)
            if max_price:
                statement = statement.where(WCProductMetaLookup.max_price <= max_price)
            if on_sale:
                statement = statement.where(WCProductMetaLookup.onsale == True)

        statement = statement.order_by(WPPost.post_date.desc()).limit(limit).offset(offset)
        result = await self.session.exec(statement)
        posts = result.unique().all()

        if not posts:
            return []

        product_ids = [p.ID for p in posts]

        # ── Batch Query 2: ALL postmeta for all products ──
        meta_keys = [
            "_price", "_regular_price", "_sale_price", "_sku",
            "_weight", "_length", "_width", "_height", "_manage_stock",
            "_seller_payment_link", "_whop_payment_link",
            "_selar_url", "selar_url", "_whop_url", "whop_url",
            "_thumbnail_id"
        ]
        meta_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id.in_(product_ids),
            WPPostMeta.meta_key.in_(meta_keys)
        )
        meta_result = await self.session.exec(meta_stmt)
        all_meta = meta_result.all()

        # Group by product_id
        meta_map = {}
        for m in all_meta:
            if m.post_id not in meta_map:
                meta_map[m.post_id] = {}
            if m.meta_key not in meta_map[m.post_id]:
                meta_map[m.post_id][m.meta_key] = m.meta_value

        # ── Batch Query 3: ALL taxonomy terms for all products ──
        terms_stmt = (
            select(WPTermRelationship.object_id, WPTerm, WPTermTaxonomy)
            .join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id)
            .join(WPTermRelationship, WPTermTaxonomy.term_taxonomy_id == WPTermRelationship.term_taxonomy_id)
            .where(
                WPTermRelationship.object_id.in_(product_ids),
                WPTermTaxonomy.taxonomy.in_(["product_type", "product_cat", "product_tag"])
            )
        )
        terms_result = await self.session.exec(terms_stmt)
        all_terms = terms_result.all()

        # Group by product_id
        terms_map = {}
        for obj_id, term, tax in all_terms:
            if obj_id not in terms_map:
                terms_map[obj_id] = {"type": "simple", "categories": [], "tags": []}
            if tax.taxonomy == "product_type":
                terms_map[obj_id]["type"] = term.slug
            elif tax.taxonomy == "product_cat":
                terms_map[obj_id]["categories"].append(WCProductCategoryRead(
                    id=term.term_id, name=term.name, slug=term.slug,
                    description=tax.description, parent=tax.parent, count=tax.count
                ))
            elif tax.taxonomy == "product_tag":
                terms_map[obj_id]["tags"].append(WCProductTagRead(
                    id=term.term_id, name=term.name, slug=term.slug,
                    description=tax.description, count=tax.count
                ))

        # ── Batch Query 4: meta_lookup for all products ──
        lookup_stmt = select(WCProductMetaLookup).where(
            WCProductMetaLookup.product_id.in_(product_ids)
        )
        lookup_result = await self.session.exec(lookup_stmt)
        lookup_map = {lk.product_id: lk for lk in lookup_result.all()}

        # ── Batch Query 5: Featured images for all products ──
        thumb_ids = []
        thumb_product_map = {}
        for pid in product_ids:
            pm = meta_map.get(pid, {})
            tid = pm.get("_thumbnail_id")
            if tid:
                try:
                    tid_int = int(tid)
                    thumb_ids.append(tid_int)
                    thumb_product_map[tid_int] = pid
                except (ValueError, TypeError):
                    pass

        img_map = {}
        if thumb_ids:
            img_stmt = select(WPPost).where(WPPost.ID.in_(thumb_ids))
            img_result = await self.session.exec(img_stmt)
            img_posts = {p.ID: p for p in img_result.all()}

            img_alt_stmt = select(WPPostMeta).where(
                WPPostMeta.post_id.in_(thumb_ids),
                WPPostMeta.meta_key == "_wp_attachment_alt_text"
            )
            img_alt_result = await self.session.exec(img_alt_stmt)
            img_alts = {m.post_id: m.meta_value for m in img_alt_result.all()}

            for tid_int, att in img_posts.items():
                img_map[tid_int] = {
                    "id": att.ID, "url": att.guid, "title": att.post_title,
                    "alt_text": img_alts.get(tid_int, ""), "caption": att.post_excerpt
                }

        # ── Assemble all products ──
        from app.schema.wordpress.post import WPImageRead
        products = []
        for post in posts:
            pm = meta_map.get(post.ID, {})
            terms = terms_map.get(post.ID, {"type": "simple", "categories": [], "tags": []})
            meta = lookup_map.get(post.ID)

            # Check for featured image
            featured_image = None
            tid_str = pm.get("_thumbnail_id")
            if tid_str:
                try:
                    img_data = img_map.get(int(tid_str))
                    if img_data:
                        featured_image = WPImageRead(**img_data)
                except (ValueError, TypeError):
                    pass

            products.append(WCProductRead(
                id=post.ID,
                name=post.post_title,
                slug=post.post_name,
                type=terms["type"],
                description=post.post_content,
                short_description=post.post_excerpt,
                status=post.post_status,
                sku=pm.get("_sku", meta.sku if meta else ""),
                price=Decimal(pm.get("_price", "0")) if pm.get("_price") else None,
                regular_price=Decimal(pm.get("_regular_price", "0")) if pm.get("_regular_price") else None,
                sale_price=Decimal(pm.get("_sale_price", "0")) if pm.get("_sale_price") else None,
                manage_stock=pm.get("_manage_stock") == "yes",
                stock_quantity=int(meta.stock_quantity) if meta and meta.stock_quantity is not None else None,
                stock_status=meta.stock_status if meta else "instock",
                weight=pm.get("_weight"),
                dimensions=WCProductDimensions(
                    length=pm.get("_length"),
                    width=pm.get("_width"),
                    height=pm.get("_height")
                ),
                virtual=meta.virtual if meta else False,
                downloadable=meta.downloadable if meta else False,
                date_created=post.post_date,
                date_modified=post.post_modified,
                average_rating=meta.average_rating if meta else None,
                rating_count=meta.rating_count if meta else 0,
                total_sales=meta.total_sales if meta else 0,
                categories=terms["categories"],
                tags=terms["tags"],
                seller_payment_link=pm.get("_seller_payment_link") or pm.get("selar_url") or pm.get("_selar_url"),
                whop_payment_link=pm.get("_whop_payment_link") or pm.get("whop_url") or pm.get("_whop_url"),
                featured_image=featured_image,
                gallery_images=[]
            ))
        return products

    async def create_product(self, data: WCProductCreate) -> WCProductRead:
        """Create a new product"""
        # Create the post
        new_post = WPPost(
            post_author=1,  # Default admin
            post_title=data.name,
            post_content=data.description or "",
            post_excerpt=data.short_description or "",
            post_status=data.status or "draft",
            post_type="product",
            post_name=data.name.lower().replace(" ", "-"),
            post_date=datetime.now(),
            post_date_gmt=datetime.now(),
            post_modified=datetime.now(),
            post_modified_gmt=datetime.now()
        )
        self.session.add(new_post)
        await self.session.flush()
        product_id = new_post.ID
        await self.session.commit()
        await self.session.refresh(new_post)

        # Add product type taxonomy
        if data.type:
            await self._set_product_terms(product_id, [data.type], "product_type")

        # Add categories and tags
        if data.categories:
            await self.set_product_categories(product_id, data.categories)
        if data.tags:
            await self.set_product_tags(product_id, data.tags)

        # Add product meta
        meta_data = {
            "_sku": data.sku or "",
            "_price": str(data.price or 0),
            "_regular_price": str(data.regular_price or data.price or 0),
            "_sale_price": str(data.sale_price or ""),
            "_stock": str(data.stock_quantity or 0),
            "_stock_status": data.stock_status or "instock",
            "_virtual": "yes" if data.virtual else "no",
            "_downloadable": "yes" if data.downloadable else "no",
            "_manage_stock": "yes" if data.manage_stock else "no",
            "_weight": data.weight or "",
            "_seller_payment_link": data.seller_payment_link or "",
            "_whop_payment_link": data.whop_payment_link or "",
            "_signal_link": data.signal_link or "",
            "_telegram_link": data.telegram_link or "",
            "_vip_group": data.vip_group or "",
        }

        if data.dimensions:
            meta_data["_length"] = data.dimensions.length or ""
            meta_data["_width"] = data.dimensions.width or ""
            meta_data["_height"] = data.dimensions.height or ""

        if data.attributes:
            import phpserialize
            serialized_attrs = {}
            for i, attr in enumerate(data.attributes):
                attr_name = attr.get("name", "")
                serialized_attrs[attr_name] = {
                    "name": attr_name,
                    "value": "|".join(attr.get("options", [])) if not attr.get("slug") else "",
                    "position": attr.get("position", i),
                    "is_visible": 1 if attr.get("visible", True) else 0,
                    "is_variation": 1 if attr.get("variation", False) else 0,
                    "is_taxonomy": 1 if attr.get("slug") else 0
                }
            meta_data["_product_attributes"] = phpserialize.dumps(serialized_attrs).decode()

        for key, value in meta_data.items():
            meta = WPPostMeta(
                post_id=product_id,
                meta_key=key,
                meta_value=value
            )
            self.session.add(meta)

        # Create or update product meta lookup entry
        lookup_stmt = select(WCProductMetaLookup).where(WCProductMetaLookup.product_id == product_id)
        lookup_res = await self.session.exec(lookup_stmt)
        existing_lookup = lookup_res.first()

        if existing_lookup:
            existing_lookup.sku = data.sku or ""
            existing_lookup.virtual = data.virtual or False
            existing_lookup.downloadable = data.downloadable or False
            existing_lookup.min_price = data.price
            existing_lookup.max_price = data.price
            existing_lookup.stock_quantity = float(data.stock_quantity) if data.stock_quantity is not None else None
            existing_lookup.stock_status = data.stock_status or "instock"
            self.session.add(existing_lookup)
        else:
            product_meta = WCProductMetaLookup(
                product_id=product_id,
                sku=data.sku or "",
                virtual=data.virtual or False,
                downloadable=data.downloadable or False,
                min_price=data.price,
                max_price=data.price,
                stock_quantity=float(data.stock_quantity) if data.stock_quantity is not None else None,
                stock_status=data.stock_status or "instock",
                total_sales=0
            )
            self.session.add(product_meta)

        # Store custom addon fields (e.g. Telegram Username input)
        if data.addons:
            await self.set_product_addons(product_id, data.addons)

        await self.session.commit()
        return await self.get_product(product_id)

    async def set_product_categories(self, product_id: int, category_ids: List[int]) -> None:
        """Replace product categories"""
        await self._set_product_terms_by_id(product_id, category_ids, "product_cat")

    async def set_product_tags(self, product_id: int, tag_ids: List[int]) -> None:
        """Replace product tags"""
        await self._set_product_terms_by_id(product_id, tag_ids, "product_tag")

    async def _set_product_terms(self, product_id: int, term_slugs: List[str], taxonomy: str) -> None:
        """Set terms for a product by slug"""
        term_ids = []
        for slug in term_slugs:
            stmt = select(WPTerm).join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id).where(
                WPTerm.slug == slug,
                WPTermTaxonomy.taxonomy == taxonomy
            )
            res = await self.session.exec(stmt)
            term = res.first()
            if term:
                term_ids.append(term.term_id)

        if term_ids:
            await self._set_product_terms_by_id(product_id, term_ids, taxonomy)

    async def _set_product_terms_by_id(self, product_id: int, term_ids: List[int], taxonomy: str) -> None:
        """Internal helper to set product terms by ID"""
        # 1. Get term_taxonomy_ids for these terms
        stmt = select(WPTermTaxonomy).where(
            WPTermTaxonomy.term_id.in_(term_ids),
            WPTermTaxonomy.taxonomy == taxonomy
        )
        res = await self.session.exec(stmt)
        tt_ids = [t.term_taxonomy_id for t in res.all()]

        # 2. Remove existing relationships for this taxonomy
        # We need to find which relationships belong to this taxonomy
        del_stmt = select(WPTermRelationship).join(
            WPTermTaxonomy, WPTermRelationship.term_taxonomy_id == WPTermTaxonomy.term_taxonomy_id
        ).where(
            WPTermRelationship.object_id == product_id,
            WPTermTaxonomy.taxonomy == taxonomy
        )
        del_res = await self.session.exec(del_stmt)
        for rel in del_res.all():
            await self.session.delete(rel)

        await self.session.flush()

        # 3. Add new relationships
        for tt_id in tt_ids:
            rel = WPTermRelationship(object_id=product_id, term_taxonomy_id=tt_id)
            self.session.add(rel)

        await self.session.commit()

    async def update_product(self, product_id: int, data: WCProductUpdate) -> Optional[WCProductRead]:
        """Update an existing product"""
        # Fetch product post
        stmt = select(WPPost).where(
            WPPost.ID == product_id,
            WPPost.post_type == "product"
        )
        result = await self.session.exec(stmt)
        post = result.first()

        if not post:
            return None

        # Update post fields
        if data.name is not None:
            post.post_title = data.name
            post.post_name = data.name.lower().replace(" ", "-")
        if data.description is not None:
            post.post_content = data.description
        if data.short_description is not None:
            post.post_excerpt = data.short_description
        if data.status is not None:
            post.post_status = data.status

        post.post_modified = datetime.now()
        post.post_modified_gmt = datetime.now()
        self.session.add(post)

        # Update taxonomy terms
        if data.type:
            await self._set_product_terms(product_id, [data.type], "product_type")
        if data.categories is not None:
            await self.set_product_categories(product_id, data.categories)
        if data.tags is not None:
            await self.set_product_tags(product_id, data.tags)

        # Update meta
        meta_updates = {}
        if data.sku is not None: meta_updates["_sku"] = data.sku
        if data.price is not None: meta_updates["_price"] = str(data.price)
        if data.regular_price is not None: meta_updates["_regular_price"] = str(data.regular_price)
        if data.sale_price is not None: meta_updates["_sale_price"] = str(data.sale_price)
        if data.manage_stock is not None: meta_updates["_manage_stock"] = "yes" if data.manage_stock else "no"
        if data.stock_quantity is not None: meta_updates["_stock"] = str(data.stock_quantity)
        if data.stock_status is not None: meta_updates["_stock_status"] = data.stock_status
        if data.weight is not None: meta_updates["_weight"] = data.weight
        if data.virtual is not None: meta_updates["_virtual"] = "yes" if data.virtual else "no"
        if data.downloadable is not None: meta_updates["_downloadable"] = "yes" if data.downloadable else "no"
        if data.seller_payment_link is not None: meta_updates["_seller_payment_link"] = data.seller_payment_link
        if data.whop_payment_link is not None: meta_updates["_whop_payment_link"] = data.whop_payment_link
        if data.signal_link is not None: meta_updates["_signal_link"] = data.signal_link
        if data.telegram_link is not None: meta_updates["_telegram_link"] = data.telegram_link
        if data.vip_group is not None: meta_updates["_vip_group"] = data.vip_group

        if data.dimensions:
            if data.dimensions.length is not None: meta_updates["_length"] = data.dimensions.length
            if data.dimensions.width is not None: meta_updates["_width"] = data.dimensions.width
            if data.dimensions.height is not None: meta_updates["_height"] = data.dimensions.height

        if data.attributes is not None:
            import phpserialize
            serialized_attrs = {}
            for i, attr in enumerate(data.attributes):
                attr_name = attr.get("name", "")
                serialized_attrs[attr_name] = {
                    "name": attr_name,
                    "value": "|".join(attr.get("options", [])) if not attr.get("slug") else "",
                    "position": attr.get("position", i),
                    "is_visible": 1 if attr.get("visible", True) else 0,
                    "is_variation": 1 if attr.get("variation", False) else 0,
                    "is_taxonomy": 1 if attr.get("slug") else 0
                }
            meta_updates["_product_attributes"] = phpserialize.dumps(serialized_attrs).decode()

        for key, value in meta_updates.items():
            await self._set_product_meta(product_id, key, value)

        # Update product meta lookup
        lookup_stmt = select(WCProductMetaLookup).where(
            WCProductMetaLookup.product_id == product_id
        )
        lookup_result = await self.session.exec(lookup_stmt)
        lookup = lookup_result.first()

        if lookup:
            if data.sku is not None: lookup.sku = data.sku
            if data.price is not None:
                lookup.min_price = data.price
                lookup.max_price = data.price
            if data.stock_quantity is not None: lookup.stock_quantity = float(data.stock_quantity)
            if data.stock_status is not None: lookup.stock_status = data.stock_status
            if data.virtual is not None: lookup.virtual = data.virtual
            if data.downloadable is not None: lookup.downloadable = data.downloadable
            self.session.add(lookup)

        await self.session.commit()
        return await self.get_product(product_id)

    async def _set_product_meta(self, product_id: int, key: str, value: Any) -> None:
        """Internal helper to set or update post meta"""
        stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key == key
        )
        res = await self.session.exec(stmt)
        meta = res.first()

        if meta:
            meta.meta_value = str(value)
            self.session.add(meta)
        else:
            new_meta = WPPostMeta(post_id=product_id, meta_key=key, meta_value=str(value))
            self.session.add(new_meta)

    async def delete_product(self, product_id: int, force: bool = False) -> bool:
        """Delete (trash) a product. If force=True, permanently delete."""
        stmt = select(WPPost).where(
            WPPost.ID == product_id,
            WPPost.post_type == "product"
        )
        result = await self.session.exec(stmt)
        post = result.first()

        if not post:
            return False

        if force:
            # Delete variations first
            variations = await self.get_product_variations(product_id)
            for var in variations:
                await self.delete_variation(var.id)

            # Permanently delete post and its meta
            meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == product_id)
            meta_result = await self.session.exec(meta_stmt)
            for meta in meta_result.all():
                await self.session.delete(meta)

            await self.session.delete(post)
        else:
            # Move to trash
            post.post_status = "trash"
            self.session.add(post)

        await self.session.commit()
        return True

    async def create_variation(self, product_id: int, data: WCProductVariationCreate) -> Optional[WCProductVariationRead]:
        """Create a new product variation"""
        new_post = WPPost(
            post_author=1,
            post_title=f"Variation for Product #{product_id}",
            post_content=data.description or "",
            post_status=data.status or "publish",
            post_type="product_variation",
            post_parent=product_id,
            post_date=datetime.now(),
            post_modified=datetime.now()
        )
        self.session.add(new_post)
        await self.session.flush()
        var_id = new_post.ID
        await self.session.commit()
        await self.session.refresh(new_post)

        meta_data = {
            "_sku": data.sku or "",
            "_price": str(data.sale_price if data.sale_price else data.regular_price or 0),
            "_regular_price": str(data.regular_price or 0),
            "_sale_price": str(data.sale_price or ""),
            "_stock": str(data.stock_quantity or 0),
            "_stock_status": data.stock_status or "instock",
            "_manage_stock": "yes" if data.manage_stock else "no",
            "_weight": data.weight or "",
            "_length": data.length or "",
            "_width": data.width or "",
            "_height": data.height or ""
        }

        if data.attributes:
            for attr in data.attributes:
                name = attr.get("name", "").lower().replace(" ", "-")
                meta_key = f"attribute_{name}"
                meta_data[meta_key] = attr.get("option", "")

        for key, value in meta_data.items():
            meta = WPPostMeta(post_id=var_id, meta_key=key, meta_value=value)
            self.session.add(meta)

        await self.session.commit()

        # Sync min/max price range on parent product
        await self._update_product_price_range(product_id)

        variations = await self.get_product_variations(product_id)
        return next((v for v in variations if v.id == var_id), None)

    async def update_variation(self, variation_id: int, data: WCProductVariationUpdate) -> Optional[WCProductVariationRead]:
        """Update an existing product variation"""
        stmt = select(WPPost).where(
            WPPost.ID == variation_id,
            WPPost.post_type == "product_variation"
        )
        result = await self.session.exec(stmt)
        post = result.first()
        if not post:
            return None

        if data.description is not None: post.post_content = data.description
        if data.status is not None: post.post_status = data.status
        post.post_modified = datetime.now()
        self.session.add(post)

        meta_updates = {}
        if data.sku is not None: meta_updates["_sku"] = data.sku
        if data.regular_price is not None: meta_updates["_regular_price"] = str(data.regular_price)
        if data.sale_price is not None: meta_updates["_sale_price"] = str(data.sale_price)

        # Simple logical price update
        if data.regular_price is not None or data.sale_price is not None:
             # Just update _price to sale if present, else regular
             # (Needs fetching original if only one is provided, but we'll use a shortcut here)
             pass

        if data.stock_quantity is not None: meta_updates["_stock"] = str(data.stock_quantity)
        if data.stock_status is not None: meta_updates["_stock_status"] = data.stock_status
        if data.manage_stock is not None: meta_updates["_manage_stock"] = "yes" if data.manage_stock else "no"
        if data.weight is not None: meta_updates["_weight"] = data.weight
        if data.length is not None: meta_updates["_length"] = data.length
        if data.width is not None: meta_updates["_width"] = data.width
        if data.height is not None: meta_updates["_height"] = data.height

        if data.attributes:
            for attr in data.attributes:
                name = attr.get("name", "").lower().replace(" ", "-")
                meta_key = f"attribute_{name}"
                meta_updates[meta_key] = attr.get("option", "")

        for key, value in meta_updates.items():
            await self._set_product_meta(variation_id, key, value)

        # Recalculate _price based on current sale/regular prices
        if data.regular_price is not None or data.sale_price is not None:
            meta_stmt = select(WPPostMeta).where(
                WPPostMeta.post_id == variation_id,
                WPPostMeta.meta_key.in_(["_regular_price", "_sale_price"])
            )
            price_result = await self.session.exec(meta_stmt)
            price_meta = {m.meta_key: m.meta_value for m in price_result.all()}
            sale = price_meta.get("_sale_price", "")
            regular = price_meta.get("_regular_price", "0")
            active_price = sale if sale and sale not in ("", "0") else regular
            await self._set_product_meta(variation_id, "_price", active_price)

        parent_id = post.post_parent
        await self.session.commit()

        # Sync min/max price range on parent product
        if parent_id:
            await self._update_product_price_range(parent_id)

        return next((v for v in await self.get_product_variations(parent_id) if v.id == variation_id), None)

    async def delete_variation(self, variation_id: int) -> bool:
        """Delete a variation permanently"""
        stmt = select(WPPost).where(
            WPPost.ID == variation_id,
            WPPost.post_type == "product_variation"
        )
        result = await self.session.exec(stmt)
        post = result.first()
        if not post:
            return False

        parent_id = post.post_parent

        # Delete meta first
        meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == variation_id)
        meta_res = await self.session.exec(meta_stmt)
        for m in meta_res.all():
            await self.session.delete(m)

        await self.session.delete(post)
        await self.session.commit()

        # Sync min/max price range on parent product
        if parent_id:
            await self._update_product_price_range(parent_id)

        return True

    async def get_product_meta(self, product_id: int) -> Optional[WCProductMeta]:
        """Get product meta lookup entry"""
        stmt = select(WCProductMetaLookup).where(
            WCProductMetaLookup.product_id == product_id
        )
        result = await self.session.exec(stmt)
        meta = result.first()

        if not meta:
            return None

        return WCProductMeta(
            product_id=meta.product_id,
            sku=meta.sku,
            virtual=meta.virtual or False,
            downloadable=meta.downloadable or False,
            min_price=meta.min_price,
            max_price=meta.max_price,
            onsale=meta.onsale or False,
            stock_quantity=meta.stock_quantity,
            stock_status=meta.stock_status,
            rating_count=meta.rating_count or 0,
            average_rating=meta.average_rating,
            total_sales=meta.total_sales or 0,
            tax_status=meta.tax_status,
            tax_class=meta.tax_class
        )

    async def list_all_tags(self, limit: int = 20, offset: int = 0) -> List[WCProductTagRead]:
        """List all product tags"""
        stmt = (
            select(WPTerm, WPTermTaxonomy)
            .join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id)
            .where(
                WPTermTaxonomy.taxonomy == "product_tag"
            )
            .limit(limit).offset(offset)
        )
        res = await self.session.exec(stmt)
        return [
            WCProductTagRead(
                id=term.term_id,
                name=term.name,
                slug=term.slug,
                count=tax.count
            )
            for term, tax in res.all()
        ]

    # ============== Product Image Methods ==============

    async def get_product_images(self, product_id: int) -> dict:
        """Get product featured image and gallery images"""
        result = {
            "featured_image": None,
            "gallery_images": []
        }

        # Get featured image (_thumbnail_id)
        thumb_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key == "_thumbnail_id"
        )
        thumb_result = await self.session.exec(thumb_stmt)
        thumb_meta = thumb_result.first()

        if thumb_meta and thumb_meta.meta_value:
            thumb_id = int(thumb_meta.meta_value)
            result["featured_image"] = await self._get_attachment_data(thumb_id)

        # Get gallery images (_product_image_gallery)
        gallery_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key == "_product_image_gallery"
        )
        gallery_result = await self.session.exec(gallery_stmt)
        gallery_meta = gallery_result.first()

        if gallery_meta and gallery_meta.meta_value:
            gallery_ids = [int(x) for x in gallery_meta.meta_value.split(",") if x.strip()]
            for img_id in gallery_ids:
                img_data = await self._get_attachment_data(img_id)
                if img_data:
                    result["gallery_images"].append(img_data)

        return result

    async def set_product_featured_image(self, product_id: int, attachment_id: int) -> bool:
        """Set the featured/main image for a product"""
        # Verify product exists
        stmt = select(WPPost).where(
            WPPost.ID == product_id,
            WPPost.post_type == "product"
        )
        result = await self.session.exec(stmt)
        if not result.first():
            return False

        # Verify attachment exists
        attachment = await self.session.get(WPPost, attachment_id)
        if not attachment or attachment.post_type != "attachment":
            return False

        await self._set_product_meta(product_id, "_thumbnail_id", str(attachment_id))
        return True

    async def set_product_gallery(self, product_id: int, image_ids: List[int]) -> bool:
        """Set the product gallery images (replaces existing gallery)"""
        # Verify product exists
        stmt = select(WPPost).where(
            WPPost.ID == product_id,
            WPPost.post_type == "product"
        )
        result = await self.session.exec(stmt)
        if not result.first():
            return False

        # Validate all attachment IDs
        valid_ids = []
        for img_id in image_ids:
            attachment = await self.session.get(WPPost, img_id)
            if attachment and attachment.post_type == "attachment":
                valid_ids.append(str(img_id))

        gallery_value = ",".join(valid_ids) if valid_ids else ""
        await self._set_product_meta(product_id, "_product_image_gallery", gallery_value)
        return True

    async def add_product_gallery_image(self, product_id: int, attachment_id: int) -> bool:
        """Add a single image to product gallery"""
        # Verify attachment exists
        attachment = await self.session.get(WPPost, attachment_id)
        if not attachment or attachment.post_type != "attachment":
            return False

        # Get current gallery
        gallery_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key == "_product_image_gallery"
        )
        gallery_result = await self.session.exec(gallery_stmt)
        gallery_meta = gallery_result.first()

        current_ids = []
        if gallery_meta and gallery_meta.meta_value:
            current_ids = [x.strip() for x in gallery_meta.meta_value.split(",") if x.strip()]

        # Add if not already present
        if str(attachment_id) not in current_ids:
            current_ids.append(str(attachment_id))
            await self._set_product_meta(product_id, "_product_image_gallery", ",".join(current_ids))

        return True

    async def remove_product_gallery_image(self, product_id: int, attachment_id: int) -> bool:
        """Remove a single image from product gallery"""
        gallery_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key == "_product_image_gallery"
        )
        gallery_result = await self.session.exec(gallery_stmt)
        gallery_meta = gallery_result.first()

        if not gallery_meta or not gallery_meta.meta_value:
            return False

        current_ids = [x.strip() for x in gallery_meta.meta_value.split(",") if x.strip()]

        if str(attachment_id) in current_ids:
            current_ids.remove(str(attachment_id))
            await self._set_product_meta(product_id, "_product_image_gallery", ",".join(current_ids))
            return True

        return False

    async def _get_attachment_data(self, attachment_id: int) -> Optional[dict]:
        """Get attachment data for image response"""
        attachment = await self.session.get(WPPost, attachment_id)
        if not attachment or attachment.post_type != "attachment":
            return None

        # Get alt text
        alt_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == attachment_id,
            WPPostMeta.meta_key == "_wp_attachment_alt_text"
        )
        alt_result = await self.session.exec(alt_stmt)
        alt_meta = alt_result.first()

        return {
            "id": attachment.ID,
            "title": attachment.post_title,
            "url": attachment.guid,
            "alt_text": alt_meta.meta_value if alt_meta else "",
            "caption": attachment.post_excerpt,
            "mime_type": attachment.post_mime_type
        }

    async def _set_product_meta(self, product_id: int, meta_key: str, meta_value: str) -> None:
        """Helper to set product post meta"""
        stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key == meta_key
        )
        result = await self.session.exec(stmt)
        meta = result.first()

        if meta:
            meta.meta_value = meta_value
            self.session.add(meta)
        else:
            new_meta = WPPostMeta(post_id=product_id, meta_key=meta_key, meta_value=meta_value)
            self.session.add(new_meta)

        await self.session.commit()

    # ============== Product Addons (Custom Input Fields) ==============

    async def get_product_addons(self, product_id: int) -> List[WCProductAddonField]:
        """Get custom input fields (addons) for a product, e.g. Telegram Username.
        Supports both official WooCommerce Product Add-Ons (_product_addons)
        and WCPA plugin (_wcpa_product_meta -> form post IDs -> _wcpa_fb-editor-data)."""
        import phpserialize
        import json

        # Fetch both meta keys
        addon_meta_keys = ["_product_addons", "_wcpa_product_meta"]
        stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key.in_(addon_meta_keys)
        )
        result = await self.session.exec(stmt)
        metas = {m.meta_key: m.meta_value for m in result.all()}

        all_addons = []

        # 1) Official WooCommerce Product Add-Ons: fields stored inline
        official_raw = metas.get("_product_addons")
        if official_raw:
            try:
                data = json.loads(official_raw)
            except (json.JSONDecodeError, ValueError):
                try:
                    data = phpserialize.loads(official_raw.encode(), decode_strings=True)
                    if isinstance(data, dict):
                        data = list(data.values())
                except Exception:
                    data = None
            if isinstance(data, list):
                for i, ad in enumerate(data):
                    if isinstance(ad, dict):
                        options = ad.get("options", [])
                        if isinstance(options, list) and options and isinstance(options[0], dict):
                            options = [o.get("label", o.get("value", "")) for o in options]
                        all_addons.append(WCProductAddonField(
                            name=ad.get("name") or ad.get("label") or ad.get("field_name") or f"Field {i}",
                            type=ad.get("type") or ad.get("field_type") or "text",
                            required=bool(ad.get("required", False)),
                            placeholder=ad.get("placeholder"),
                            description=ad.get("description"),
                            options=options if isinstance(options, list) else [],
                            position=int(ad.get("position", i)),
                            max_length=int(ad.get("max_length")) if ad.get("max_length") else None
                        ))

        # 2) WCPA (Acowebs) plugin: _wcpa_product_meta contains form post IDs
        wcpa_raw = metas.get("_wcpa_product_meta")
        if wcpa_raw:
            form_ids = []
            try:
                wcpa_data = phpserialize.loads(wcpa_raw.encode(), decode_strings=True)
                if isinstance(wcpa_data, dict):
                    form_ids = [int(v) for v in wcpa_data.values()]
                elif isinstance(wcpa_data, list):
                    form_ids = [int(v) for v in wcpa_data]
            except Exception:
                pass

            if form_ids:
                form_meta_stmt = select(WPPostMeta).where(
                    WPPostMeta.post_id.in_(form_ids),
                    WPPostMeta.meta_key == "_wcpa_fb-editor-data"
                )
                form_meta_result = await self.session.exec(form_meta_stmt)
                for fm in form_meta_result.all():
                    if not fm.meta_value:
                        continue
                    try:
                        fields = json.loads(fm.meta_value)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if not isinstance(fields, list):
                        continue
                    for i, field in enumerate(fields):
                        if not isinstance(field, dict):
                            continue
                        options = field.get("options", [])
                        if not options:
                            values = field.get("values", [])
                            if values and isinstance(values, list):
                                options = [v.get("label", v.get("value", "")) for v in values if isinstance(v, dict)]
                        all_addons.append(WCProductAddonField(
                            name=field.get("label") or field.get("name") or f"Field {i}",
                            type=field.get("type") or "text",
                            required=bool(field.get("required", False)),
                            placeholder=field.get("placeholder"),
                            description=field.get("description"),
                            options=options if isinstance(options, list) else [],
                            position=int(field.get("position", i)),
                            max_length=int(field.get("maxlength")) if field.get("maxlength") else None
                        ))

        return all_addons

    async def set_product_addons(self, product_id: int, addons: List[WCProductAddonField]) -> bool:
        """Set custom input fields for a product. Stores as JSON in _product_addons meta."""
        import json

        addon_list = [addon.model_dump() for addon in addons]
        json_value = json.dumps(addon_list)

        await self._set_product_meta(product_id, "_product_addons", json_value)

        # Also set the flag that tells WooCommerce this product has addons
        await self._set_product_meta(product_id, "_product_addons_exclude_global", "1")

        return True

    async def delete_product_addons(self, product_id: int) -> bool:
        """Remove all custom input fields from a product."""
        stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == product_id,
            WPPostMeta.meta_key.in_(["_product_addons", "_product_addons_exclude_global"])
        )
        result = await self.session.exec(stmt)
        metas = result.all()
        if not metas:
            return False

        for meta in metas:
            await self.session.delete(meta)

        await self.session.commit()
        return True

    # ============== Variation Price Range Sync ==============

    async def _update_product_price_range(self, product_id: int) -> None:
        """Recalculate and update min/max prices on the parent product's meta lookup
        based on all its variations. This keeps the price range in sync just like
        WordPress does when you save a variable product."""
        variations = await self.get_product_variations(product_id)

        if not variations:
            return

        prices = []
        for v in variations:
            if v.price is not None:
                prices.append(v.price)

        if not prices:
            return

        min_price = min(prices)
        max_price = max(prices)

        # Update product meta lookup
        lookup_stmt = select(WCProductMetaLookup).where(
            WCProductMetaLookup.product_id == product_id
        )
        lookup_result = await self.session.exec(lookup_stmt)
        lookup = lookup_result.first()

        if lookup:
            lookup.min_price = min_price
            lookup.max_price = max_price
            if min_price != max_price:
                lookup.onsale = any(v.sale_price and v.sale_price > 0 for v in variations)
            self.session.add(lookup)
        else:
            new_lookup = WCProductMetaLookup(
                product_id=product_id,
                min_price=min_price,
                max_price=max_price,
                onsale=any(v.sale_price and v.sale_price > 0 for v in variations),
                stock_status="instock"
            )
            self.session.add(new_lookup)

        # Also update the parent post meta _price to the min price
        await self._set_product_meta(product_id, "_price", str(min_price))

        await self.session.commit()




class WCCustomerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_customer(self, customer_id: int) -> Optional[WCCustomerLookup]:
        return await self.session.get(WCCustomerLookup, customer_id)

    async def get_customers(self, limit: int = 10, offset: int = 0) -> List[WCCustomerLookup]:
        statement = select(WCCustomerLookup).limit(limit).offset(offset)
        result = await self.session.exec(statement)
        return result.all()

    async def get_customer_by_email(self, email: str) -> Optional[WCCustomerLookup]:
        statement = select(WCCustomerLookup).where(WCCustomerLookup.email == email)
        result = await self.session.exec(statement)
        return result.first()

    async def get_customer_by_user_id(self, user_id: int) -> Optional[WCCustomerLookup]:
        statement = select(WCCustomerLookup).where(WCCustomerLookup.user_id == user_id)
        result = await self.session.exec(statement)
        return result.first()


class WCCouponRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_coupon(self, coupon_id: int) -> Optional[WCCouponRead]:
        """Get a coupon by ID with all metadata"""
        stmt = select(WPPost).where(
            WPPost.ID == coupon_id,
            WPPost.post_type == "shop_coupon"
        )
        result = await self.session.exec(stmt)
        post = result.first()
        if not post:
            return None

        # Fetch all related meta
        meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == coupon_id)
        meta_result = await self.session.exec(meta_stmt)
        meta = {m.meta_key: m.meta_value for m in meta_result.all()}

        return self._map_to_coupon_read(post, meta)

    async def get_coupon_by_code(self, code: str) -> Optional[WCCouponRead]:
        """Get a coupon by its code (post_title) - Case-insensitive"""
        code_clean = code.strip().lower()
        stmt = select(WPPost).where(
            func.lower(WPPost.post_title) == code_clean,
            WPPost.post_type == "shop_coupon",
            WPPost.post_status == "publish"
        )
        result = await self.session.exec(stmt)
        post = result.first()
        if not post:
            return None

        meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == post.ID)
        meta_result = await self.session.exec(meta_stmt)
        meta = {m.meta_key: m.meta_value for m in meta_result.all()}

        return self._map_to_coupon_read(post, meta)

    async def get_coupons(self, limit: int = 10, offset: int = 0, search: str = None) -> List[WCCouponRead]:
        """Get list of coupons"""
        stmt = select(WPPost).where(WPPost.post_type == "shop_coupon")
        if search:
            stmt = stmt.where(or_(
                WPPost.post_title.like(f"%{search}%"),
                WPPost.post_excerpt.like(f"%{search}%")
            ))

        stmt = stmt.order_by(WPPost.post_date.desc()).limit(limit).offset(offset)
        result = await self.session.exec(stmt)
        posts = result.all()

        coupons = []
        for post in posts:
            meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == post.ID)
            meta_result = await self.session.exec(meta_stmt)
            meta = {m.meta_key: m.meta_value for m in meta_result.all()}
            coupons.append(self._map_to_coupon_read(post, meta))

        return coupons

    async def create_coupon(self, data: WCCouponCreate) -> WCCouponRead:
        """Create a new coupon"""
        post = WPPost(
            post_title=data.code,
            post_excerpt=data.description or "",
            post_status="publish",
            post_type="shop_coupon",
            post_author=1 # Admin
        )
        self.session.add(post)
        await self.session.flush() # Get ID

        coupon_id = post.ID
        meta_items = self._map_to_meta(data)
        for key, value in meta_items.items():
            meta = WPPostMeta(post_id=coupon_id, meta_key=key, meta_value=str(value))
            self.session.add(meta)

        await self.session.commit()
        return await self.get_coupon(coupon_id)

    async def update_coupon(self, coupon_id: int, data: WCCouponUpdate) -> Optional[WCCouponRead]:
        """Update an existing coupon"""
        stmt = select(WPPost).where(WPPost.ID == coupon_id, WPPost.post_type == "shop_coupon")
        result = await self.session.exec(stmt)
        post = result.first()
        if not post:
            return None

        if data.code: post.post_title = data.code
        if data.description is not None: post.post_excerpt = data.description
        post.post_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.session.add(post)

        # Update meta
        update_meta = self._map_to_meta_partial(data)
        for key, value in update_meta.items():
            meta_stmt = select(WPPostMeta).where(
                WPPostMeta.post_id == coupon_id,
                WPPostMeta.meta_key == key
            )
            existing_meta = (await self.session.exec(meta_stmt)).first()
            if existing_meta:
                existing_meta.meta_value = str(value)
                self.session.add(existing_meta)
            else:
                new_meta = WPPostMeta(post_id=coupon_id, meta_key=key, meta_value=str(value))
                self.session.add(new_meta)

        await self.session.commit()
        return await self.get_coupon(coupon_id)

    async def delete_coupon(self, coupon_id: int) -> bool:
        """Delete a coupon"""
        stmt = select(WPPost).where(WPPost.ID == coupon_id, WPPost.post_type == "shop_coupon")
        result = await self.session.exec(stmt)
        post = result.first()
        if not post:
            return False

        await self.session.delete(post)
        # Cascade delete meta
        meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == coupon_id)
        metas = (await self.session.exec(meta_stmt)).all()
        for m in metas:
            await self.session.delete(m)

        await self.session.commit()
        return True

    def _map_to_coupon_read(self, post: WPPost, meta: Dict[str, str]) -> WCCouponRead:
        """Helper to map post and meta to WCCouponRead"""
        product_ids = []
        if meta.get("product_ids"):
            product_ids = [int(i.strip()) for i in meta["product_ids"].split(",") if i.strip()]

        excl_ids = []
        if meta.get("exclude_product_ids"):
            excl_ids = [int(i.strip()) for i in meta["exclude_product_ids"].split(",") if i.strip()]

        return WCCouponRead(
            id=post.ID,
            code=post.post_title,
            description=post.post_excerpt,
            amount=Decimal(meta.get("coupon_amount", "0.00")),
            discount_type=meta.get("discount_type", "fixed_cart"),
            date_expires=datetime.strptime(meta["expiry_date"], "%Y-%m-%d") if meta.get("expiry_date") else None,
            usage_limit=int(meta.get("usage_limit", 0)) if meta.get("usage_limit") else None,
            usage_limit_per_user=int(meta.get("usage_limit_per_user", 0)) if meta.get("usage_limit_per_user") else None,
            usage_count=int(meta.get("usage_count", 0)),
            free_shipping=meta.get("free_shipping") == "yes",
            product_ids=product_ids,
            excluded_product_ids=excl_ids,
            exclude_sale_items=meta.get("exclude_sale_items") == "yes",
            minimum_amount=Decimal(meta.get("minimum_amount", "0.00")),
            maximum_amount=Decimal(meta.get("maximum_amount", "0.00")),
            individual_use=meta.get("individual_use") == "yes",
            date_created=post.post_date if isinstance(post.post_date, datetime) else datetime.strptime(post.post_date, "%Y-%m-%d %H:%M:%S"),
            date_modified=post.post_modified if isinstance(post.post_modified, datetime) else datetime.strptime(post.post_modified, "%Y-%m-%d %H:%M:%S")
        )

    def _map_to_meta(self, data: WCCouponCreate) -> Dict[str, Any]:
        """Map schema to WooCommerce meta keys"""
        return {
            "discount_type": data.discount_type,
            "coupon_amount": str(data.amount),
            "individual_use": "yes" if data.individual_use else "no",
            "product_ids": ",".join(map(str, data.product_ids)),
            "exclude_product_ids": ",".join(map(str, data.excluded_product_ids)),
            "usage_limit": str(data.usage_limit) if data.usage_limit else "",
            "usage_limit_per_user": str(data.usage_limit_per_user) if data.usage_limit_per_user else "",
            "limit_usage_to_x_items": str(data.limit_usage_to_x_items) if data.limit_usage_to_x_items else "",
            "expiry_date": data.date_expires.strftime("%Y-%m-%d") if data.date_expires else "",
            "free_shipping": "yes" if data.free_shipping else "no",
            "exclude_sale_items": "yes" if data.exclude_sale_items else "no",
            "minimum_amount": str(data.minimum_amount),
            "maximum_amount": str(data.maximum_amount),
            "usage_count": "0"
        }

    def _map_to_meta_partial(self, data: WCCouponUpdate) -> Dict[str, Any]:
        """Map partial update schema to meta keys"""
        meta = {}
        if data.discount_type: meta["discount_type"] = data.discount_type
        if data.amount is not None: meta["coupon_amount"] = str(data.amount)
        if data.individual_use is not None: meta["individual_use"] = "yes" if data.individual_use else "no"
        if data.product_ids is not None: meta["product_ids"] = ",".join(map(str, data.product_ids))
        if data.excluded_product_ids is not None: meta["exclude_product_ids"] = ",".join(map(str, data.excluded_product_ids))
        if data.usage_limit is not None: meta["usage_limit"] = str(data.usage_limit)
        if data.usage_limit_per_user is not None: meta["usage_limit_per_user"] = str(data.usage_limit_per_user)
        if data.date_expires is not None: meta["expiry_date"] = data.date_expires.strftime("%Y-%m-%d") if data.date_expires else ""
        if data.free_shipping is not None: meta["free_shipping"] = "yes" if data.free_shipping else "no"
        if data.exclude_sale_items is not None: meta["exclude_sale_items"] = "yes" if data.exclude_sale_items else "no"
        if data.minimum_amount is not None: meta["minimum_amount"] = str(data.minimum_amount)
        if data.maximum_amount is not None: meta["maximum_amount"] = str(data.maximum_amount)
        return meta


class WCCartRepository:
    """Repository for managing WooCommerce cart and checkout"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._product_repo = WCProductRepository(session)
        self._coupon_repo = WCCouponRepository(session)

    async def get_cart(self, user_id: int, payment_method: Optional[str] = None) -> Dict[str, Any]:
        """Get cart for a user from session data"""
        from app.model.wordpress.woocommerce import WCSession
        import json

        # Try to find user's cart session
        stmt = select(WCSession).where(
            WCSession.session_key == f"user_{user_id}"
        )
        result = await self.session.exec(stmt)
        session = result.first()

        if not session or not session.session_value:
            return {
                "user_id": user_id,
                "items": [],
                "subtotal": 0,
                "discount_total": 0,
                "shipping_total": 0,
                "tax_total": 0,
                "total": 0,
                "item_count": 0,
                "coupon_codes": []
            }

        try:
            # WooCommerce stores serialized PHP data, we'll use JSON for our custom carts
            cart_data = json.loads(session.session_value) if session.session_value else {"items": [], "coupon_codes": []}
            return await self._build_cart_response(user_id, cart_data, payment_method)
        except (json.JSONDecodeError, TypeError):
            return {
                "user_id": user_id,
                "items": [],
                "subtotal": 0,
                "discount_total": 0,
                "shipping_total": 0,
                "tax_total": 0,
                "total": 0,
                "item_count": 0,
                "coupon_codes": []
            }

    async def _build_cart_response(self, user_id: int, cart_data: Dict, payment_method: Optional[str] = None) -> Dict[str, Any]:
        """Build cart response with product details"""
        items = []
        subtotal = 0

        for item in cart_data.get("items", []):
            product = await self._product_repo.get_product(item.get("product_id"))
            if product:
                quantity = item.get("quantity", 1)
                variation_id = item.get("variation_id")

                # If a variation is specified, use its price instead of the parent product price
                price = float(product.price or 0)
                variation_name = None
                if variation_id:
                    variation_meta_stmt = select(WPPostMeta).where(
                        WPPostMeta.post_id == variation_id,
                        WPPostMeta.meta_key.in_(["_price", "_sale_price"])
                    )
                    var_result = await self.session.exec(variation_meta_stmt)
                    var_metas = {m.meta_key: m.meta_value for m in var_result.all()}

                    sale_price = var_metas.get("_sale_price")
                    active_price = var_metas.get("_price")

                    if sale_price and float(sale_price) > 0:
                        price = float(sale_price)
                    elif active_price:
                        try:
                            price = float(active_price)
                        except (ValueError, TypeError):
                            pass

                    # Also fetch variation attributes for display name
                    attr_stmt = select(WPPostMeta).where(
                        WPPostMeta.post_id == variation_id,
                        WPPostMeta.meta_key.like("attribute_%")
                    )
                    attr_result = await self.session.exec(attr_stmt)
                    attrs = attr_result.all()
                    if attrs:
                        attr_values = [a.meta_value for a in attrs if a.meta_value]
                        if attr_values:
                            variation_name = f"{product.name} - {', '.join(attr_values)}"

                line_total = round(price * quantity, 2)
                subtotal += line_total

                items.append({
                    "product_id": product.id,
                    "variation_id": variation_id,
                    "quantity": quantity,
                    "product_name": variation_name or product.name,
                    "product_price": price,
                    "line_total": line_total,
                    "product_image": None,
                    "seller_payment_link": product.seller_payment_link,
                    "whop_payment_link": product.whop_payment_link,
                    "custom_fields": item.get("custom_fields")
                })

        discount_total = 0
        if cart_data.get("coupon_codes"):
            discount_total = await self._calculate_cart_discount(subtotal, items, cart_data["coupon_codes"], payment_method)

        return {
            "user_id": user_id,
            "items": items,
            "subtotal": round(subtotal, 2),
            "discount_total": round(discount_total, 2),
            "shipping_total": cart_data.get("shipping_total", 0),
            "tax_total": cart_data.get("tax_total", 0),
            "total": round(subtotal - discount_total + cart_data.get("shipping_total", 0) + cart_data.get("tax_total", 0), 2),
            "item_count": sum(item.get("quantity", 1) for item in cart_data.get("items", [])),
            "coupon_codes": cart_data.get("coupon_codes", [])
        }

    async def _calculate_cart_discount(self, subtotal: float, items: List[Dict], coupon_codes: List[str], payment_method: Optional[str] = None) -> float:
        """Calculate total discount from multiple coupons"""
        # Discount only applicable for crypto payment
        if payment_method and payment_method.lower() != "crypto":
            return 0.0

        total_discount = 0.0

        for code in coupon_codes:
            coupon = await self._coupon_repo.get_coupon_by_code(code)
            if not coupon:
                continue

            # 1. Minimum/Maximum amount checks
            if coupon.minimum_amount > 0 and subtotal < float(coupon.minimum_amount):
                continue
            if coupon.maximum_amount > 0 and subtotal > float(coupon.maximum_amount):
                continue

            # 2. Expiry check
            if coupon.date_expires and coupon.date_expires < datetime.now():
                continue

            # 3. Usage limit check
            if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
                continue

            # 4. Calculate discount based on type
            if coupon.discount_type == "fixed_cart":
                total_discount += float(coupon.amount)
            elif coupon.discount_type in ["percentage", "percent"]:
                total_discount += (subtotal * (float(coupon.amount) / 100.0))
            elif coupon.discount_type == "fixed_product":
                # Only apply to specific products if defined
                for item in items:
                    if not coupon.product_ids or item["product_id"] in coupon.product_ids:
                        if item["product_id"] not in coupon.excluded_product_ids:
                            total_discount += (float(coupon.amount) * item["quantity"])
            elif coupon.discount_type in ["percentage_product", "percent_product"]:
                for item in items:
                    if not coupon.product_ids or item["product_id"] in coupon.product_ids:
                        if item["product_id"] not in coupon.excluded_product_ids:
                            total_discount += (item["line_total"] * (float(coupon.amount) / 100.0))

        return total_discount

    async def _get_or_create_session(self, user_id: int):
        """Get or create cart session for user"""
        from app.model.wordpress.woocommerce import WCSession
        import time

        stmt = select(WCSession).where(WCSession.session_key == f"user_{user_id}")
        result = await self.session.exec(stmt)
        session = result.first()

        if not session:
            session = WCSession(
                session_key=f"user_{user_id}",
                session_value="{}",
                session_expiry=int(time.time()) + (60 * 60 * 24 * 30)  # 30 days
            )
            self.session.add(session)
            await self.session.commit()
            await self.session.refresh(session)

        return session

    async def _save_cart_data(self, session, cart_data: Dict) -> None:
        """Save cart data to session"""
        import json
        session.session_value = json.dumps(cart_data)
        self.session.add(session)
        await self.session.commit()

    async def add_to_cart(
        self,
        user_id: int,
        product_id: int,
        quantity: int = 1,
        variation_id: Optional[int] = None,
        custom_fields: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Add product to cart"""
        import json

        # Verify product exists
        product = await self._product_repo.get_product(product_id)
        if not product:
            raise ValueError("Product not found")

        session = await self._get_or_create_session(user_id)

        try:
            cart_data = json.loads(session.session_value) if session.session_value else {}
        except (json.JSONDecodeError, TypeError):
            cart_data = {}

        if "items" not in cart_data:
            cart_data["items"] = []

        # Check if product already in cart
        found = False
        target_prod_id = str(product_id)
        target_var_id = str(variation_id or 0)

        for item in cart_data["items"]:
            item_prod_id = str(item.get("product_id"))
            item_var_id = str(item.get("variation_id") or 0)

            if item_prod_id == target_prod_id and item_var_id == target_var_id:
                item["quantity"] = item.get("quantity", 0) + quantity
                found = True
                break

        if not found:
            cart_data["items"].append({
                "product_id": product_id,
                "variation_id": variation_id,
                "quantity": quantity,
                "custom_fields": custom_fields
            })

        await self._save_cart_data(session, cart_data)
        return await self.get_cart(user_id)

    async def update_cart_item(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
        variation_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update cart item quantity. Set quantity to 0 to remove."""
        import json

        session = await self._get_or_create_session(user_id)

        try:
            cart_data = json.loads(session.session_value) if session.session_value else {}
        except (json.JSONDecodeError, TypeError):
            cart_data = {}

        if "items" not in cart_data:
            cart_data["items"] = []

        # Find and update or remove item
        target_prod_id = str(product_id)
        target_var_id = str(variation_id or 0)

        new_items = []
        for item in cart_data["items"]:
            item_prod_id = str(item.get("product_id"))
            item_var_id = str(item.get("variation_id") or 0)

            if item_prod_id == target_prod_id and item_var_id == target_var_id:
                if quantity > 0:
                    new_item = {**item, "quantity": quantity}
                    new_items.append(new_item)
                # if quantity is 0, we just don't append it (remove)
            else:
                new_items.append(item)

        cart_data["items"] = new_items

        await self._save_cart_data(session, cart_data)
        return await self.get_cart(user_id)

    async def remove_from_cart(
        self,
        user_id: int,
        product_id: int,
        variation_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Remove item from cart"""
        return await self.update_cart_item(user_id, product_id, 0, variation_id)

    async def clear_cart(self, user_id: int, payment_method: Optional[str] = None) -> Dict[str, Any]:
        """Clear all items from cart"""
        import json

        session = await self._get_or_create_session(user_id)
        cart_data = {"items": [], "coupon_codes": []}
        await self._save_cart_data(session, cart_data)
        return await self.get_cart(user_id, payment_method=payment_method)

    async def apply_coupon(self, user_id: int, coupon_code: str, payment_method: Optional[str] = None) -> Dict[str, Any]:
        """Apply a coupon to the cart"""
        import json
        from fastapi import HTTPException

        session = await self._get_or_create_session(user_id)

        try:
            cart_data = json.loads(session.session_value) if session.session_value else {}
        except (json.JSONDecodeError, TypeError):
            cart_data = {}

        if "coupon_codes" not in cart_data:
            cart_data["coupon_codes"] = []

        if coupon_code not in cart_data["coupon_codes"]:
            # Validate coupon before adding
            coupon = await self._coupon_repo.get_coupon_by_code(coupon_code)
            if not coupon:
                raise HTTPException(status_code=404, detail="Invalid coupon code")

            cart_data["coupon_codes"].append(coupon_code)

        await self._save_cart_data(session, cart_data)
        return await self.get_cart(user_id, payment_method=payment_method)

    async def remove_coupon(self, user_id: int, coupon_code: str, payment_method: Optional[str] = None) -> Dict[str, Any]:
        """Remove a coupon from the cart"""
        import json

        session = await self._get_or_create_session(user_id)

        try:
            cart_data = json.loads(session.session_value) if session.session_value else {}
        except (json.JSONDecodeError, TypeError):
            cart_data = {}

        if "coupon_codes" in cart_data:
            cart_data["coupon_codes"] = [c for c in cart_data["coupon_codes"] if c != coupon_code]

        await self._save_cart_data(session, cart_data)
        return await self.get_cart(user_id, payment_method=payment_method)

    async def checkout(
        self,
        user_id: int,
        billing_address: Dict[str, Any],
        shipping_address: Optional[Dict[str, Any]] = None,
        payment_method: str = "manual",
        payment_method_title: str = "Manual Payment",
        customer_note: Optional[str] = None,
        custom_fields: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create order from cart"""
        import uuid

        # Get cart
        cart = await self.get_cart(user_id)
        if not cart["items"]:
            raise ValueError("Cart is empty")

        # Determine initial status: free orders are completed immediately
        is_free = float(cart["total"]) == 0 or payment_method == "free"
        initial_status = "completed" if is_free else "pending"

        # Create order
        order = WCOrder(
            status=initial_status,
            currency="USD",
            type="shop_order",
            total_amount=cart["total"],
            tax_amount=cart["tax_total"],
            customer_id=user_id,
            billing_email=billing_address.get("email", ""),
            date_created_gmt=datetime.now(),
            date_updated_gmt=datetime.now(),
            payment_method=payment_method,
            payment_method_title=payment_method_title,
            customer_note=customer_note or ""
        )
        self.session.add(order)
        await self.session.flush() # Get ID without committing yet
        order_id = order.id
        await self.session.commit()
        await self.session.refresh(order)

        # Create addresses
        for addr_type, addr_data in [("billing", billing_address), ("shipping", shipping_address or billing_address)]:
            address = WCOrderAddress(
                order_id=order_id,
                address_type=addr_type,
                first_name=addr_data.get("first_name", ""),
                last_name=addr_data.get("last_name", ""),
                company=addr_data.get("company", ""),
                address_1=addr_data.get("address_1", ""),
                address_2=addr_data.get("address_2", ""),
                city=addr_data.get("city", ""),
                state=addr_data.get("state", ""),
                postcode=addr_data.get("postcode", ""),
                country=addr_data.get("country", ""),
                email=addr_data.get("email", ""),
                phone=addr_data.get("phone", "")
            )
            self.session.add(address)

        # Create order items
        for item in cart["items"]:
            order_item = WCOrderItem(
                order_id=order_id,
                order_item_name=item.get("product_name", "Unknown Product"),
                order_item_type="line_item"
            )
            self.session.add(order_item)
            await self.session.flush() # Get order_item_id

            # Add item meta
            item_meta = [
                ("_product_id", str(item.get("product_id", 0))),
                ("_qty", str(item.get("quantity", 1))),
                ("_line_total", str(item.get("line_total", 0))),
                ("_line_subtotal", str(item.get("line_total", 0)))
            ]
            for meta_key, meta_value in item_meta:
                meta = WCOrderItemMeta(
                    order_item_id=order_item.order_item_id,
                    meta_key=meta_key,
                    meta_value=meta_value
                )
                self.session.add(meta)

            # Save custom fields (e.g. Telegram Username) as order item meta
            if custom_fields:
                for field_name, field_value in custom_fields.items():
                    cf_meta = WCOrderItemMeta(
                        order_item_id=order_item.order_item_id,
                        meta_key=field_name,
                        meta_value=field_value
                    )
                    self.session.add(cf_meta)

        await self.session.commit()
        await self.session.refresh(order)

        # Capture values before clear_cart expires the object again
        order_id = order.id
        order_status = order.status

        # Clear cart
        await self.clear_cart(user_id)

        # Prepare response
        response = {
            "order_id": order_id,
            "order_key": f"wc_order_{uuid.uuid4().hex[:16]}",
            "order_status": order_status,
            "total": float(cart["total"]),
            "payment_url": None,
            "redirect_url": None,
            "message": "Order created successfully"
        }

        # Set redirect URL for alternative payment methods
        if payment_method in ["seller", "whop"]:
            link_key = f"{payment_method}_payment_link"
            # Use the link from the first item in the cart
            for item in cart["items"]:
                if item.get(link_key):
                    response["redirect_url"] = item[link_key]
                    break
        elif payment_method == "crypto":
            from app.service.nowpayments_service import NOWPaymentsService
            from app.schema.crypto_payment import NOWPaymentsInvoiceRequest
            from app.core.config import settings
            from app.core.logging_config import logger

            service = NOWPaymentsService(self.session)
            invoice_data = NOWPaymentsInvoiceRequest(
                price_amount=float(cart["total"]),
                price_currency="usd",
                order_id=str(order_id),
                order_description=f"Order #{order_id} at {settings.APP_NAME}",
                ipn_callback_url=f"{settings.BACKEND_URL}/api/v1/crypto-payments/ipn-callback",
                success_url=f"{settings.FRONTEND_URL}/my-orders/{order_id}",
                cancel_url=f"{settings.FRONTEND_URL}/checkout"
            )
            try:
                invoice = await service.create_invoice(invoice_data, user_id)
                if invoice and hasattr(invoice, "invoice_url"):
                    response["redirect_url"] = invoice.invoice_url
                elif isinstance(invoice, dict) and "invoice_url" in invoice:
                     response["redirect_url"] = invoice["invoice_url"]
            except Exception as e:
                logger.error(f"Failed to create NOWPayments invoice for order {order_id}: {str(e)}")
                # We still return the order_id so the user can see it in their dashboard
                response["message"] = f"Order created, but payment redirection failed: {str(e)}"

        return response

    async def get_user_orders(self, user_id: int, limit: int = 10, offset: int = 0) -> List[Any]:
        """Get orders for a specific user"""
        stmt = select(WCOrder).where(
            WCOrder.customer_id == user_id
        ).order_by(WCOrder.date_created_gmt.desc()).limit(limit).offset(offset)
        result = await self.session.exec(stmt)
        return result.all()

    async def get_user_order_summary(self, user_id: int) -> Dict[str, Any]:
        """Get order summary for a user"""
        orders = await self.get_user_orders(user_id, limit=1000, offset=0)

        total_spent = sum(float(o.total_amount or 0) for o in orders if o.status in ["completed", "processing"])
        pending = sum(1 for o in orders if o.status == "pending")
        processing = sum(1 for o in orders if o.status == "processing")
        completed = sum(1 for o in orders if o.status == "completed")

        return {
            "total_orders": len(orders),
            "total_spent": total_spent,
            "pending_orders": pending,
            "processing_orders": processing,
            "completed_orders": completed
        }


class WCProductReviewRepository:
    """Repository for product reviews"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_product_reviews(self, product_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get reviews for a product"""
        from app.model.wordpress.core import WPComment, WPCommentMeta

        stmt = select(WPComment).where(
            WPComment.comment_post_ID == product_id,
            WPComment.comment_type == "review",
            WPComment.comment_approved == "1"
        ).order_by(WPComment.comment_date.desc()).limit(limit).offset(offset)
        result = await self.session.exec(stmt)
        reviews = result.all()

        output = []
        for review in reviews:
            # Get rating from meta
            meta_stmt = select(WPCommentMeta).where(
                WPCommentMeta.comment_id == review.comment_ID,
                WPCommentMeta.meta_key == "rating"
            )
            meta_result = await self.session.exec(meta_stmt)
            rating_meta = meta_result.first()
            rating = int(rating_meta.meta_value) if rating_meta and rating_meta.meta_value else 0

            # Check if verified purchase
            verified_stmt = select(WPCommentMeta).where(
                WPCommentMeta.comment_id == review.comment_ID,
                WPCommentMeta.meta_key == "verified"
            )
            verified_result = await self.session.exec(verified_stmt)
            verified_meta = verified_result.first()
            verified = verified_meta.meta_value == "1" if verified_meta else False

            output.append({
                "id": review.comment_ID,
                "product_id": review.comment_post_ID,
                "reviewer": review.comment_author,
                "reviewer_email": review.comment_author_email,
                "review": review.comment_content,
                "rating": rating,
                "verified": verified,
                "date_created": review.comment_date,
                "status": "approved" if review.comment_approved == "1" else "pending"
            })

        return output

    async def create_review(
        self,
        product_id: int,
        user_id: int,
        reviewer_name: str,
        reviewer_email: str,
        review: str,
        rating: int,
        ip: str = "",
        user_agent: str = ""
    ) -> Dict[str, Any]:
        """Create a product review"""
        from app.model.wordpress.core import WPComment, WPCommentMeta, WPPost

        # Verify product exists
        product = await self.session.get(WPPost, product_id)
        if not product or product.post_type != "product":
            raise ValueError("Product not found")

        # Create review comment
        new_review = WPComment(
            comment_post_ID=product_id,
            comment_author=reviewer_name,
            comment_author_email=reviewer_email,
            comment_author_url="",
            comment_author_IP=ip,
            comment_content=review,
            comment_date=datetime.now(),
            comment_date_gmt=datetime.now(),
            comment_approved="1",  # Auto-approve
            comment_agent=user_agent,
            comment_type="review",
            comment_parent=0,
            user_id=user_id
        )
        self.session.add(new_review)
        await self.session.commit()
        await self.session.refresh(new_review)

        # Capture needed attributes before next commit expires them
        review_id = new_review.comment_ID
        review_date = new_review.comment_date

        # Add rating meta
        rating_meta = WPCommentMeta(
            comment_id=review_id,
            meta_key="rating",
            meta_value=str(rating)
        )
        self.session.add(rating_meta)

        # Check if verified purchase and add meta
        # TODO: Check if user has purchased this product
        verified_meta = WPCommentMeta(
            comment_id=review_id,
            meta_key="verified",
            meta_value="0"
        )
        self.session.add(verified_meta)

        await self.session.commit()

        # Update product review count and average
        await self._update_product_rating(product_id)

        return {
            "id": review_id,
            "product_id": product_id,
            "reviewer": reviewer_name,
            "reviewer_email": reviewer_email,
            "review": review,
            "rating": rating,
            "verified": False,
            "date_created": review_date,
            "status": "approved"
        }

    async def _update_product_rating(self, product_id: int) -> None:
        """Update product's average rating and review count"""
        from app.model.wordpress.core import WPComment, WPCommentMeta

        # Get all approved reviews
        stmt = select(WPComment).where(
            WPComment.comment_post_ID == product_id,
            WPComment.comment_type == "review",
            WPComment.comment_approved == "1"
        )
        result = await self.session.exec(stmt)
        reviews = result.all()

        if reviews:
            # Get ratings
            ratings = []
            for review in reviews:
                meta_stmt = select(WPCommentMeta).where(
                    WPCommentMeta.comment_id == review.comment_ID,
                    WPCommentMeta.meta_key == "rating"
                )
                meta_result = await self.session.exec(meta_stmt)
                meta = meta_result.first()
                if meta and meta.meta_value:
                    ratings.append(int(meta.meta_value))

            if ratings:
                avg_rating = sum(ratings) / len(ratings)

                # Update product meta lookup
                lookup_stmt = select(WCProductMetaLookup).where(
                    WCProductMetaLookup.product_id == product_id
                )
                lookup_result = await self.session.exec(lookup_stmt)
                lookup = lookup_result.first()

                if lookup:
                    lookup.average_rating = avg_rating
                    lookup.rating_count = len(ratings)
                    self.session.add(lookup)
                    await self.session.commit()


class WCProductCategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_categories(self, parent: int = 0, limit: int = 20, offset: int = 0) -> List[WCProductCategoryRead]:
        """List product categories"""
        stmt = (
            select(WPTerm, WPTermTaxonomy)
            .join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id)
            .where(
                WPTermTaxonomy.taxonomy == "product_cat"
            )
        )

        if parent is not None:
            stmt = stmt.where(WPTermTaxonomy.parent == parent)

        stmt = stmt.limit(limit).offset(offset)
        res = await self.session.exec(stmt)
        return [
            WCProductCategoryRead(
                id=term.term_id,
                name=term.name,
                slug=term.slug,
                description=tax.description,
                parent=tax.parent,
                count=tax.count
            )
            for term, tax in res.all()
        ]

    async def get_category(self, category_id: int) -> Optional[WCProductCategoryRead]:
        """Get single category"""
        stmt = (
            select(WPTerm, WPTermTaxonomy)
            .join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id)
            .where(
                WPTerm.term_id == category_id,
                WPTermTaxonomy.taxonomy == "product_cat"
            )
        )
        res = await self.session.exec(stmt)
        item = res.first()
        if not item:
            return None

        term, tax = item
        return WCProductCategoryRead(
            id=term.term_id,
            name=term.name,
            slug=term.slug,
            description=tax.description,
            parent=tax.parent,
            count=tax.count
        )

    async def create_category(self, data: WCProductCategoryCreate) -> WCProductCategoryRead:
        """Create a new product category"""
        new_term = WPTerm(
            name=data.name,
            slug=data.slug or data.name.lower().replace(" ", "-"),
            term_group=0
        )
        self.session.add(new_term)
        await self.session.flush() # Get ID
        term_id = new_term.term_id

        new_tax = WPTermTaxonomy(
            term_id=term_id,
            taxonomy="product_cat",
            description=data.description or "",
            parent=data.parent or 0,
            count=0
        )
        self.session.add(new_tax)
        await self.session.commit()

        return await self.get_category(term_id)

    async def update_category(self, category_id: int, data: WCProductCategoryUpdate) -> Optional[WCProductCategoryRead]:
        """Update product category"""
        term = await self.session.get(WPTerm, category_id)
        if not term:
            return None

        stmt = select(WPTermTaxonomy).where(
            WPTermTaxonomy.term_id == category_id,
            WPTermTaxonomy.taxonomy == "product_cat"
        )
        res = await self.session.exec(stmt)
        tax = res.first()

        if data.name: term.name = data.name
        if data.slug: term.slug = data.slug
        self.session.add(term)

        if tax:
            if data.description is not None: tax.description = data.description
            if data.parent is not None: tax.parent = data.parent
            self.session.add(tax)

        await self.session.commit()
        return await self.get_category(category_id)

    async def delete_category(self, category_id: int) -> bool:
        """Delete product category"""
        term = await self.session.get(WPTerm, category_id)
        if not term:
            return False

        stmt = select(WPTermTaxonomy).where(
            WPTermTaxonomy.term_id == category_id,
            WPTermTaxonomy.taxonomy == "product_cat"
        )
        res = await self.session.exec(stmt)
        tax = res.first()

        if tax: await self.session.delete(tax)
        await self.session.delete(term)
        await self.session.commit()
        return True
