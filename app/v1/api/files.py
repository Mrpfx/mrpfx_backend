"""
File serving proxy endpoint for Railway S3 bucket storage.
Proxies file requests from the backend to S3, so files appear to
be served from the backend domain (avoiding private bucket limitations).
"""
import logging
from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

CONTENT_TYPE_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "avif": "image/avif",
    "bmp": "image/bmp",
    "ico": "image/x-icon",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    "avi": "video/x-msvideo",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "zip": "application/zip",
    "gz": "application/gzip",
    "tar": "application/x-tar",
    "rar": "application/vnd.rar",
    "7z": "application/x-7z-compressed",
    "json": "application/json",
    "xml": "application/xml",
    "csv": "text/csv",
    "txt": "text/plain",
    "html": "text/html",
    "css": "text/css",
    "js": "application/javascript",
    "woff": "font/woff",
    "woff2": "font/woff2",
    "ttf": "font/ttf",
    "otf": "font/otf",
    "eot": "application/vnd.ms-fontobject",
}


@router.get("/{path:path}")
async def serve_file(path: str):
    """Proxy a file from Railway S3 bucket through the backend."""
    if not settings.USE_RAILWAY_BUCKET:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File storage not available"
        )

    from app.service.storage import storage

    data = await storage.download_fileobj(path)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    content_type = CONTENT_TYPE_MAP.get(ext, "application/octet-stream")

    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Access-Control-Allow-Origin": "*",
        }
    )
