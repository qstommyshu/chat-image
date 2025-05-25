"""
Flask Server for Website Crawler and Image Search (v2.0 - Modular)

This is the main entry point for the modular Flask application.
The server provides REST API endpoints for:
1. Crawling websites and extracting images
2. Real-time status updates via Server-Sent Events (SSE)
3. Natural language image search using AI
4. Session management and resource cleanup

The server now uses a modular architecture with separate concerns:
- Configuration management
- Service layer for business logic
- API blueprints for routes
- Model classes for data structures
"""

from app import create_app
from app.config import Config

# Create Flask application using the application factory pattern
app = create_app()

if __name__ == '__main__':
    # Start the development server
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        threaded=True
    ) 