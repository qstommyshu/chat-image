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
    in Pinecone for semantic search. Each user gets their own isolated 
    session and data namespace.
    
    Request Body:
        url (str): The URL to start crawling from
        limit (int, optional): Maximum number of pages to crawl (default: 10)
        skip_cache (bool, optional): Skip cache lookup for this crawl (default: false)
    
    Returns:
        JSON response with session_id and subscribe_url for status updates
        
    Error Codes:
        400: Missing or invalid URL
        429: Too many concurrent crawls (server-wide limit)
    """
    data = request.json
    url = data.get('url')
    limit = data.get('limit', 10)
    skip_cache = data.get('skip_cache', False)
    
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
    session, error_message = session_manager.create_session(
        session_id=session_id,
        url=url,
        limit=limit,
        domain=domain,
        skip_cache=skip_cache
    )
    
    if error_message:
        return jsonify({"error": error_message}), 429
    
    # Start crawling in background thread
    crawler_service.start_crawl(session)
    
    # Prepare response with cache info
    response = {
        "session_id": session_id,
        "message": "Crawling started",
        "subscribe_url": f"/crawl/{session_id}/status",
        "status_url_sse": f"/crawl/{session_id}/status",
        "status_url_polling": f"/crawl/{session_id}/status-simple",
        "cache_enabled": not skip_cache and crawler_service.cache_service.is_available()
    }
    
    return jsonify(response)


 