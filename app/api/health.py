"""
Health API Endpoints

This module contains health check and monitoring endpoints.
"""

from flask import Blueprint, jsonify

# Create blueprint
health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint for monitoring server status.
    
    Returns:
        JSON response indicating server health and version
    """
    return jsonify({"status": "healthy", "version": "2.0.0"}) 