"""
Search service for image search functionality.

This module handles the AI-powered natural language search of crawled images.
"""
from app.config import DEFAULT_SEARCH_RESULTS
from app.utils.helpers import format_search_results_for_api

# Import search functionality from combined module
from combined import (
    search_images_with_dedup,
    parse_user_query_with_ai
)


def search_images(chroma_db, query, max_results=DEFAULT_SEARCH_RESULTS):
    """
    Search for images using natural language query.
    
    This function:
    1. Parses the user query using AI to extract search intent
    2. Performs a vector search for images matching the query
    3. Formats the results for the API response
    
    Args:
        chroma_db: ChromaDB vector database to search
        query (str): User's natural language query
        max_results (int): Maximum number of results to return
        
    Returns:
        dict: Search response containing formatted text and structured results
    """
    # Parse the query with AI to extract search intent
    parsed_query = parse_user_query_with_ai(query)
    
    # Search for images in the vector database
    search_results = search_images_with_dedup(
        chroma_db,
        parsed_query['search_query'],
        format_filter=parsed_query['format_filter'],
        max_results=max_results
    )
    
    # Generate text response
    if not search_results:
        response_text = "I couldn't find any images matching your search. Try describing what you're looking for differently, or ask about the types of images available."
    else:
        # Combine AI understanding with search results
        response_text = f"{parsed_query['response_message']}\n\n"
        response_text += format_search_results_for_api(search_results, query)
    
    # Format structured results for API response
    structured_results = []
    if search_results:
        structured_results = [
            {
                "url": img['url'],
                "format": img['format'],
                "alt_text": img['alt_text'],
                "source_url": img['source_url'],
                "score": img['score']
            } for img in search_results[:max_results]
        ]
    
    return {
        "response_text": response_text,
        "search_results": structured_results,
        "parsed_query": parsed_query
    }


def get_last_human_message(chat_history):
    """
    Extract the last human message from a chat history.
    
    Args:
        chat_history (list): List of chat messages with 'role' and 'content'
        
    Returns:
        str or None: The content of the last human message, or None if not found
    """
    for message in reversed(chat_history):
        if message.get('role') == 'human':
            return message.get('content', '')
    return None 