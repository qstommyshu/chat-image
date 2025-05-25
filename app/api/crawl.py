"""
Crawl API Endpoints

This module contains API endpoints for website crawling operations.
"""

import uuid
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify

from app.config import Config
from app.models.session import session_manager
from app.services.crawler import CrawlerService

# Create blueprint
crawl_bp = Blueprint('crawl', __name__)

# Initialize services
crawler_service = CrawlerService()


@crawl_bp.route('/crawl', methods=['POST'])
def start_crawl():
    """
    Start a new website crawling session.
    
    This endpoint initiates a background crawling operation that processes
    content directly in memory without disk storage, then indexes images
    in Pinecone for semantic search.
    
    Request Body:
        url (str): The URL to start crawling from
        limit (int, optional): Maximum number of pages to crawl (default: 10)
    
    Returns:
        JSON response with session_id and subscribe_url for status updates
        
    Error Codes:
        400: Missing or invalid URL
        409: Domain already being crawled  
        429: Too many concurrent crawls
    """
    data = request.json
    url = data.get('url')
    limit = data.get('limit', 10)
    
    # Validate required parameters
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    # Parse and validate URL format
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
    except:
        return jsonify({"error": "Invalid URL format"}), 400
    
    # Create new session with concurrency checks
    session_id = str(uuid.uuid4())
    session, error_message = session_manager.create_session(session_id, url, limit, domain)
    
    if error_message:
        if "concurrent crawls" in error_message:
            return jsonify({"error": error_message}), 429
        else:
            return jsonify({
                "error": error_message,
                "existing_session": session_manager.active_crawls.get(domain),
                "message": "Please wait for the current crawl to complete or use the existing session"
            }), 409
    
    # Start crawling in background thread
    crawler_service.start_crawl(session)
    
    return jsonify({
        "session_id": session_id,
        "message": "Crawling started",
        "subscribe_url": f"/crawl/{session_id}/status",
        "status_url_sse": f"/crawl/{session_id}/status",
        "status_url_polling": f"/crawl/{session_id}/status-simple"
    })


@crawl_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all active crawl sessions.
    
    Returns summary information about all sessions, including their
    status, results, and creation time.
    
    Returns:
        JSON response with array of session summaries
    """
    sessions = session_manager.list_sessions()
    return jsonify({"sessions": sessions})


@crawl_bp.route('/sessions/<session_id>', methods=['DELETE'])
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
    if not session_manager.delete_session(session_id):
        return jsonify({"error": "Session not found"}), 404
    
    return jsonify({"message": f"Session {session_id} deleted successfully"})


@crawl_bp.route('/cleanup', methods=['POST'])
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
    from datetime import datetime, timedelta
    
    data = request.json or {}
    hours_old = data.get('hours_old', 24)  # Default: 24 hours
    
    # Calculate cutoff time
    cutoff_time = datetime.now() - timedelta(hours=hours_old)
    sessions_to_delete = []
    
    # Find sessions eligible for cleanup
    for session_id, session in session_manager.crawl_sessions.items():
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
        if session_manager.delete_session(session_id):
            deleted_count += 1
    
    return jsonify({
        "message": f"Cleaned up {deleted_count} old sessions",
        "deleted_sessions": sessions_to_delete,
        "remaining_sessions": len(session_manager.crawl_sessions)
    }) 