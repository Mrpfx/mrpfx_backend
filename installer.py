import subprocess
import sys

# === List of required packages with versions ===
packages = [
    "aiosqlite==0.22.0",
    "alembic==1.17.2",
    "annotated-doc==0.0.4",
    "annotated-types==0.7.0",
    "anyio==4.12.0",
    "asyncpg==0.31.0",
    "attrs==25.4.0",
    "bcrypt==5.0.0",
    "certifi==2025.11.12",
    "charset-normalizer==3.4.4",
    "click==8.3.1",
    "Deprecated==1.3.1",
    "dnspython==2.8.0",
    "dotenv==0.9.9",
    "ecdsa==0.19.1",
    "email-validator==2.3.0",
    "fastapi==0.124.4",
    "greenlet==3.3.0",
    "h11==0.16.0",
    "httpcore==1.0.9",
    "httpx==0.28.1",
    "idna==3.11",
    "Jinja2==3.1.6",
    "limits==5.6.0",
    "mailjet==1.4.1",
    "mailjet-rest==1.3.4",
    "Mako==1.3.10",
    "MarkupSafe==3.0.3",
    "outcome==1.3.0.post0",
    "packaging==25.0",
    "passlib==1.7.4",
    "pyasn1==0.6.1",
    "pydantic==2.12.5",
    "pydantic-settings==2.12.0",
    "pydantic_core==2.41.5",
    "PySocks==1.7.1",
    "python-dotenv==1.2.1",
    "python-jose==3.5.0",
    "python-multipart==0.0.20",
    "requests==2.32.5",
    "rsa==4.9.1",
    "selenium==4.39.0",
    "six==1.17.0",
    "slowapi==0.1.9",
    "sniffio==1.3.1",
    "sortedcontainers==2.4.0",
    "SQLAlchemy==2.0.45",
    "sqlmodel==0.0.27",
    "starlette==0.50.0",
    "trio==0.32.0",
    "trio-websocket==0.12.2",
    "typing-inspection==0.4.2",
    "typing_extensions==4.15.0",
    "urllib3==2.6.2",
    "uvicorn==0.38.0",
    "webdriver-manager==4.0.2",
    "websocket-client==1.9.0",
    "wrapt==2.0.1",
    "wsproto==1.3.2",
    "a2wsgi==1.10.7",
    "cloudinary==1.41.0",
    "psycopg[binary]",
    "psycopg-pool==3.2.1",
    "PyJWT==2.8.0"
]

def install(package):
    """Install a Python package using pip."""
    try:
        print(f"📦 Installing {package} ...")
        # Use sys.executable to ensure pip is from the correct virtual env
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}\n")

if __name__ == "__main__":
    print("--- Starting package installation ---")
    for pkg in packages:
        install(pkg)
    print("--- All packages processed ---")
