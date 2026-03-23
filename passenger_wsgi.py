import sys
import os

# Add the current directory to the path so 'app' can be found
# Passenger sometimes runs from a different working directory
sys.path.insert(0, os.path.dirname(__file__))

# Import the FastAPI app
try:
    from app.main import app
    from a2wsgi import ASGIMiddleware
except ImportError as e:
    # Log the error for troubleshooting in Passenger environment
    print(f"Error importing app or a2wsgi: {e}")
    raise

# Wrap the FastAPI app for WSGI compatibility
# Passenger expectations 'application' to be the entry point
application = ASGIMiddleware(app)

# Note: In some environments, you might need to handle static files explicitly
# if the web server doesn't serve them directly.
# FastAPI's mount("/wp-content", ...) in app/main.py handles this if reached.
