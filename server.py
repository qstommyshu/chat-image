"""
Flask Server for Website Crawler and Image Search

Entry point for running the web crawler and image search server.
"""

import os
from app import app

if __name__ == "__main__":
    # Read host & port from environment, with sensible defaults
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    # Turn off debug unless explicitly enabled via FLASK_DEBUG=1
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app.run(host=host, port=port, debug=debug)
