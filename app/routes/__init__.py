"""
Route initialization module.

This module imports and initializes all route blueprints for registration
with the Flask application.
"""
from app.routes.crawl_routes import crawl_bp
from app.routes.search_routes import search_bp
from app.routes.admin_routes import admin_bp

__all__ = ['crawl_bp', 'search_bp', 'admin_bp']
