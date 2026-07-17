import multiprocessing
import os

# Binding - use Railway's PORT env or default to 8000
port = os.getenv("PORT", "8000")
bind = f"0.0.0.0:{port}"

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"

# Timeouts
timeout = 120
keepalive = 5

# Daemon
daemon = False

# Process Name
proc_name = "mrpfx_backend"

# Trust headers from Railway proxy
forwarded_allow_ips = "*"
proxy_protocol = False
proxy_allow_ips = "*"
