"""
Search Service

This module handles image search functionality including AI-powered query parsing,
semantic search, and result deduplication.
"""

import json
import re
from typing import List, Dict, Any, Optional

from app.config import clients


class SearchService:
    """Service class for handling image search operations."""
    
    def search_images_with_dedup(
        self, 
        query: str, 
        namespace: str, 
        format_filter: Optional[List[str]] = None, 
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search images with deduplication and ranking.
        
        Args:
            query: Search query string
            namespace: Pinecone namespace to search in
            format_filter: Optional list of image formats to filter by
            max_results: Maximum number of results to return
            
        Returns:
            List of image result dictionaries
        """
        # Create a retriever with the specific namespace for this session
        retriever = clients.vector_store.as_retriever(
            search_kwargs={"k": 50, "namespace": namespace}
        )
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
    
    def format_search_results_for_api(self, search_results: List[Dict], query: str) -> str:
        """
        Format search results for API response.
        
        Args:
            search_results: List of search result dictionaries
            query: Original search query (not used in current implementation)
            
        Returns:
            Formatted summary text
        """
        if not search_results:
            return "No images found matching your search."
        
        return f"I found {len(search_results)} relevant images:"
    
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