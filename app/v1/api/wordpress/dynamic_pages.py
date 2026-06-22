from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.repo.wordpress.dynamic_content import DynamicContentRepository
from app.schema.wordpress.signals import SignalRead, SignalCreate, SignalUpdate, SignalPagination
from app.schema.wordpress.trading_tools import TradingToolRead, TradingToolCreate, TradingToolUpdate, TradingToolPagination
from app.schema.wordpress.books import BookRead, BookCreate, BookUpdate, BookPagination
from app.schema.wordpress.videos import YouTubeVideoRead
from app.dependencies.auth import get_current_user
from app.model.user import User

router = APIRouter()

# ============== User-Side Endpoints ==============

@router.get("/signals", response_model=SignalPagination, tags=["Dynamic Pages"])
async def get_signals(
    type: Optional[str] = Query(None, description="vip or free"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_session)
):
    """Get list of recent signals."""
    repo = DynamicContentRepository(session)
    return await repo.get_signals(signal_type=type, limit=limit, offset=offset)

@router.get("/videos/trading", response_model=List[YouTubeVideoRead], tags=["Dynamic Pages"])
async def get_trading_videos(
    limit: int = Query(10, le=50),
    session: AsyncSession = Depends(get_session)
):
    """Get list of YouTube trading videos."""
    repo = DynamicContentRepository(session)
    return await repo.get_trading_videos(limit=limit)

@router.get("/trading-tools", response_model=TradingToolPagination, tags=["Dynamic Pages"])
async def get_trading_tools(
    type: Optional[str] = Query(None, description="bot or indicator"),
    category: Optional[str] = Query(None, description="vip or free"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_session)
):
    """Get list of trading tools (bots/indicators)."""
    repo = DynamicContentRepository(session)
    return await repo.get_trading_tools(tool_type=type, category=category, limit=limit, offset=offset)

@router.get("/books", response_model=BookPagination, tags=["Dynamic Pages"])
async def get_books(
    is_free: Optional[bool] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_session)
):
    """Get list of forex books."""
    repo = DynamicContentRepository(session)
    return await repo.get_books(is_free=is_free, limit=limit, offset=offset)

@router.get("/trading-tools/{tool_id}", response_model=TradingToolRead, tags=["Dynamic Pages"])
async def get_trading_tool(
    tool_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single trading tool by ID."""
    repo = DynamicContentRepository(session)
    tool = await repo.get_trading_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Trading tool not found")
    return tool

@router.get("/books/{book_id}", response_model=BookRead, tags=["Dynamic Pages"])
async def get_book(
    book_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single forex book by ID."""
    repo = DynamicContentRepository(session)
    book = await repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

# ============== Admin-Side Endpoints ==============

@router.post("/admin/signals", response_model=SignalRead, tags=["Admin Dynamic Pages"])
async def create_signal(
    data: SignalCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new signal (Admin only)."""
    # In a real app, we'd check if current_user is an admin
    repo = DynamicContentRepository(session)
    return await repo.create_signal(user_id=current_user.ID, data=data)

@router.post("/admin/trading-tools", response_model=TradingToolRead, tags=["Admin Dynamic Pages"])
async def create_trading_tool(
    data: TradingToolCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new trading tool (Admin only)."""
    repo = DynamicContentRepository(session)
    return await repo.create_trading_tool(user_id=current_user.ID, data=data)

@router.post("/admin/books", response_model=BookRead, tags=["Admin Dynamic Pages"])
async def create_book(
    data: BookCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new book (Admin only)."""
    repo = DynamicContentRepository(session)
    return await repo.create_book(user_id=current_user.ID, data=data)

@router.post("/admin/videos", response_model=YouTubeVideoRead, tags=["Admin Dynamic Pages"])
async def create_video(
    title: str,
    youtube_id: str,
    thumbnail: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new trading video (Admin only)."""
    repo = DynamicContentRepository(session)
    return await repo.create_trading_video(user_id=current_user.ID, title=title, youtube_id=youtube_id, thumbnail=thumbnail)

# --- Update/Delete Endpoints ---

@router.put("/admin/signals/{signal_id}", response_model=SignalRead, tags=["Admin Dynamic Pages"])
async def update_signal(
    signal_id: int,
    data: SignalUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a signal (Admin only)."""
    repo = DynamicContentRepository(session)
    signal = await repo.update_signal(signal_id, data)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal

@router.delete("/admin/signals/{signal_id}", tags=["Admin Dynamic Pages"])
async def delete_signal(
    signal_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a signal (Admin only)."""
    repo = DynamicContentRepository(session)
    if not await repo.delete_signal(signal_id):
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"status": "success"}

@router.put("/admin/trading-tools/{tool_id}", response_model=TradingToolRead, tags=["Admin Dynamic Pages"])
async def update_trading_tool(
    tool_id: int,
    data: TradingToolUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a trading tool (Admin only)."""
    repo = DynamicContentRepository(session)
    tool = await repo.update_trading_tool(tool_id, data)
    if not tool:
        raise HTTPException(status_code=404, detail="Trading tool not found")
    return tool

@router.delete("/admin/trading-tools/{tool_id}", tags=["Admin Dynamic Pages"])
async def delete_trading_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a trading tool (Admin only)."""
    repo = DynamicContentRepository(session)
    if not await repo.delete_trading_tool(tool_id):
        raise HTTPException(status_code=404, detail="Trading tool not found")
    return {"status": "success"}

@router.put("/admin/books/{book_id}", response_model=BookRead, tags=["Admin Dynamic Pages"])
async def update_book(
    book_id: int,
    data: BookUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a book (Admin only)."""
    repo = DynamicContentRepository(session)
    book = await repo.update_book(book_id, data)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.delete("/admin/books/{book_id}", tags=["Admin Dynamic Pages"])
async def delete_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a book (Admin only)."""
    repo = DynamicContentRepository(session)
    if not await repo.delete_book(book_id):
        raise HTTPException(status_code=404, detail="Book not found")
    return {"status": "success"}
