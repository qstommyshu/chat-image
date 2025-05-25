"""
Session models for crawl operations.

This module defines the CrawlSession class that represents a single crawl operation
and manages its state, messages, and results.
"""
import queue
from datetime import datetime


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
        folder_name (str): Folder where HTML files are saved
        total_images (int): Total number of images found
        total_pages (int): Total number of pages crawled
        error (str): Error message if crawl failed
        completed (bool): Whether the crawl has finished successfully
        image_stats (dict): Statistics about images found (formats, pages)
    """
    
    def __init__(self, session_id, url, limit):
        """Initialize a new crawl session."""
        self.session_id = session_id
        self.url = url
        self.limit = limit
        self.status = "initializing"
        self.messages = queue.Queue()
        self.folder_name = None
        self.total_images = 0
        self.total_pages = 0
        self.error = None
        self.completed = False
        self.image_stats = {}
        
    def add_message(self, message_type, data):
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
    
    def to_dict(self):
        """
        Convert session to a dictionary for JSON serialization.
        
        Returns:
            dict: Session data in dictionary format
        """
        # Get creation timestamp from first message if available
        created_at = None
        if not self.messages.empty():
            try:
                created_at = self.messages.queue[0]['timestamp']
            except (IndexError, KeyError):
                pass
        
        return {
            "session_id": self.session_id,
            "url": self.url,
            "status": self.status,
            "total_images": self.total_images,
            "total_pages": self.total_pages,
            "completed": self.completed,
            "created_at": created_at,
            "folder_name": self.folder_name
        } 