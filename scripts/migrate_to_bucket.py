#!/usr/bin/env python3
"""
Migrate existing WordPress files from cPanel URLs to Railway S3 bucket.
Does NOT modify the database — the ASSETS_BASE_URL setting will handle
URL rewriting on responses automatically.

Usage:
    1. Set in .env:
         USE_RAILWAY_BUCKET=true
         BUCKET_NAME=...
         BUCKET_ACCESS_KEY_ID=...
         BUCKET_SECRET_ACCESS_KEY=...

    2. Run: python scripts/migrate_to_bucket.py [--dry-run] [--skip-images]
"""
import asyncio
import io
import os
import sys
import logging
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from PIL import Image

from app.core.config import settings
from app.service.storage import storage
from app.model.wordpress.core import WPPost, WPPostMeta

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("migrate_to_bucket")

DRY_RUN = "--dry-run" in sys.argv
SKIP_CONFIRM = "--yes" in sys.argv
SKIP_IMAGES = "--skip-images" in sys.argv


async def download_file(url: str) -> Optional[bytes]:
    import httpx
    # Try with SSL verification first, then without, then fallback to http://
    for attempt, kwargs in [
        ("https+verify", {"verify": True}),
        ("https+no-verify", {"verify": False}),
        ("http", {"verify": False}),
    ]:
        try:
            u = url
            if attempt == "http" and u.startswith("https://"):
                u = "http://" + u[8:]
            async with httpx.AsyncClient(timeout=120, follow_redirects=True, **kwargs) as client:
                resp = await client.get(u)
                resp.raise_for_status()
                if attempt != "https+verify":
                    logger.info("  Downloaded via %s", attempt)
                return resp.content
        except Exception as e:
            if "ssl" in str(e).lower() or "certificate" in str(e).lower() or "wrong_version" in str(e).lower():
                continue  # Try next method
            if attempt == "http":
                logger.error("  Failed to download %s: %s", url, e)
                return None
    logger.error("  Failed to download %s (all methods)", url)
    return None


async def process_attachment(session: AsyncSession, attachment: WPPost) -> dict:
    aid = attachment.ID
    old_guid = attachment.guid
    mime = attachment.post_mime_type or ""

    if "/wp-content/uploads/" in old_guid:
        rel_path = old_guid.split("/wp-content/uploads/")[-1]
    else:
        meta_q = select(WPPostMeta).where(
            WPPostMeta.post_id == aid,
            WPPostMeta.meta_key == "_wp_attached_file"
        )
        meta_r = await session.exec(meta_q)
        meta = meta_r.first()
        rel_path = meta.meta_value if meta else f"file-{aid}"

    s3_key = f"wp-content/uploads/{rel_path}"

    logger.info("[%d] %s → %s", aid, old_guid, s3_key)

    if DRY_RUN:
        return {"status": "dry-run"}

    if await storage.file_exists(s3_key):
        logger.info("  Already exists, skipping")
        return {"status": "skipped"}

    data = await download_file(old_guid)
    if data is None:
        return {"status": "failed"}

    await storage.upload_bytes(data, s3_key, content_type=mime or "application/octet-stream")
    logger.info("  Uploaded")

    if mime.startswith("image/") and not SKIP_IMAGES:
        try:
            sizes = await storage.generate_thumbnails(data, s3_key)
            if sizes:
                logger.info("  +%d thumbnails", len(sizes))
        except Exception as e:
            logger.warning("  Thumbnail generation failed: %s", e)

    return {"status": "migrated"}


async def main():
    if not settings.USE_RAILWAY_BUCKET:
        logger.error("Set USE_RAILWAY_BUCKET=true in .env first!")
        sys.exit(1)

    engine = create_async_engine(settings.WP_DATABASE_URL, echo=False)
    async with AsyncSession(engine) as session:
        q = select(WPPost).where(WPPost.post_type == "attachment").order_by(WPPost.ID)
        r = await session.exec(q)
        attachments = r.all()

        logger.info("Found %d attachments", len(attachments))
        if not attachments:
            return

        if not DRY_RUN and not SKIP_CONFIRM:
            c = input(f"Upload {len(attachments)} files to Railway bucket? [y/N] ")
            if c.lower() != "y":
                return

        stats: dict[str, int] = {}
        for att in attachments:
            result = await process_attachment(session, att)
            k = result.get("status", "failed")
            stats[k] = stats.get(k, 0) + 1

        logger.info("")
        logger.info("=" * 50)
        for k, v in stats.items():
            logger.info("  %s: %d", k, v)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
