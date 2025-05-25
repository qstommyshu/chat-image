"""
Flask Web Crawler and Image Search Application.

This is the main application module that initializes the Flask application,
registers blueprints, and configures middleware.
"""
from flask import Flask
from flask_cors import CORS

from app.config import DEBUG, PORT, THREADED
from app.routes import crawl_bp, search_bp, admin_bp


def create_app():
    """
    Application factory function.
    
    This function creates and configures the Flask application, registering
    all blueprints and middleware.
    
    Returns:
        Flask application instance
    """
    # Initialize Flask application
    app = Flask(__name__)
    
    # Enable CORS for all routes
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(crawl_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(admin_bp)
    
    return app


# Default application instance for direct running
app = create_app()

if __name__ == "__main__":
    app.run(debug=DEBUG, port=PORT, threaded=THREADED)
