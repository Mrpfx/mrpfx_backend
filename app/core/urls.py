from typing import Optional
from urllib.parse import urlparse

from app.core.config import settings


def rewrite_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return url
    base = settings.PUBLIC_STORAGE_URL.rstrip("/")
    if url.startswith("/"):
        return f"{base}{url}"
    if url.startswith("http://") or url.startswith("https://"):
        if url.startswith(base):
            return url
        try:
            parsed = urlparse(url)
            path = parsed.path
            return f"{base}{path}"
        except Exception:
            return url
    return url
