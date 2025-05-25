"""
Application Configuration

This module contains all configuration settings for the Flask application.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Server configuration
DEBUG = True
PORT = 5000
THREADED = True

# Crawling configuration
MAX_CONCURRENT_CRAWLS = 3  # Maximum number of simultaneous crawl operations

# Crawl options
DEFAULT_CRAWL_LIMIT = 10  # Default number of pages to crawl per session
DEFAULT_WAIT_TIME = 3000  # Milliseconds to wait for JavaScript rendering

# Search configuration
DEFAULT_SEARCH_RESULTS = 5  # Default number of search results to return

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Cleanup configuration
DEFAULT_CLEANUP_HOURS = 24  # Default hours before cleaning up old sessions
