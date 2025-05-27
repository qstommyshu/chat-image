"""
Chat API Endpoints

This module contains API endpoints for natural language image search
and chat functionality.
"""

from flask import Blueprint, request, jsonify

from app.models.session import session_manager
from app.services.search import SearchService

# Create blueprint
chat_bp = Blueprint('chat', __name__)

# Initialize services
search_service = SearchService()


@chat_bp.route('/chat', methods=['POST'])
async def chat():
    """
    Natural language image search endpoint.
    
    This endpoint processes chat messages and searches for relevant images
    using AI-powered natural language understanding and vector similarity.
    
    Request Body:
        session_id (str): The crawl session to search within
        chat_history (list): Array of chat messages with role and content
        skip_cache (bool, optional): Skip cache lookup for this query (default: false)
        
    Returns:
        JSON response with formatted text response, structured search results, and cache info
        
    Error Codes:
        400: Missing session_id or invalid chat history
        404: Session not found or vector database missing
        400: Crawling not yet completed
    """
    data = request.json
    chat_history = data.get('chat_history', [])
    session_id = data.get('session_id')
    skip_cache = data.get('skip_cache', False)
    
    # Validate required parameters
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    # Verify session exists and is ready for search
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    if not session.completed:
        return jsonify({"error": "Crawling not yet completed"}), 400
    
    # Get the namespace for this session
    namespace = session_manager.get_namespace(session_id)
    if not namespace:
        return jsonify({"error": "Session namespace not found - data may have been cleaned up"}), 404
    
    # Extract the most recent human message from chat history
    last_human_message = None
    for message in reversed(chat_history):
        if message.get('role') == 'human':
            last_human_message = message.get('content', '')
            break
    
    if not last_human_message:
        return jsonify({"error": "No human message found in chat history"}), 400
    
    # Use AI to parse the user's query and extract search intent (with caching)
    parsed_query = await search_service.parse_user_query_with_ai_cached(last_human_message)
    parser_cache_info = parsed_query.pop('_cache', None)
    
    # Execute semantic search with deduplication and caching
    search_results, cache_info = await search_service.search_images_with_cache(
        query=parsed_query['search_query'],
        namespace=namespace,
        format_filter=parsed_query['format_filter'],
        max_results=5,
        skip_cache=skip_cache
    )
    
    # Generate formatted API response with results
    api_response = search_service.format_search_results_for_api(
        search_results=search_results,
        query=last_human_message,
        cache_info=cache_info
    )
    
    # Generate response text
    if not search_results:
        response = "I couldn't find any images matching your search. Try describing what you're looking for differently, or ask about the types of images available."
    else:
        # Combine AI understanding with search summary
        response = f"{parsed_query['response_message']}\n\n"
        response += api_response["message"]
        
        # Add cache hit indication to response if applicable
        if cache_info and cache_info.get("cache_hit"):
            cache_age = cache_info.get("cache_age", "")
            performance_gain = cache_info.get("performance_gain", "")
            response += f"\n\n🚀 Cache hit! Results loaded {performance_gain} ({cache_age} old)"
    
    # Add context for first-time users
    if len(chat_history) == 1:  # Only AI's initial greeting message
        response = f"Based on my crawl of {session.url}, " + response
    
    # Prepare response with all information
    result = {
        "response": response,
        "search_results": [
            {
                "url": img['url'],
                "format": img['format'],
                "alt_text": img['alt_text'],
                "source_url": img['source_url'],
                "score": img['score']
            } for img in search_results[:5]
        ] if search_results else [],
        "session_id": session_id,
        "cache_info": cache_info,
        "parser_cache_info": parser_cache_info
    }
    
    return jsonify(result) 