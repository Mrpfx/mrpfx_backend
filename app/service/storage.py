"""
Railway S3-compatible bucket storage service.
Provides upload, download, delete, and thumbnail generation.
"""
import io
import logging
from typing import Optional, BinaryIO

import boto3
from botocore.config import Config
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)


class RailwayStorage:
    """S3-compatible storage service for Railway Buckets."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.BUCKET_ENDPOINT,
                region_name=settings.BUCKET_REGION,
                aws_access_key_id=settings.BUCKET_ACCESS_KEY_ID,
                aws_secret_access_key=settings.BUCKET_SECRET_ACCESS_KEY,
                config=Config(
                    s3={"addressing_style": "path"},
                    signature_version="s3v4",
                ),
            )
        return self._client

    async def upload_fileobj(
        self, fileobj: BinaryIO, key: str, content_type: str = "application/octet-stream"
    ) -> str:
        client = self._get_client()
        client.upload_fileobj(
            fileobj, settings.BUCKET_NAME, key,
            ExtraArgs={"ContentType": content_type},
        )
        logger.info("Uploaded to S3: %s", key)
        return key

    async def upload_bytes(
        self, data: bytes, key: str, content_type: str = "application/octet-stream"
    ) -> str:
        return await self.upload_fileobj(io.BytesIO(data), key, content_type)

    async def download_fileobj(self, key: str) -> Optional[bytes]:
        client = self._get_client()
        try:
            buffer = io.BytesIO()
            client.download_fileobj(settings.BUCKET_NAME, key, buffer)
            buffer.seek(0)
            return buffer.read()
        except Exception as e:
            logger.error("Failed to download %s: %s", key, str(e))
            return None

    async def delete_file(self, key: str) -> bool:
        client = self._get_client()
        try:
            client.delete_object(Bucket=settings.BUCKET_NAME, Key=key)
            logger.info("Deleted from S3: %s", key)
            return True
        except Exception as e:
            logger.error("Failed to delete %s: %s", key, str(e))
            return False

    async def delete_files(self, keys: list[str]) -> bool:
        client = self._get_client()
        try:
            objects = [{"Key": k} for k in keys]
            client.delete_objects(
                Bucket=settings.BUCKET_NAME,
                Delete={"Objects": objects, "Quiet": True},
            )
            logger.info("Deleted %d objects from S3", len(keys))
            return True
        except Exception as e:
            logger.error("Failed to delete objects: %s", str(e))
            return False

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        client = self._get_client()
        try:
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.BUCKET_NAME, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception as e:
            logger.error("Failed to generate presigned URL for %s: %s", key, str(e))
            return None

    def get_public_url(self, key: str) -> str:
        base = settings.ASSETS_BASE_URL or settings.BACKEND_URL
        return f"{base.rstrip('/')}/api/v1/files/{key}"

    async def generate_thumbnails(self, image_data: bytes, key_base: str) -> dict:
        """Generate and upload thumbnail sizes for an image.

        Returns dict mapping size names to thumbnail metadata.
        """
        target_sizes = {
            "thumbnail": (150, 150, True),
            "medium": (300, 300, False),
            "large": (1024, 1024, False),
        }

        sizes_meta = {}

        with Image.open(io.BytesIO(image_data)) as img:
            width, height = img.size
            ext = key_base.rsplit(".", 1)[-1] if "." in key_base else "jpg"
            fmt = img.format or "JPEG"
            mime_type = f"image/{fmt.lower()}"

            for size_name, (tw, th, crop) in target_sizes.items():
                if width <= tw and height <= th:
                    continue

                resized = img.copy()

                if crop:
                    w_ratio = tw / width
                    h_ratio = th / height
                    ratio = max(w_ratio, h_ratio)
                    new_size = (int(width * ratio), int(height * ratio))
                    resized = resized.resize(new_size, Image.LANCZOS)
                    left = (resized.width - tw) / 2
                    top = (resized.height - th) / 2
                    resized = resized.crop((left, top, left + tw, top + th))
                    rw, rh = tw, th
                else:
                    resized.thumbnail((tw, th), Image.LANCZOS)
                    rw, rh = resized.size

                file_dir = key_base.rsplit("/", 1)[0] if "/" in key_base else ""
                file_base = key_base.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                thumb_filename = f"{file_base}-{rw}x{rh}.{ext}"
                thumb_key = f"{file_dir}/{thumb_filename}" if file_dir else thumb_filename

                buf = io.BytesIO()
                resized.save(buf, format=fmt)
                buf.seek(0)
                await self.upload_fileobj(buf, thumb_key, content_type=mime_type)

                sizes_meta[size_name] = {
                    "file": thumb_filename,
                    "width": rw,
                    "height": rh,
                    "mime-type": mime_type,
                }

        return sizes_meta

    async def file_exists(self, key: str) -> bool:
        client = self._get_client()
        try:
            client.head_object(Bucket=settings.BUCKET_NAME, Key=key)
            return True
        except Exception:
            return False


storage = RailwayStorage()
