"""
Routes for image search operations.

This module defines the API endpoints for searching crawled images using
natural language queries.
"""
from flask import Blueprint, request, jsonify

from app.services.search import search_images, get_last_human_message
from app.services.crawler import crawl_sessions, vector_stores

# Create a Blueprint for search routes
search_bp = Blueprint('search', __name__)


@search_bp.route('/chat', methods=['POST'])
def chat():
    """
    Natural language image search endpoint.
    
    This endpoint processes chat messages and searches for relevant images
    using AI-powered natural language understanding and vector similarity.
    
    Request Body:
        session_id (str): The crawl session to search within
        chat_history (list): Array of chat messages with role and content
        
    Returns:
        JSON response with formatted text response and structured search results
        
    Error Codes:
        400: Missing session_id or invalid chat history
        404: Session not found or vector database missing
        400: Crawling not yet completed
    """
    data = request.json
    chat_history = data.get('chat_history', [])
    session_id = data.get('session_id')
    
    # Validate required parameters
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    # Verify session exists and is ready for search
    session = crawl_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    if not session.completed:
        return jsonify({"error": "Crawling not yet completed"}), 400
    
    # Get the vector database for this session
    chroma_db = vector_stores.get(session_id)
    if not chroma_db:
        return jsonify({"error": "Vector database not found"}), 404
    
    # Extract the most recent human message from chat history
    last_human_message = get_last_human_message(chat_history)
    if not last_human_message:
        return jsonify({"error": "No human message found in chat history"}), 400
    
    # Execute the search
    search_response = search_images(chroma_db, last_human_message)
    
    # Add context for first-time users (if this is their first message)
    response_text = search_response["response_text"]
    if len(chat_history) == 1:  # Only AI's initial greeting message
        response_text = f"Based on my crawl of {session.url}, " + response_text
    
    return jsonify({
        "response": response_text,
        "search_results": search_response["search_results"],
        "session_id": session_id
    }) 