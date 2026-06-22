from typing import List, Optional
from datetime import datetime
from sqlalchemy import desc, func
from sqlalchemy.orm import aliased
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model.wordpress.core import WPPost, WPPostMeta
from app.schema.wordpress.signals import SignalRead, SignalCreate, SignalUpdate, SignalPagination
from app.schema.wordpress.trading_tools import TradingToolRead, TradingToolCreate, TradingToolUpdate, TradingToolPagination
from app.schema.wordpress.books import BookRead, BookCreate, BookUpdate, BookPagination
from .posts import WPPostRepository

class DynamicContentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.post_repo = WPPostRepository(session)

    # ============== Signals ==============
    async def get_signals(self, signal_type: Optional[str] = None, limit: int = 20, offset: int = 0) -> SignalPagination:
        stmt = select(WPPost).where(WPPost.post_type == "signal", WPPost.post_status == "publish")

        if signal_type:
            MetaType = aliased(WPPostMeta)
            stmt = stmt.join(MetaType, WPPost.ID == MetaType.post_id).where(
                MetaType.meta_key == "_signal_type",
                MetaType.meta_value == signal_type
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.exec(count_stmt)
        total = total_result.one()

        stmt = stmt.order_by(desc(WPPost.post_date)).limit(limit).offset(offset)
        result = await self.session.exec(stmt)
        posts = result.all()

        signals = []
        for p in posts:
            meta = await self.post_repo.get_post_meta(p.ID)
            meta_dict = {m["meta_key"]: m["meta_value"] for m in meta}

            signals.append(SignalRead(
                id=p.ID,
                title=p.post_title,
                date=p.post_date,
                status=p.post_status,
                instrument=meta_dict.get("_signal_instrument", ""),
                signal_type=meta_dict.get("_signal_type", "free"),
                entry=meta_dict.get("_signal_entry", ""),
                sl=meta_dict.get("_signal_sl", ""),
                tp1=meta_dict.get("_signal_tp1", ""),
                tp2=meta_dict.get("_signal_tp2"),
                price=float(meta_dict.get("_signal_price", 0.0) or 0.0),
                image_url=meta_dict.get("_signal_image_url")
            ))

        return SignalPagination(
            items=signals,
            total=total,
            page=(offset // limit) + 1,
            pageSize=limit
        )

    async def create_signal(self, user_id: int, data: SignalCreate) -> SignalRead:
        new_post = WPPost(
            post_author=user_id,
            post_title=data.title,
            post_status=data.status,
            post_type="signal",
            post_name=data.title.lower().replace(" ", "-"),
            post_date=datetime.now(),
            post_date_gmt=datetime.now(),
            post_modified=datetime.now(),
            post_modified_gmt=datetime.now()
        )
        self.session.add(new_post)
        await self.session.flush()

        post_id = new_post.ID

        # Add meta
        await self.post_repo.set_post_meta(post_id, "_signal_instrument", data.instrument)
        await self.post_repo.set_post_meta(post_id, "_signal_type", data.signal_type)
        await self.post_repo.set_post_meta(post_id, "_signal_entry", data.entry)
        await self.post_repo.set_post_meta(post_id, "_signal_sl", data.sl)
        await self.post_repo.set_post_meta(post_id, "_signal_tp1", data.tp1)
        if data.tp2:
            await self.post_repo.set_post_meta(post_id, "_signal_tp2", data.tp2)
        await self.post_repo.set_post_meta(post_id, "_signal_price", str(data.price or 0.0))
        if data.image_url:
            await self.post_repo.set_post_meta(post_id, "_signal_image_url", data.image_url)

        await self.session.commit()
        return await self.get_signal(post_id)

    async def update_signal(self, signal_id: int, data: SignalUpdate) -> Optional[SignalRead]:
        post = await self.session.get(WPPost, signal_id)
        if not post or post.post_type != "signal":
            return None

        if data.title:
            post.post_title = data.title
        if data.status:
            post.post_status = data.status
        post.post_modified = datetime.now()
        self.session.add(post)

        if data.instrument:
            await self.post_repo.set_post_meta(signal_id, "_signal_instrument", data.instrument)
        if data.signal_type:
            await self.post_repo.set_post_meta(signal_id, "_signal_type", data.signal_type)
        if data.entry:
            await self.post_repo.set_post_meta(signal_id, "_signal_entry", data.entry)
        if data.sl:
            await self.post_repo.set_post_meta(signal_id, "_signal_sl", data.sl)
        if data.tp1:
            await self.post_repo.set_post_meta(signal_id, "_signal_tp1", data.tp1)
        if data.tp2:
            await self.post_repo.set_post_meta(signal_id, "_signal_tp2", data.tp2)
        if data.price is not None:
            await self.post_repo.set_post_meta(signal_id, "_signal_price", str(data.price))
        if data.image_url:
            await self.post_repo.set_post_meta(signal_id, "_signal_image_url", data.image_url)

        await self.session.commit()
        return await self.get_signal(signal_id)

    async def delete_signal(self, signal_id: int) -> bool:
        post = await self.session.get(WPPost, signal_id)
        if not post or post.post_type != "signal":
            return False
        await self.session.delete(post)
        await self.session.commit()
        return True

    async def get_signal(self, signal_id: int) -> Optional[SignalRead]:
        post = await self.session.get(WPPost, signal_id)
        if not post or post.post_type != "signal":
            return None

        meta = await self.post_repo.get_post_meta(post.ID)
        meta_dict = {m["meta_key"]: m["meta_value"] for m in meta}

        return SignalRead(
            id=post.ID,
            title=post.post_title,
            date=post.post_date,
            status=post.post_status,
            instrument=meta_dict.get("_signal_instrument", ""),
            signal_type=meta_dict.get("_signal_type", "free"),
            entry=meta_dict.get("_signal_entry", ""),
            sl=meta_dict.get("_signal_sl", ""),
            tp1=meta_dict.get("_signal_tp1", ""),
            tp2=meta_dict.get("_signal_tp2"),
            price=float(meta_dict.get("_signal_price", 0.0)),
            image_url=meta_dict.get("_signal_image_url")
        )

    # ============== Trading Tools ==============
    async def get_trading_tools(self, tool_type: Optional[str] = None, category: Optional[str] = None, limit: int = 50, offset: int = 0) -> TradingToolPagination:
        stmt = select(WPPost).where(WPPost.post_type == "trading_tool", WPPost.post_status == "publish")

        # SQL-level filtering for better performance and to fix "limit before filter" bug
        if tool_type:
            MetaType = aliased(WPPostMeta)
            stmt = stmt.join(MetaType, WPPost.ID == MetaType.post_id).where(
                MetaType.meta_key == "_tool_type",
                MetaType.meta_value == tool_type
            )

        if category:
            MetaCat = aliased(WPPostMeta)
            stmt = stmt.join(MetaCat, WPPost.ID == MetaCat.post_id).where(
                MetaCat.meta_key == "_tool_category",
                MetaCat.meta_value == category
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.exec(count_stmt)
        total = total_result.one()

        stmt = stmt.order_by(desc(WPPost.post_date)).limit(limit).offset(offset)
        result = await self.session.exec(stmt)
        posts = result.all()

        tools = []
        for p in posts:
            meta = await self.post_repo.get_post_meta(p.ID)
            meta_dict = {m["meta_key"]: m["meta_value"] for m in meta}

            tools.append(TradingToolRead(
                id=p.ID,
                title=p.post_title,
                status=p.post_status,
                tool_type=meta_dict.get("_tool_type", ""),
                category=meta_dict.get("_tool_category", "free"),
                description=meta_dict.get("_tool_description", ""),
                price=float(meta_dict.get("_tool_price", 0.0) or 0.0),
                image_url=meta_dict.get("_tool_image_url"),
                download_url=meta_dict.get("_tool_download_url"),
                purchase_url=meta_dict.get("_tool_purchase_url"),
                seller_payment_link=meta_dict.get("_tool_seller_payment_link"),
                whop_payment_link=meta_dict.get("_tool_whop_payment_link")
            ))

        return TradingToolPagination(
            items=tools,
            total=total,
            page=(offset // limit) + 1,
            pageSize=limit
        )

    async def create_trading_tool(self, user_id: int, data: TradingToolCreate) -> TradingToolRead:
        new_post = WPPost(
            post_author=user_id,
            post_title=data.title,
            post_status=data.status,
            post_type="trading_tool",
            post_name=data.title.lower().replace(" ", "-"),
            post_date=datetime.now(),
            post_modified=datetime.now()
        )
        self.session.add(new_post)
        await self.session.flush()

        post_id = new_post.ID

        await self.post_repo.set_post_meta(post_id, "_tool_type", data.tool_type)
        await self.post_repo.set_post_meta(post_id, "_tool_category", data.category)
        await self.post_repo.set_post_meta(post_id, "_tool_description", data.description or "")
        if data.download_url:
            await self.post_repo.set_post_meta(post_id, "_tool_download_url", data.download_url)
        if data.purchase_url:
            await self.post_repo.set_post_meta(post_id, "_tool_purchase_url", data.purchase_url)
        if data.seller_payment_link:
            await self.post_repo.set_post_meta(post_id, "_tool_seller_payment_link", data.seller_payment_link)
        if data.whop_payment_link:
            await self.post_repo.set_post_meta(post_id, "_tool_whop_payment_link", data.whop_payment_link)
        await self.post_repo.set_post_meta(post_id, "_tool_price", str(data.price or 0.0))
        if data.image_url:
            await self.post_repo.set_post_meta(post_id, "_tool_image_url", data.image_url)

        await self.session.commit()
        return await self.get_trading_tool(post_id)

    async def update_trading_tool(self, tool_id: int, data: TradingToolUpdate) -> Optional[TradingToolRead]:
        post = await self.session.get(WPPost, tool_id)
        if not post or post.post_type != "trading_tool":
            return None

        if data.title:
            post.post_title = data.title
        if data.status:
            post.post_status = data.status
        post.post_modified = datetime.now()
        self.session.add(post)

        if data.tool_type:
            await self.post_repo.set_post_meta(tool_id, "_tool_type", data.tool_type)
        if data.category:
            await self.post_repo.set_post_meta(tool_id, "_tool_category", data.category)
        if data.description is not None:
            await self.post_repo.set_post_meta(tool_id, "_tool_description", data.description)
        if data.download_url:
            await self.post_repo.set_post_meta(tool_id, "_tool_download_url", data.download_url)
        if data.purchase_url:
            await self.post_repo.set_post_meta(tool_id, "_tool_purchase_url", data.purchase_url)
        if data.seller_payment_link is not None:
            await self.post_repo.set_post_meta(tool_id, "_tool_seller_payment_link", data.seller_payment_link)
        if data.whop_payment_link is not None:
            await self.post_repo.set_post_meta(tool_id, "_tool_whop_payment_link", data.whop_payment_link)
        if data.price is not None:
            await self.post_repo.set_post_meta(tool_id, "_tool_price", str(data.price))
        if data.image_url:
            await self.post_repo.set_post_meta(tool_id, "_tool_image_url", data.image_url)

        await self.session.commit()
        return await self.get_trading_tool(tool_id)

    async def delete_trading_tool(self, tool_id: int) -> bool:
        post = await self.session.get(WPPost, tool_id)
        if not post or post.post_type != "trading_tool":
            return False
        await self.session.delete(post)
        await self.session.commit()
        return True

    async def get_trading_tool(self, tool_id: int) -> Optional[TradingToolRead]:
        post = await self.session.get(WPPost, tool_id)
        if not post or post.post_type != "trading_tool":
            return None

        meta = await self.post_repo.get_post_meta(post.ID)
        meta_dict = {m["meta_key"]: m["meta_value"] for m in meta}

        return TradingToolRead(
            id=post.ID,
            title=post.post_title,
            status=post.post_status,
            tool_type=meta_dict.get("_tool_type", ""),
            category=meta_dict.get("_tool_category", "free"),
            description=meta_dict.get("_tool_description", ""),
            price=float(meta_dict.get("_tool_price", 0.0)),
            image_url=meta_dict.get("_tool_image_url"),
            download_url=meta_dict.get("_tool_download_url"),
            purchase_url=meta_dict.get("_tool_purchase_url"),
            seller_payment_link=meta_dict.get("_tool_seller_payment_link"),
            whop_payment_link=meta_dict.get("_tool_whop_payment_link")
        )

    # ============== Books ==============
    async def get_books(self, is_free: Optional[bool] = None, limit: int = 50, offset: int = 0) -> BookPagination:
        stmt = select(WPPost).where(WPPost.post_type == "forex_book", WPPost.post_status == "publish")

        if is_free is not None:
            MetaFree = aliased(WPPostMeta)
            stmt = stmt.join(MetaFree, WPPost.ID == MetaFree.post_id).where(
                MetaFree.meta_key == "_book_is_free",
                MetaFree.meta_value == ("1" if is_free else "0")
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.exec(count_stmt)
        total = total_result.one()

        stmt = stmt.order_by(desc(WPPost.post_date)).limit(limit).offset(offset)
        result = await self.session.exec(stmt)
        posts = result.all()

        books = []
        for p in posts:
            meta = await self.post_repo.get_post_meta(p.ID)
            meta_dict = {m["meta_key"]: m["meta_value"] for m in meta}

            books.append(BookRead(
                id=p.ID,
                title=p.post_title,
                status=p.post_status,
                is_free=meta_dict.get("_book_is_free") == "1",
                description=meta_dict.get("_book_description", ""),
                price=float(meta_dict.get("_book_price", 0.0) or 0.0),
                image_url=meta_dict.get("_book_image_url"),
                download_url=meta_dict.get("_book_download_url"),
                purchase_url=meta_dict.get("_book_purchase_url"),
                seller_payment_link=meta_dict.get("_book_seller_payment_link"),
                whop_payment_link=meta_dict.get("_book_whop_payment_link")
            ))

        return BookPagination(
            items=books,
            total=total,
            page=(offset // limit) + 1,
            pageSize=limit
        )

    async def create_book(self, user_id: int, data: BookCreate) -> BookRead:
        new_post = WPPost(
            post_author=user_id,
            post_title=data.title,
            post_status=data.status,
            post_type="forex_book",
            post_name=data.title.lower().replace(" ", "-"),
            post_date=datetime.now(),
            post_modified=datetime.now()
        )
        self.session.add(new_post)
        await self.session.flush()

        post_id = new_post.ID

        await self.post_repo.set_post_meta(post_id, "_book_is_free", "1" if data.is_free else "0")
        await self.post_repo.set_post_meta(post_id, "_book_description", data.description or "")
        if data.download_url:
            await self.post_repo.set_post_meta(post_id, "_book_download_url", data.download_url)
        if data.purchase_url:
            await self.post_repo.set_post_meta(post_id, "_book_purchase_url", data.purchase_url)
        if data.seller_payment_link:
            await self.post_repo.set_post_meta(post_id, "_book_seller_payment_link", data.seller_payment_link)
        if data.whop_payment_link:
            await self.post_repo.set_post_meta(post_id, "_book_whop_payment_link", data.whop_payment_link)
        await self.post_repo.set_post_meta(post_id, "_book_price", str(data.price or 0.0))
        if data.image_url:
            await self.post_repo.set_post_meta(post_id, "_book_image_url", data.image_url)

        await self.session.commit()
        return await self.get_book(post_id)

    async def update_book(self, book_id: int, data: BookUpdate) -> Optional[BookRead]:
        post = await self.session.get(WPPost, book_id)
        if not post or post.post_type != "forex_book":
            return None

        if data.title:
            post.post_title = data.title
        if data.status:
            post.post_status = data.status
        post.post_modified = datetime.now()
        self.session.add(post)

        if data.is_free is not None:
            await self.post_repo.set_post_meta(book_id, "_book_is_free", "1" if data.is_free else "0")
        if data.description is not None:
            await self.post_repo.set_post_meta(book_id, "_book_description", data.description)
        if data.download_url:
            await self.post_repo.set_post_meta(book_id, "_book_download_url", data.download_url)
        if data.purchase_url:
            await self.post_repo.set_post_meta(book_id, "_book_purchase_url", data.purchase_url)
        if data.seller_payment_link is not None:
            await self.post_repo.set_post_meta(book_id, "_book_seller_payment_link", data.seller_payment_link)
        if data.whop_payment_link is not None:
            await self.post_repo.set_post_meta(book_id, "_book_whop_payment_link", data.whop_payment_link)
        if data.price is not None:
            await self.post_repo.set_post_meta(book_id, "_book_price", str(data.price))
        if data.image_url:
            await self.post_repo.set_post_meta(book_id, "_book_image_url", data.image_url)

        await self.session.commit()
        return await self.get_book(book_id)

    async def delete_book(self, book_id: int) -> bool:
        post = await self.session.get(WPPost, book_id)
        if not post or post.post_type != "forex_book":
            return False
        await self.session.delete(post)
        await self.session.commit()
        return True

    async def get_book(self, book_id: int) -> Optional[BookRead]:
        post = await self.session.get(WPPost, book_id)
        if not post or post.post_type != "forex_book":
            return None

        meta = await self.post_repo.get_post_meta(post.ID)
        meta_dict = {m["meta_key"]: m["meta_value"] for m in meta}

        return BookRead(
            id=post.ID,
            title=post.post_title,
            status=post.post_status,
            is_free=meta_dict.get("_book_is_free") == "1",
            description=meta_dict.get("_book_description", ""),
            price=float(meta_dict.get("_book_price", 0.0)),
            image_url=meta_dict.get("_book_image_url"),
            download_url=meta_dict.get("_book_download_url"),
            purchase_url=meta_dict.get("_book_purchase_url"),
            seller_payment_link=meta_dict.get("_book_seller_payment_link"),
            whop_payment_link=meta_dict.get("_book_whop_payment_link")
        )

    # ============== Videos ==============
    async def get_trading_videos(self, limit: int = 10) -> List[dict]:
        stmt = select(WPPost).where(WPPost.post_type == "trading_video", WPPost.post_status == "publish")
        stmt = stmt.order_by(WPPost.post_date.desc()).limit(limit)
        result = await self.session.exec(stmt)
        posts = result.all()

        videos = []
        for p in posts:
            meta = await self.post_repo.get_post_meta(p.ID)
            meta_dict = {m["meta_key"]: m["meta_value"] for m in meta}

            videos.append({
                "id": meta_dict.get("_video_youtube_id", ""),
                "title": p.post_title,
                "thumbnail": meta_dict.get("_video_thumbnail_url", "")
            })
        return videos

    async def create_trading_video(self, user_id: int, title: str, youtube_id: str, thumbnail: str) -> dict:
        new_post = WPPost(
            post_author=user_id,
            post_title=title,
            post_status="publish",
            post_type="trading_video",
            post_name=title.lower().replace(" ", "-"),
            post_date=datetime.now(),
            post_modified=datetime.now()
        )
        self.session.add(new_post)
        await self.session.flush()

        post_id = new_post.ID

        await self.post_repo.set_post_meta(post_id, "_video_youtube_id", youtube_id)
        await self.post_repo.set_post_meta(post_id, "_video_thumbnail_url", thumbnail)

        await self.session.commit()
        return {
            "id": youtube_id,
            "title": title,
            "thumbnail": thumbnail
        }
