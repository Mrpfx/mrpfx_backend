"""
WordPress Media/Attachments Repository.
Provides CRUD operations for WordPress media attachments.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import re
from PIL import Image
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model.wordpress.core import WPPost, WPPostMeta
from app.core.urls import rewrite_url


class WPMediaRepository:
    """Repository for WordPress media attachments"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Get list of media attachments
    async def get_attachments(
        self,
        mime_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of media attachments with optional filters"""
        query = select(WPPost).where(WPPost.post_type == "attachment")

        if mime_type:
            query = query.where(WPPost.post_mime_type.like(f"{mime_type}%"))

        if search:
            query = query.where(
                WPPost.post_title.ilike(f"%{search}%") |
                WPPost.post_name.ilike(f"%{search}%")
            )

        query = query.order_by(WPPost.post_date.desc()).offset(offset).limit(limit)
        result = await self.session.exec(query)
        attachments = result.all()

        media_list = []
        for attachment in attachments:
            media_data = await self._build_media_response(attachment)
            media_list.append(media_data)

        return media_list

    # Get a single attachment by ID
    async def get_attachment(self, attachment_id: int) -> Optional[Dict[str, Any]]:
        """Get a single media attachment by ID"""
        query = select(WPPost).where(
            WPPost.ID == attachment_id,
            WPPost.post_type == "attachment"
        )
        result = await self.session.exec(query)
        attachment = result.first()

        if not attachment:
            return None

        return await self._build_media_response(attachment)

    # Create a new attachment record
    async def create_attachment(
        self,
        user_id: int,
        filename: str,
        mime_type: str,
        guid: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        alt_text: Optional[str] = None,
        caption: Optional[str] = None,
        s3_key: Optional[str] = None,
        file_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """Create a new media attachment record

        Args:
            s3_key: S3 object key (for Railway bucket storage)
            file_bytes: Raw file bytes (for S3-based image processing)
        """
        now = datetime.now()

        attachment = WPPost(
            post_author=user_id,
            post_date=now,
            post_date_gmt=now,
            post_content=description or "",
            post_title=title or filename,
            post_excerpt=caption or "",
            post_status="inherit",
            post_type="attachment",
            post_name=filename.replace(" ", "-").lower(),
            post_modified=now,
            post_modified_gmt=now,
            post_parent=0,
            guid=guid,
            post_mime_type=mime_type,
            comment_status="open",
            ping_status="closed"
        )

        self.session.add(attachment)
        await self.session.commit()
        await self.session.refresh(attachment)

        attachment_id = attachment.ID

        if alt_text:
            await self._set_attachment_meta(attachment_id, "_wp_attachment_alt_text", alt_text)

        if s3_key:
            await self._set_attachment_meta(attachment_id, "_wp_attached_file", s3_key)
        else:
            relative_path = guid.split("/wp-content/uploads/")[-1] if "/wp-content/uploads/" in guid else filename
            await self._set_attachment_meta(attachment_id, "_wp_attached_file", relative_path)

        if mime_type.startswith("image/"):
            try:
                if s3_key and file_bytes:
                    from app.service.storage import storage
                    sizes_meta = await storage.generate_thumbnails(file_bytes, s3_key)
                    if sizes_meta:
                        metadata = self._serialize_image_metadata(
                            file_bytes, s3_key, sizes_meta
                        )
                        if metadata:
                            await self._set_attachment_meta(attachment_id, "_wp_attachment_metadata", metadata)
                else:
                    relative_path = guid.split("/wp-content/uploads/")[-1] if "/wp-content/uploads/" in guid else filename
                    abs_path = os.path.join("wp-content/uploads", relative_path)
                    metadata = await self._generate_image_metadata(abs_path, relative_path)
                    if metadata:
                        await self._set_attachment_meta(attachment_id, "_wp_attachment_metadata", metadata)
            except Exception as e:
                print(f"Error generating image metadata: {e}")

        return await self._build_media_response(attachment)

    # Update an attachment
    async def update_attachment(
        self,
        attachment_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        alt_text: Optional[str] = None,
        caption: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update a media attachment"""
        query = select(WPPost).where(
            WPPost.ID == attachment_id,
            WPPost.post_type == "attachment"
        )
        result = await self.session.exec(query)
        attachment = result.first()

        if not attachment:
            return None

        if title is not None:
            attachment.post_title = title
        if description is not None:
            attachment.post_content = description
        if caption is not None:
            attachment.post_excerpt = caption

        attachment.post_modified = datetime.now()
        attachment.post_modified_gmt = datetime.now()

        self.session.add(attachment)

        if alt_text is not None:
            await self._set_attachment_meta(attachment_id, "_wp_attachment_alt_text", alt_text)

        attachment_id = attachment.ID
        await self.session.commit()

        return await self.get_attachment(attachment_id)

    # Delete an attachment
    async def delete_attachment(self, attachment_id: int, force: bool = False) -> bool:
        """Delete a media attachment"""
        query = select(WPPost).where(
            WPPost.ID == attachment_id,
            WPPost.post_type == "attachment"
        )
        result = await self.session.exec(query)
        attachment = result.first()

        if not attachment:
            return False

        if force and settings.USE_RAILWAY_BUCKET:
            from app.service.storage import storage
            s3_key_meta = await self._get_attachment_meta(attachment_id, "_wp_attached_file")
            if s3_key_meta:
                keys_to_delete = [s3_key_meta]
                metadata_meta = await self._get_attachment_meta(attachment_id, "_wp_attachment_metadata")
                if metadata_meta:
                    for size in ["thumbnail", "medium", "large"]:
                        pattern = rf's:{len(size)}:"{size}";a:4:{{s:4:"file";s:\d+:"([^"]+)"'
                        match = re.search(pattern, metadata_meta)
                        if match:
                            base_dir = s3_key_meta.rsplit("/", 1)[0] if "/" in s3_key_meta else ""
                            thumb_key = f"{base_dir}/{match.group(1)}"
                            keys_to_delete.append(thumb_key)
                await storage.delete_files(keys_to_delete)

        if force:
            meta_query = select(WPPostMeta).where(WPPostMeta.post_id == attachment_id)
            meta_result = await self.session.exec(meta_query)
            for meta in meta_result.all():
                await self.session.delete(meta)

            await self.session.delete(attachment)
        else:
            attachment.post_status = "trash"
            self.session.add(attachment)

        await self.session.commit()
        return True

    # Get attachment URL with different sizes
    async def get_attachment_urls(self, attachment_id: int) -> Dict[str, str]:
        """Get all available URLs for an attachment (different sizes)"""
        query = select(WPPost).where(
            WPPost.ID == attachment_id,
            WPPost.post_type == "attachment"
        )
        result = await self.session.exec(query)
        attachment = result.first()

        if not attachment:
            return {}

        base_url = rewrite_url(attachment.guid)

        meta_query = select(WPPostMeta).where(
            WPPostMeta.post_id == attachment_id,
            WPPostMeta.meta_key == "_wp_attachment_metadata"
        )
        meta_result = await self.session.exec(meta_query)
        meta = meta_result.first()

        urls = {"full": base_url}

        if meta and meta.meta_value:
            base_dir_url = base_url.rsplit("?", 1)[0].rsplit("/", 1)[0]

            sizes = ["thumbnail", "medium", "large"]
            for size in sizes:
                pattern = rf's:{len(size)}:"{size}";a:4:{{s:4:"file";s:\d+:"([^"]+)"'
                match = re.search(pattern, meta.meta_value)
                if match:
                    urls[size] = f"{base_dir_url}/{match.group(1)}"

        return urls

    # Helper: Generate image metadata and resized versions
    async def _generate_image_metadata(self, file_path: str, relative_path: str) -> Optional[str]:
        """Generate multiple image sizes and return serialized WP metadata (local filesystem)"""
        if not os.path.exists(file_path):
            return None

        try:
            with Image.open(file_path) as img:
                width, height = img.size
                mime_type = f"image/{img.format.lower()}"

                target_sizes = {
                    "thumbnail": (150, 150, True),
                    "medium": (300, 300, False),
                    "large": (1024, 1024, False)
                }

                file_dir = os.path.dirname(file_path)
                file_base, file_ext = os.path.splitext(os.path.basename(file_path))

                sizes_meta = {}

                for size_name, (tw, th, crop) in target_sizes.items():
                    if width > tw or height > th:
                        resized_img = img.copy()
                        if crop:
                            w_ratio = tw / width
                            h_ratio = th / height
                            ratio = max(w_ratio, h_ratio)
                            new_size = (int(width * ratio), int(height * ratio))
                            resized_img = resized_img.resize(new_size, Image.LANCZOS)
                            left = (resized_img.width - tw) / 2
                            top = (resized_img.height - th) / 2
                            resized_img = resized_img.crop((left, top, left + tw, top + th))
                            rw, rh = tw, th
                        else:
                            resized_img.thumbnail((tw, th), Image.LANCZOS)
                            rw, rh = resized_img.size

                        resized_filename = f"{file_base}-{rw}x{rh}{file_ext}"
                        resized_path = os.path.join(file_dir, resized_filename)
                        resized_img.save(resized_path)

                        sizes_meta[size_name] = {
                            "file": resized_filename,
                            "width": rw,
                            "height": rh,
                            "mime-type": mime_type
                        }

                def serialize_size(name, data):
                    return (f's:{len(name)}:"{name}";a:4:{{'
                            f's:4:"file";s:{len(data["file"])}:"{data["file"]}";'
                            f's:5:"width";i:{data["width"]};'
                            f's:6:"height";i:{data["height"]};'
                            f's:9:"mime-type";s:{len(data["mime-type"])}:"{data["mime-type"]}";}}')

                sizes_str = "".join([serialize_size(k, v) for k, v in sizes_meta.items()])

                metadata = (f'a:5:{{s:5:"width";i:{width};s:6:"height";i:{height};'
                           f's:4:"file";s:{len(relative_path)}:"{relative_path}";'
                           f's:5:"sizes";a:{len(sizes_meta)}:{{{sizes_str}}}'
                           f's:10:"image_meta";a:0:{{}}}}')

                return metadata
        except Exception as e:
            print(f"Error in _generate_image_metadata: {e}")
            return None

    def _serialize_image_metadata(self, file_bytes: bytes, s3_key: str, sizes_meta: dict) -> str:
        """Build PHP-serialized WP metadata string from S3-sized images."""
        from PIL import Image as PILImage
        import io
        with PILImage.open(io.BytesIO(file_bytes)) as img:
            width, height = img.size

        def serialize_size(name, data):
            return (f's:{len(name)}:"{name}";a:4:{{'
                    f's:4:"file";s:{len(data["file"])}:"{data["file"]}";'
                    f's:5:"width";i:{data["width"]};'
                    f's:6:"height";i:{data["height"]};'
                    f's:9:"mime-type";s:{len(data["mime-type"])}:"{data["mime-type"]}";}}')

        sizes_str = "".join([serialize_size(k, v) for k, v in sizes_meta.items()])

        return (f'a:5:{{s:5:"width";i:{width};s:6:"height";i:{height};'
                f's:4:"file";s:{len(s3_key)}:"{s3_key}";'
                f's:5:"sizes";a:{len(sizes_meta)}:{{{sizes_str}}}'
                f's:10:"image_meta";a:0:{{}}}}')

    # Helper: Build media response
    async def _build_media_response(self, attachment: WPPost) -> Dict[str, Any]:
        """Build a complete media response with all metadata"""
        alt_meta = await self._get_attachment_meta(attachment.ID, "_wp_attachment_alt_text")

        urls = await self.get_attachment_urls(attachment.ID)

        return {
            "id": attachment.ID,
            "title": attachment.post_title,
            "description": attachment.post_content,
            "caption": attachment.post_excerpt,
            "alt_text": alt_meta or "",
            "url": urls.get("full") or rewrite_url(attachment.guid),
            "mime_type": attachment.post_mime_type,
            "date_created": attachment.post_date,
            "date_modified": attachment.post_modified,
            "author": attachment.post_author,
            "sizes": {k: rewrite_url(v) for k, v in urls.items()},
            "slug": attachment.post_name
        }

    # Helper: Get attachment meta
    async def _get_attachment_meta(self, attachment_id: int, meta_key: str) -> Optional[str]:
        """Get a single meta value for an attachment"""
        query = select(WPPostMeta).where(
            WPPostMeta.post_id == attachment_id,
            WPPostMeta.meta_key == meta_key
        )
        result = await self.session.exec(query)
        meta = result.first()
        return meta.meta_value if meta else None

    # Helper: Set attachment meta
    async def _set_attachment_meta(self, attachment_id: int, meta_key: str, meta_value: str) -> None:
        """Set or update a meta value for an attachment"""
        query = select(WPPostMeta).where(
            WPPostMeta.post_id == attachment_id,
            WPPostMeta.meta_key == meta_key
        )
        result = await self.session.exec(query)
        meta = result.first()

        if meta:
            meta.meta_value = meta_value
            self.session.add(meta)
        else:
            new_meta = WPPostMeta(
                post_id=attachment_id,
                meta_key=meta_key,
                meta_value=meta_value
            )
            self.session.add(new_meta)
