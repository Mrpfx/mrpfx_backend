import asyncio
from sqlmodel import select
from app.db.session import get_session
from app.model.wordpress.core import WPPost

async def run():
    async for session in get_session():
        query = select(WPPost).where(WPPost.post_type == "attachment").order_by(WPPost.ID.desc()).limit(5)
        result = await session.exec(query)
        for post in result.all():
            print(f"ID: {post.ID}, guid: {post.guid}")
        break

asyncio.run(run())
