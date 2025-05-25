"""
Administrative routes for session management.

This module defines API endpoints for managing crawl sessions, including
listing, deleting, and cleaning up old sessions.
"""
from datetime import datetime, timedelta
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify

from app.config import DEFAULT_CLEANUP_HOURS
from app.utils.helpers import get_domain_from_url
from app.services.crawler import crawl_sessions, vector_stores, crawl_lock, active_crawls

# Create a Blueprint for admin routes
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all active crawl sessions.
    
    Returns summary information about all sessions, including their
    status, results, and creation time.
    
    Returns:
        JSON response with array of session summaries
    """
    sessions = []
    for session_id, session in crawl_sessions.items():
        sessions.append(session.to_dict())
    
    return jsonify({"sessions": sessions})


@admin_bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint for monitoring server status.
    
    Returns:
        JSON response indicating server health and version
    """
    return jsonify({
        "status": "healthy", 
        "version": "1.0.0",
        "active_sessions": len(crawl_sessions),
        "active_crawls": len(active_crawls)
    })


@admin_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """
    Delete a specific session and free its resources.
    
    This endpoint removes a session and all associated data including
    the vector database and domain tracking.
    
    Args:
        session_id (str): Session to delete
        
    Returns:
        JSON confirmation message
        
    Error Codes:
        404: Session not found
    """
    if session_id not in crawl_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    # Clean up vector database
    if session_id in vector_stores:
        del vector_stores[session_id]
    
    session = crawl_sessions[session_id]
    
    # Clean up domain tracking if session is still active
    try:
        domain = get_domain_from_url(session.url)
        with crawl_lock:
            active_crawls.pop(domain, None)
    except:
        pass  # Ignore errors during cleanup
    
    # Remove session
    del crawl_sessions[session_id]
    
    return jsonify({"message": f"Session {session_id} deleted successfully"})


@admin_bp.route('/cleanup', methods=['POST'])
def cleanup_old_sessions():
    """
    Clean up old completed sessions to free memory.
    
    This endpoint removes sessions that have been completed or errored
    for longer than the specified time period.
    
    Request Body:
        hours_old (int, optional): Age threshold in hours (default: 24)
        
    Returns:
        JSON response with cleanup statistics
    """
    data = request.json or {}
    hours_old = data.get('hours_old', DEFAULT_CLEANUP_HOURS)
    
    # Calculate cutoff time
    cutoff_time = datetime.now() - timedelta(hours=hours_old)
    sessions_to_delete = []
    
    # Find sessions eligible for cleanup
    for session_id, session in crawl_sessions.items():
        # Only clean up completed or errored sessions
        if session.status in ["completed", "error"]:
            try:
                # Use first message timestamp as creation time
                if not session.messages.empty():
                    first_message = session.messages.queue[0]
                    created_at = datetime.fromisoformat(first_message['timestamp'])
                    if created_at < cutoff_time:
                        sessions_to_delete.append(session_id)
            except:
                # If timestamp parsing fails, assume session is old
                sessions_to_delete.append(session_id)
    
    # Perform cleanup
    deleted_count = 0
    for session_id in sessions_to_delete:
        try:
            # Remove vector database
            if session_id in vector_stores:
                del vector_stores[session_id]
            # Remove session
            del crawl_sessions[session_id]
            deleted_count += 1
        except:
            pass  # Continue cleanup even if individual deletion fails
    
    return jsonify({
        "message": f"Cleaned up {deleted_count} old sessions",
        "deleted_sessions": sessions_to_delete,
        "remaining_sessions": len(crawl_sessions)
    }) 