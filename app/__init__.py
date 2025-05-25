"""
Flask Application Factory

This module creates and configures the Flask application with all necessary
components including CORS, routes, and error handlers.
"""

from flask import Flask
from flask_cors import CORS
from app.config import Config


def create_app(config_class=Config):
    """
    Application factory pattern for creating Flask app.
    
    Args:
        config_class: Configuration class to use
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize CORS
    CORS(app)
    
    # Register blueprints
    from app.api.crawl import crawl_bp
    from app.api.chat import chat_bp
    from app.api.status import status_bp
    from app.api.health import health_bp
    
    app.register_blueprint(crawl_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(health_bp)
    
    return app 