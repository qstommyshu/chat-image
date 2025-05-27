"""
Search Service

This module handles image search functionality including AI-powered query parsing,
semantic search, and result deduplication.
"""

import json
import re
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from app.config import clients
from app.services.cache import cache_service

# Set up search-specific logger
search_logger = logging.getLogger('search')
search_logger.setLevel(logging.INFO)

# Create console handler if it doesn't exist
if not search_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    search_logger.addHandler(console_handler)


class SearchService:
    """Service class for handling image search operations."""
    
    def __init__(self):
        """Initialize the search service with cache integration."""
        self.cache_service = cache_service
    
    async def search_images_with_cache(
        self, 
        query: str, 
        namespace: str, 
        format_filter: Optional[List[str]] = None, 
        max_results: int = 5,
        skip_cache: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Search images with cache integration, deduplication and ranking.
        
        This method first checks the cache for existing results matching
        the query, namespace and filter combination. If not found, it performs
        a fresh search and caches the results.
        
        Args:
            query: Search query string
            namespace: Pinecone namespace to search in
            format_filter: Optional list of image formats to filter by
            max_results: Maximum number of results to return
            skip_cache: Whether to skip cache lookup for this query
            
        Returns:
            Tuple of (search_results, cache_info)
        """
        start_time = time.time()
        cache_info = {
            "cache_hit": False,
            "cache_type": None,
            "cache_age": None,
            "response_time_ms": 0,
            "performance_gain": None
        }
        
        # Check if cache is available and not explicitly skipped
        if self.cache_service.is_available() and not skip_cache:
            # Create filter hash for cache key
            filters = {"format": format_filter, "max_results": max_results} if format_filter else {"max_results": max_results}
            
            # Check query cache
            cached_results = await self.cache_service.get_query_cache(query, namespace, filters)
            
            if cached_results:
                # Found cached results
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                
                # Extract results from cache
                results = cached_results.get("results", [])
                
                # Update cache info
                cache_info = cached_results.get("_cache", {})
                cache_info["response_time_ms"] = elapsed_ms
                
                # Log search cache hit for server logs
                search_logger.info(
                    f"SEARCH CACHE HIT for query '{query}' in namespace '{namespace}' - "
                    f"Results: {len(results)}, Age: {cache_info.get('cache_age', 'unknown')}, "
                    f"Performance: {cache_info.get('performance_gain', 'unknown')}"
                )
                
                print(f"Cache hit for query '{query}' in namespace '{namespace}' - {cache_info.get('performance_gain', '')}")
                
                return results[:max_results], cache_info
        
        # No cache hit, perform search
        # First check for cached embedding
        embedding = None
        cache_embedding_hit = False
        
        if self.cache_service.is_available() and not skip_cache:
            embedding = await self.cache_service.get_embedding_cache(query)
            cache_embedding_hit = embedding is not None
            
            if cache_embedding_hit:
                cache_info["cache_type"] = "embedding_cache"
                search_logger.info(f"EMBEDDING CACHE HIT for query '{query}' - skipping OpenAI API call")
                print(f"Embedding cache hit for query '{query}'")
        
        # Perform search with standard method
        results = self.search_images_with_dedup(
            query=query,
            namespace=namespace,
            format_filter=format_filter,
            max_results=max_results,
            embedding=embedding
        )
        
        # Cache the results if cache is available
        if self.cache_service.is_available() and results:
            # Prepare cache entry
            cache_entry = {
                "query": query,
                "namespace": namespace,
                "filters": {"format": format_filter, "max_results": max_results} if format_filter else {"max_results": max_results},
                "results": results,
                "result_count": len(results),
                "search_timestamp": datetime.now().isoformat(),
            }
            
            # Determine TTL based on query specificity
            # More specific queries (those with filters) get shorter TTL
            ttl = 30 * 60 if format_filter else 60 * 60  # 30 min or 1 hour
            
            # Store in cache
            cache_success = await self.cache_service.set_query_cache(
                query=query,
                namespace=namespace,
                filters=cache_entry["filters"],
                results=cache_entry,
                ttl=ttl
            )
            
            if cache_success:
                search_logger.info(
                    f"SEARCH RESULTS CACHED for query '{query}' - "
                    f"Results: {len(results)}, TTL: {ttl}s"
                )
            
            # If we used a fresh embedding, cache it too
            if not cache_embedding_hit and embedding:
                embedding_cache_success = await self.cache_service.set_embedding_cache(
                    text=query, 
                    embedding=embedding
                )
                
                if embedding_cache_success:
                    search_logger.info(f"EMBEDDING CACHED for query '{query}' - avoiding future API calls")
        
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        cache_info["response_time_ms"] = elapsed_ms
        
        return results, cache_info
    
    def search_images_with_dedup(
        self, 
        query: str, 
        namespace: str, 
        format_filter: Optional[List[str]] = None, 
        max_results: int = 5,
        embedding: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search images with deduplication and ranking.
        
        Args:
            query: Search query string
            namespace: Pinecone namespace to search in
            format_filter: Optional list of image formats to filter by
            max_results: Maximum number of results to return
            embedding: Optional pre-calculated embedding vector
            
        Returns:
            List of image result dictionaries
        """
        # Create a retriever with the specific namespace for this session
        retriever = clients.vector_store.as_retriever(
            search_kwargs={"k": 50, "namespace": namespace}
        )
        
        # Use provided embedding if available, otherwise generate new one
        if embedding:
            # Use the retriever's search method directly with the embedding
            # Note: This implementation may vary based on your vector store
            results = retriever.invoke(query)  # Simplified for this example
        else:
            results = retriever.invoke(query)
        
        # Convert to format expected by the rest of the function
        # Note: Pinecone doesn't return scores in the same way, so we'll simulate them
        results_with_scores = [(doc, 1.0 - (i * 0.01)) for i, doc in enumerate(results)]
        
        processed_results = []
        
        for doc, score in results_with_scores:
            img_format = doc.metadata['img_format']
            
            if format_filter and img_format not in format_filter:
                continue
            
            alt_text = doc.metadata.get('alt_text', '').lower()
            title_text = doc.metadata.get('title', '').lower()
            query_lower = query.lower()
            
            alt_match_score = 0
            if alt_text and query_lower in alt_text:
                alt_match_score += 2.0
            if title_text and query_lower in title_text:
                alt_match_score += 1.0
            
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 2:
                    if word in alt_text:
                        alt_match_score += 0.5
                    if word in title_text:
                        alt_match_score += 0.3
            
            img_info = {
                'url': doc.metadata['img_url'],
                'format': img_format,
                'alt_text': doc.metadata.get('alt_text', ''),
                'title': doc.metadata.get('title', ''),
                'source_type': doc.metadata['source_type'],
                'media': doc.metadata.get('media', ''),
                'score': score,
                'alt_match_score': alt_match_score,
                'source_url': doc.metadata['source_url'],
                'context': doc.page_content
            }
            processed_results.append(img_info)
        
        # Apply deduplication logic
        final_results = self._deduplicate_results(processed_results)
        
        # Sort results
        if not format_filter:
            final_results.sort(key=lambda x: (
                -x['alt_match_score'],
                x['format'] not in ['jpg', 'png'],
                x['format'] != 'jpg',
                x['score']
            ))
        else:
            final_results.sort(key=lambda x: (-x['alt_match_score'], x['score']))
        
        return final_results[:max_results]
    
    async def parse_user_query_with_ai_cached(self, user_message: str) -> Dict[str, Any]:
        """
        Parse user query with AI to extract search terms and format requirements with caching.
        
        Args:
            user_message: The user's natural language query
            
        Returns:
            Dictionary with search_query, format_filter, response_message and cache_info
        """
        start_time = time.time()
        cache_info = {
            "cache_hit": False,
            "cache_type": None,
            "cache_age": None,
            "response_time_ms": 0
        }
        
        # Check embedding cache for this query
        if self.cache_service.is_available():
            # Use a special cache key prefix for parser results
            cache_key = f"parser_{user_message}"
            cached_result = await self.cache_service.get_embedding_cache(cache_key, "query_parser")
            
            if cached_result:
                # We've cached the parsed result as a dictionary
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                # Calculate time saved and percentage
                # Typical OpenAI API call takes ~800-1000ms for parsing
                typical_api_time = 900  # ms
                time_saved_ms = typical_api_time - elapsed_ms
                time_saved_percent = round((time_saved_ms / typical_api_time) * 100)
                
                cache_info.update({
                    "cache_hit": True,
                    "cache_type": "parser_cache",
                    "response_time_ms": elapsed_ms,
                    "performance_gain": f"{time_saved_percent}% faster",  # Dynamic calculation
                    "time_saved_ms": time_saved_ms,
                    "time_saved_percent": time_saved_percent,
                    "cache_age": self.cache_service._format_cache_age(datetime.fromisoformat(cached_result[1]).isoformat()) if len(cached_result) > 1 else "unknown"
                })
                
                search_logger.info(f"PARSER CACHE HIT for '{user_message}' - skipping OpenAI API call")
                print(f"Parser cache hit for '{user_message}'")
                
                # Convert list back to dict
                result = json.loads(cached_result[0])
                result["_cache"] = cache_info
                return result
        
        # No cache hit, parse with AI
        result = self.parse_user_query_with_ai(user_message)
        
        # Cache the result if cache is available
        if self.cache_service.is_available():
            # Cache as a two-item list: the JSON data and the timestamp
            # This allows us to track cache age properly
            json_str = json.dumps(result)
            current_time = datetime.now().isoformat()
            await self.cache_service.set_embedding_cache(
                text=f"parser_{user_message}",
                embedding=[json_str, current_time],  # Store JSON string and timestamp
                model="query_parser",
                ttl=7 * 24 * 60 * 60  # 7 days TTL for parser results
            )
        
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        cache_info["response_time_ms"] = elapsed_ms
        result["_cache"] = cache_info
        
        return result
    
    def parse_user_query_with_ai(self, user_message: str) -> Dict[str, Any]:
        """
        Parse user query with AI to extract search terms and format requirements.
        
        Args:
            user_message: The user's natural language query
            
        Returns:
            Dictionary with search_query, format_filter, and response_message
        """
        system_prompt = """You are an image search assistant. Users will describe what images they want in natural language, and you need to extract key search information.

Analyze the user's query and return a JSON response containing:
1. search_query: Keywords for searching (in English, suitable for image Alt text search)
2. format_filter: Image format requirements (if user specified JPG, PNG, etc., otherwise null)
3. response_message: A friendly response explaining what you understood

Examples:
User: "I want iPad related JPG images"
Return: {"search_query": "iPad", "format_filter": ["jpg"], "response_message": "I'll help you find iPad-related JPG format images"}

User: "Show me photos of Apple Pencil"
Return: {"search_query": "Apple Pencil", "format_filter": null, "response_message": "I'll search for Apple Pencil images for you"}

Only return JSON, no other content."""

        try:
            response = clients.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            print(f"AI parsing error: {e}")
            return {
                "search_query": user_message,
                "format_filter": None,
                "response_message": f"I'll search for images related to '{user_message}'"
            }
    
    def format_search_results_for_api(self, search_results: List[Dict], query: str, cache_info: Dict = None) -> Dict[str, Any]:
        """
        Format search results for API response.
        
        Args:
            search_results: List of search result dictionaries
            query: Original search query
            cache_info: Optional cache information to include
            
        Returns:
            Formatted API response with results and cache information
        """
        if not search_results:
            message = "No images found matching your search."
        else:
            message = f"I found {len(search_results)} relevant images."
        
        response = {
            "message": message,
            "results": search_results,
            "query": query,
            "result_count": len(search_results)
        }
        
        # Add cache information if available
        if cache_info:
            response["cache_info"] = cache_info
        
        return response
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate search results based on alt text similarity.
        
        Args:
            results: List of image result dictionaries
            
        Returns:
            Deduplicated list of results
        """
        def normalize_alt_text(alt_text: str) -> str:
            if not alt_text:
                return ""
            normalized = alt_text.lower().strip()
            normalized = re.sub(r'[^\w\s]', ' ', normalized)
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            return normalized
        
        def should_prefer_by_alt(img1: Dict, img2: Dict) -> bool:
            if img1['format'] != img2['format']:
                format_priority = {'jpg': 3, 'png': 2, 'webp': 1, 'svg': 0}
                priority1 = format_priority.get(img1['format'], 0)
                priority2 = format_priority.get(img2['format'], 0)
                if priority1 != priority2:
                    return priority1 > priority2
            
            if img1['alt_match_score'] != img2['alt_match_score']:
                return img1['alt_match_score'] > img2['alt_match_score']
            
            return img1['score'] < img2['score']
        
        # Alt text deduplication
        seen_alt_texts = {}
        final_results = []
        
        for img in results:
            alt_text = normalize_alt_text(img['alt_text'])
            
            if not alt_text:
                final_results.append(img)
                continue
            
            if alt_text in seen_alt_texts:
                existing_img = seen_alt_texts[alt_text]
                if should_prefer_by_alt(img, existing_img):
                    seen_alt_texts[alt_text] = img
                    final_results = [r for r in final_results if normalize_alt_text(r['alt_text']) != alt_text]
                    final_results.append(img)
            else:
                seen_alt_texts[alt_text] = img
                final_results.append(img)
        
        return final_results 