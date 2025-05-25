"""
Routes for website crawling operations.

This module defines the API endpoints for initiating crawl operations and
monitoring their progress via Server-Sent Events (SSE).
"""
import uuid
import json
import threading
from flask import Blueprint, request, jsonify, Response

from app.config import MAX_CONCURRENT_CRAWLS
from app.models.session import CrawlSession
from app.utils.helpers import get_domain_from_url
from app.services.crawler import (
    perform_crawl, 
    crawl_sessions, 
    crawl_lock, 
    active_crawls
)

# Create a Blueprint for crawl routes
crawl_bp = Blueprint('crawl', __name__)


@crawl_bp.route('/crawl', methods=['POST'])
def crawl():
    """
    Start a new website crawling session.
    
    This endpoint initiates a background crawling operation and returns
    a session ID that can be used to monitor progress and search results.
    
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
    domain = get_domain_from_url(url)
    if not domain:
        return jsonify({"error": "Invalid URL format"}), 400
    
    # Thread-safe session creation with concurrency checks
    with crawl_lock:
        # Check if we've reached the maximum concurrent crawl limit
        active_session_count = len([
            s for s in crawl_sessions.values() 
            if s.status in ["crawling", "processing", "indexing"]
        ])
        
        if active_session_count >= MAX_CONCURRENT_CRAWLS:
            return jsonify({
                "error": f"Maximum {MAX_CONCURRENT_CRAWLS} concurrent crawls allowed. Please try again later."
            }), 429
        
        # Check if the same domain is already being crawled
        if domain in active_crawls:
            return jsonify({
                "error": f"Domain {domain} is already being crawled",
                "existing_session": active_crawls[domain],
                "message": "Please wait for the current crawl to complete or use the existing session"
            }), 409
        
        # Create new session and track it
        session_id = str(uuid.uuid4())
        session = CrawlSession(session_id, url, limit)
        crawl_sessions[session_id] = session
        
        # Mark domain as actively being crawled
        active_crawls[domain] = session_id
    
    # Start crawling in background thread
    thread = threading.Thread(target=perform_crawl, args=(session,))
    thread.daemon = True  # Allow server shutdown even if thread is running
    thread.start()
    
    return jsonify({
        "session_id": session_id,
        "message": "Crawling started",
        "subscribe_url": f"/crawl/{session_id}/status"
    })


@crawl_bp.route('/crawl/<session_id>/status')
def crawl_status(session_id):
    """
    Server-Sent Events endpoint for real-time crawl status updates.
    
    This endpoint provides a continuous stream of status updates for a
    crawling session. Clients can subscribe to receive real-time progress.
    
    Args:
        session_id (str): The session ID to monitor
        
    Returns:
        SSE stream with status updates
        
    Error Codes:
        404: Session not found
    """
    session = crawl_sessions.get(session_id)
    
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    def generate():
        """
        Generator function for Server-Sent Events.
        
        This function yields status messages from the session's message queue
        and handles connection lifecycle (heartbeats, completion detection).
        """
        # Send initial connection confirmation
        yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
        
        # Main message loop
        while True:
            try:
                # Wait for new message (1 second timeout)
                message = session.messages.get(timeout=1)
                yield f"data: {json.dumps(message)}\n\n"
                
                # Close connection if crawl is finished (success or error)
                if message.get('type') in ['completed', 'error']:
                    break
                    
            except Exception:
                # No new messages - send heartbeat to keep connection alive
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                
                # Check if session has finished (failsafe)
                if session.completed or session.error:
                    break
    
    return Response(generate(), mimetype='text/event-stream') 