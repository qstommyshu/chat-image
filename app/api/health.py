"""
Health API Endpoints

This module contains health check and monitoring endpoints.
"""

from flask import Blueprint, jsonify

from app.services.cache import cache_service

# Create blueprint
health_bp = Blueprint('health', __name__, url_prefix='/health')


@health_bp.route('', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "Service is running"
    })


@health_bp.route('/cache', methods=['GET'])
async def cache_stats():
    """Cache statistics endpoint."""
    if not cache_service.is_available():
        return jsonify({
            "status": "unavailable",
            "message": "Redis cache is not available or not configured"
        }), 503
    
    # Get cache statistics
    stats = await cache_service.get_cache_stats()
    
    return jsonify({
        "status": "ok",
        "cache_stats": stats
    })


@health_bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint for monitoring server status.
    
    Returns:
        JSON response indicating server health and version
    """
    return jsonify({"status": "healthy", "version": "2.0.0"}) 