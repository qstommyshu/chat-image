"""
Flask Server for Website Crawler and Image Search

This is the main entry point for running the web crawler and image search server.
It imports and runs the Flask application instance.

Usage:
    python server.py
"""
from app import app

if __name__ == "__main__":
    # Start the application using configuration from app.config
    app.run() 