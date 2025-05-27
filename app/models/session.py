"""
Session Management

This module contains the CrawlSession class and session management utilities.
"""

import queue
import threading
from datetime import datetime
from typing import Dict, Optional


class CrawlSession:
    """
    Represents a single website crawling session.
    
    This class manages the state and progress of a crawl operation,
    including status tracking, message queuing for SSE, and result storage.
    
    Attributes:
        session_id (str): Unique identifier for this session
        url (str): The URL being crawled
        limit (int): Maximum number of pages to crawl
        status (str): Current status (initializing, crawling, processing, indexing, completed, error)
        messages (Queue): Queue of status messages for SSE
        total_images (int): Total number of images found
        total_pages (int): Total number of pages crawled
        error (str): Error message if crawl failed
        completed (bool): Whether the crawl has finished successfully
        image_stats (dict): Statistics about images found (formats, pages)
        skip_cache (bool): Whether to skip cache lookup for this session
        cache_hits (int): Number of cache hits during this session
    """
    
    def __init__(self, session_id: str, url: str, limit: int, skip_cache: bool = False):
        """
        Initialize a new crawl session.
        
        Args:
            session_id: Unique identifier for this session
            url: The URL being crawled
            limit: Maximum number of pages to crawl
            skip_cache: Whether to skip cache lookup for this session
        """
        self.session_id = session_id
        self.url = url
        self.limit = limit
        self.status = "initializing"
        self.messages = queue.Queue()
        self.total_images = 0
        self.total_pages = 0
        self.error = None
        self.completed = False
        self.image_stats = {}
        
        # Cache-related properties
        self.skip_cache = skip_cache
        self.cache_hits = 0
        
    def add_message(self, message_type: str, data: dict):
        """
        Add a status message to the SSE queue.
        
        Args:
            message_type (str): Type of message (status, progress, completed, error)
            data (dict): Message data to send to client
        """
        self.messages.put({
            "type": message_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })


class SessionManager:
    """
    Manages crawl sessions and domain tracking.
    
    This class provides thread-safe session management with concurrency controls
    to prevent duplicate domain crawls and enforce session limits.
    """
    
    def __init__(self, max_concurrent_crawls: int = None):
        from app.config import Config
        self.crawl_sessions: Dict[str, CrawlSession] = {}
        self.session_namespaces: Dict[str, str] = {}  # Maps session_id to Pinecone namespace
        self.crawl_lock = threading.Lock()
        self.max_concurrent_crawls = max_concurrent_crawls or Config.MAX_CONCURRENT_CRAWLS
        
    def create_session(self, session_id: str, url: str, limit: int, domain: str, skip_cache: bool = False) -> tuple[CrawlSession, Optional[str]]:
        """
        Create a new crawl session with concurrency checks.
        
        Args:
            session_id: Unique session identifier
            url: URL to crawl
            limit: Maximum pages to crawl
            domain: Domain being crawled (kept for backwards compatibility but not used for restrictions)
            skip_cache: Whether to skip cache lookup for this session
            
        Returns:
            Tuple of (session, error_message). Error message is None if successful.
        """
        with self.crawl_lock:
            # Check concurrent crawl limits
            active_count = len([
                s for s in self.crawl_sessions.values() 
                if s.status in ["crawling", "processing", "indexing"]
            ])
            
            if active_count >= self.max_concurrent_crawls:
                return None, f"Maximum {self.max_concurrent_crawls} concurrent crawls allowed. Please try again later."
            
            # Create session - each user gets their own isolated session and namespace
            session = CrawlSession(session_id, url, limit, skip_cache)
            self.crawl_sessions[session_id] = session
            
            return session, None
    
    def get_session(self, session_id: str) -> Optional[CrawlSession]:
        """Get a session by ID."""
        return self.crawl_sessions.get(session_id)
    
    def set_namespace(self, session_id: str, namespace: str):
        """Set the Pinecone namespace for a session."""
        self.session_namespaces[session_id] = namespace
    
    def get_namespace(self, session_id: str) -> Optional[str]:
        """Get the Pinecone namespace for a session."""
        return self.session_namespaces.get(session_id)


# Global session manager instance
session_manager = SessionManager() 