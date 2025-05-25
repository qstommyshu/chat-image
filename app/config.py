"""
Configuration Management

This module handles all configuration settings, environment variables,
and initialization of external service clients.
"""

import os
import time
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

# Load environment variables
load_dotenv()


class Config:
    """Base configuration class."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    
    # Server settings
    HOST = "0.0.0.0"
    PORT = int(os.environ.get("PORT", 5001))
    
    # SSE Configuration
    ENABLE_SSE = os.environ.get("ENABLE_SSE", "true").lower() in ("true", "1", "yes")
    SSE_TIMEOUT_SECONDS = int(os.environ.get("SSE_TIMEOUT_SECONDS", "300"))
    
    # Concurrency settings
    MAX_CONCURRENT_CRAWLS = int(os.environ.get("MAX_CONCURRENT_CRAWLS", "3"))
    
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    
    # Pinecone settings
    PINECONE_INDEX_NAME = "image-chat"
    PINECONE_DIMENSION = 1536
    PINECONE_METRIC = "cosine"
    PINECONE_CLOUD = "aws"
    PINECONE_REGION = "us-east-1"
    
    @classmethod
    def validate_api_keys(cls):
        """Validate that all required API keys are present."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("Please set OPENAI_API_KEY in your .env file")
        if not cls.FIRECRAWL_API_KEY:
            raise ValueError("Please set FIRECRAWL_API_KEY in your .env file")
        if not cls.PINECONE_API_KEY:
            raise ValueError("Please set PINECONE_API_KEY in your .env file")


class ClientManager:
    """Manages initialization of external service clients."""
    
    def __init__(self):
        Config.validate_api_keys()
        self._openai_client = None
        self._firecrawl_app = None
        self._pinecone_client = None
        self._vector_store = None
        self._embeddings = None
        
    @property
    def openai_client(self):
        """Lazy-loaded OpenAI client."""
        if self._openai_client is None:
            self._openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        return self._openai_client
        
    @property
    def firecrawl_app(self):
        """Lazy-loaded Firecrawl client."""
        if self._firecrawl_app is None:
            self._firecrawl_app = FirecrawlApp(api_key=Config.FIRECRAWL_API_KEY)
        return self._firecrawl_app
        
    @property
    def pinecone_client(self):
        """Lazy-loaded Pinecone client."""
        if self._pinecone_client is None:
            self._pinecone_client = Pinecone(api_key=Config.PINECONE_API_KEY)
            self._ensure_pinecone_index()
        return self._pinecone_client
        
    @property
    def embeddings(self):
        """Lazy-loaded OpenAI embeddings."""
        if self._embeddings is None:
            self._embeddings = OpenAIEmbeddings(openai_api_key=Config.OPENAI_API_KEY)
        return self._embeddings
        
    @property
    def vector_store(self):
        """Lazy-loaded Pinecone vector store."""
        if self._vector_store is None:
            index = self.pinecone_client.Index(Config.PINECONE_INDEX_NAME)
            self._vector_store = PineconeVectorStore(
                index=index, 
                embedding=self.embeddings
            )
        return self._vector_store
        
    def _ensure_pinecone_index(self):
        """Create Pinecone index if it doesn't exist."""
        existing_indexes = [index_info["name"] for index_info in self._pinecone_client.list_indexes()]
        
        if Config.PINECONE_INDEX_NAME not in existing_indexes:
            self._pinecone_client.create_index(
                name=Config.PINECONE_INDEX_NAME,
                dimension=Config.PINECONE_DIMENSION,
                metric=Config.PINECONE_METRIC,
                spec=ServerlessSpec(
                    cloud=Config.PINECONE_CLOUD, 
                    region=Config.PINECONE_REGION
                ),
                deletion_protection="disabled",  # Allow deletion for development
            )
            
            # Wait for index to be ready
            while not self._pinecone_client.describe_index(Config.PINECONE_INDEX_NAME).status["ready"]:
                time.sleep(1)


# Global client manager instance
clients = ClientManager() 