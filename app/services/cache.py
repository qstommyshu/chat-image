"""
Redis Caching Service

This module provides a centralized caching service using Redis Cloud
for improving performance through HTML, query, and embedding caching.
"""

import json
import hashlib
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Union
from urllib.parse import urlparse

import redis
from redis.client import Redis
from redis.connection import ConnectionPool

from app.config import Config

# Set up cache-specific logger
cache_logger = logging.getLogger('cache')
cache_logger.setLevel(logging.INFO)

# Create console handler if it doesn't exist
if not cache_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    cache_logger.addHandler(console_handler)


class CacheMetrics:
    """
    Cache performance monitoring and metrics tracking.
    
    This class tracks cache hits, misses, and performance metrics
    to provide insights into cache effectiveness.
    """
    
    def __init__(self):
        """Initialize cache metrics tracking."""
        self._hits = {"html_cache": 0, "query_cache": 0, "embedding_cache": 0}
        self._misses = {"html_cache": 0, "query_cache": 0, "embedding_cache": 0}
        self._response_times = {"html_cache": [], "query_cache": [], "embedding_cache": []}
        self._cache_sizes = {"html_cache": 0, "query_cache": 0, "embedding_cache": 0}
        self._start_time = datetime.now()
    
    def track_hit(self, cache_type: str, response_time: float):
        """
        Track a cache hit event.
        
        Args:
            cache_type: Type of cache (html_cache, query_cache, embedding_cache)
            response_time: Response time in milliseconds
        """
        if cache_type in self._hits:
            self._hits[cache_type] += 1
            self._response_times[cache_type].append(response_time)
            
            # Log cache hit with performance info
            cache_logger.info(
                f"CACHE HIT - {cache_type}: {response_time:.2f}ms response time. "
                f"Total hits: {self._hits[cache_type]}"
            )
    
    def track_miss(self, cache_type: str, response_time: float):
        """
        Track a cache miss event.
        
        Args:
            cache_type: Type of cache (html_cache, query_cache, embedding_cache)
            response_time: Response time in milliseconds
        """
        if cache_type in self._misses:
            self._misses[cache_type] += 1
            self._response_times[cache_type].append(response_time)
            
            # Log cache miss
            cache_logger.debug(
                f"CACHE MISS - {cache_type}: {response_time:.2f}ms response time. "
                f"Total misses: {self._misses[cache_type]}"
            )
    
    def update_cache_size(self, cache_type: str, size_bytes: int):
        """
        Update the tracked size of a cache.
        
        Args:
            cache_type: Type of cache (html_cache, query_cache, embedding_cache)
            size_bytes: Size in bytes
        """
        if cache_type in self._cache_sizes:
            old_size = self._cache_sizes[cache_type]
            self._cache_sizes[cache_type] = size_bytes
            
            # Log significant size changes
            size_change = size_bytes - old_size
            if abs(size_change) > 1024 * 1024:  # Log changes > 1MB
                cache_logger.info(
                    f"CACHE SIZE UPDATE - {cache_type}: {size_bytes / (1024*1024):.2f}MB "
                    f"({size_change:+.2f}MB change)"
                )
    
    def get_hit_rate(self, cache_type: str = None) -> Union[float, Dict[str, float]]:
        """
        Calculate cache hit rate.
        
        Args:
            cache_type: Optional type of cache to get hit rate for
            
        Returns:
            Hit rate as float (0.0-1.0) or dict of hit rates by cache type
        """
        if cache_type:
            total = self._hits[cache_type] + self._misses[cache_type]
            return self._hits[cache_type] / total if total > 0 else 0.0
        
        # Return all hit rates
        result = {}
        for cache_type in self._hits:
            total = self._hits[cache_type] + self._misses[cache_type]
            result[cache_type] = self._hits[cache_type] / total if total > 0 else 0.0
        return result
    
    def get_avg_response_time(self, cache_type: str = None) -> Union[float, Dict[str, float]]:
        """
        Get average response time in milliseconds.
        
        Args:
            cache_type: Optional type of cache to get response time for
            
        Returns:
            Average response time or dict of response times by cache type
        """
        if cache_type:
            times = self._response_times[cache_type]
            return sum(times) / len(times) if times else 0.0
        
        # Return all response times
        result = {}
        for cache_type in self._response_times:
            times = self._response_times[cache_type]
            result[cache_type] = sum(times) / len(times) if times else 0.0
        return result
    
    def log_performance_summary(self):
        """Log a summary of cache performance metrics."""
        hit_rates = self.get_hit_rate()
        avg_times = self.get_avg_response_time()
        
        cache_logger.info("=== CACHE PERFORMANCE SUMMARY ===")
        for cache_type in self._hits:
            total_requests = self._hits[cache_type] + self._misses[cache_type]
            if total_requests > 0:
                cache_logger.info(
                    f"{cache_type}: {hit_rates[cache_type]:.1%} hit rate, "
                    f"{avg_times[cache_type]:.2f}ms avg response, "
                    f"{total_requests} total requests"
                )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics.
        
        Returns:
            Dict containing detailed cache performance metrics
        """
        stats = {}
        
        for cache_type in self._hits:
            total_requests = self._hits[cache_type] + self._misses[cache_type]
            hit_rate = self._hits[cache_type] / total_requests if total_requests > 0 else 0.0
            avg_response = self.get_avg_response_time(cache_type)
            
            stats[cache_type] = {
                "hit_rate": round(hit_rate, 3),
                "avg_response_time_ms": round(avg_response, 2),
                "total_hits": self._hits[cache_type],
                "total_misses": self._misses[cache_type],
                "cache_size_mb": round(self._cache_sizes[cache_type] / (1024 * 1024), 2)
            }
        
        stats["overall"] = {
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "total_cache_size_mb": round(sum(self._cache_sizes.values()) / (1024 * 1024), 2),
            "overall_hit_rate": round(
                sum(self._hits.values()) / 
                (sum(self._hits.values()) + sum(self._misses.values())) 
                if (sum(self._hits.values()) + sum(self._misses.values())) > 0 else 0.0,
                3
            )
        }
        
        return stats


class CacheService:
    """
    Centralized caching service with Redis Cloud integration.
    
    This service provides a unified interface for caching HTML content,
    search queries, and embeddings to improve system performance.
    """
    
    def __init__(self):
        """Initialize the cache service with Redis connection."""
        self.redis_client = self._init_redis()
        self.metrics = CacheMetrics()
        
        # Default TTL values in seconds
        self.default_ttls = {
            "html_cache": getattr(Config, "HTML_CACHE_TTL", 86400),  # 24 hours
            "query_cache": getattr(Config, "QUERY_CACHE_TTL", 3600),  # 1 hour
            "embedding_cache": getattr(Config, "EMBEDDING_CACHE_TTL", 2592000),  # 30 days
        }
        
        # Cache size limits in MB
        self.size_limits = {
            "html_cache": getattr(Config, "MAX_HTML_CACHE_SIZE_MB", 100) * 1024 * 1024,
            "query_cache": getattr(Config, "MAX_QUERY_CACHE_SIZE_MB", 50) * 1024 * 1024,
            "embedding_cache": getattr(Config, "MAX_EMBEDDING_CACHE_SIZE_MB", 200) * 1024 * 1024,
        }
        
        # Log cache service initialization
        if self.is_available():
            cache_logger.info("Cache service initialized successfully with Redis connection")
        else:
            cache_logger.warning("Cache service initialized but Redis is not available - operating in fallback mode")
    
    def _init_redis(self) -> Redis:
        """
        Initialize Redis connection pool and client.
        
        Returns:
            Redis client instance
        """
        try:
            # Get Redis connection parameters from config
            redis_url = getattr(Config, "REDIS_CLOUD_URL", None)
            
            if not redis_url:
                # Fallback to individual connection parameters
                host = getattr(Config, "REDIS_HOST", "localhost")
                port = getattr(Config, "REDIS_PORT", 6379)
                password = getattr(Config, "REDIS_PASSWORD", None)
                db = getattr(Config, "REDIS_DB", 0)
                
                cache_logger.info(f"Connecting to Redis at {host}:{port} (DB: {db})")
                
                # Create connection pool
                pool = ConnectionPool(
                    host=host,
                    port=port,
                    password=password,
                    db=db,
                    decode_responses=True,
                    max_connections=getattr(Config, "REDIS_MAX_CONNECTIONS", 20)
                )
            else:
                cache_logger.info("Connecting to Redis Cloud URL")
                
                # Create connection pool from URL
                pool = ConnectionPool.from_url(
                    redis_url,
                    decode_responses=True,
                    max_connections=getattr(Config, "REDIS_MAX_CONNECTIONS", 20)
                )
            
            # Create Redis client
            client = Redis(connection_pool=pool)
            
            # Test connection
            client.ping()
            cache_logger.info("Redis connection established successfully")
            
            return client
        
        except Exception as e:
            cache_logger.error(f"Failed to initialize Redis connection: {e}")
            # Return None to indicate connection failure
            return None
    
    def _generate_hash(self, data: Any) -> str:
        """
        Generate a hash for cache key.
        
        Args:
            data: Data to hash (string, dict, etc.)
            
        Returns:
            Hexadecimal hash string
        """
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        elif not isinstance(data, str):
            data = str(data)
        
        return hashlib.md5(data.encode('utf-8')).hexdigest()[:8]
    
    def _get_url_hash(self, url: str) -> str:
        """
        Generate a hash for a URL, considering relevant parts with normalization.
        
        Args:
            url: URL to hash
            
        Returns:
            URL hash string
        """
        # Parse URL to extract relevant parts
        parsed = urlparse(url)
        
        # Normalize the path to handle trailing slashes consistently
        # Keep root path as '/', strip trailing slashes from other paths
        # Also handle empty paths by treating them as root
        path = parsed.path.rstrip('/') if parsed.path and parsed.path != '/' else '/'
        if not path:  # Empty path becomes root
            path = '/'
        
        # Use netloc (domain) and normalized path for the hash
        # Query parameters can be included based on requirements
        relevant_parts = f"{parsed.netloc}{path}"
        
        return self._generate_hash(relevant_parts)
    
    def _detect_page_type(self, html_content: str, url: str) -> str:
        """
        Detect if a page is static or dynamic for TTL determination.
        
        Args:
            html_content: HTML content of the page
            url: URL of the page
            
        Returns:
            "static" or "dynamic"
        """
        # Simple heuristics for detecting page type
        dynamic_indicators = [
            "news", "blog", "article", "post",
            "rss", "feed", "update", "latest"
        ]
        
        # Check URL for dynamic indicators
        url_lower = url.lower()
        if any(indicator in url_lower for indicator in dynamic_indicators):
            return "dynamic"
        
        # Check for date patterns in URL (common in news/blogs)
        if any(str(year) in url for year in range(2020, datetime.now().year + 1)):
            return "dynamic"
        
        # Default to static for most corporate/product pages
        return "static"
    
    def _calculate_ttl(self, cache_type: str, metadata: Dict = None) -> int:
        """
        Calculate appropriate TTL based on content type and metadata.
        
        Args:
            cache_type: Type of cache (html_cache, query_cache, embedding_cache)
            metadata: Optional metadata for intelligent TTL decisions
            
        Returns:
            TTL in seconds
        """
        # Start with default TTL for this cache type
        ttl = self.default_ttls.get(cache_type, 3600)  # 1 hour default
        
        # Apply specific TTL logic based on cache type
        if cache_type == "html_cache" and metadata:
            page_type = metadata.get("page_type", "dynamic")
            
            if page_type == "static":
                # Longer TTL for static pages (7 days)
                ttl = 7 * 24 * 60 * 60
            else:
                # Shorter TTL for dynamic content (24 hours)
                ttl = 24 * 60 * 60
        
        elif cache_type == "query_cache" and metadata:
            # Adjust query cache TTL based on popularity
            popularity = metadata.get("popularity", "normal")
            
            if popularity == "high":
                # Popular queries get longer TTL (6 hours)
                ttl = 6 * 60 * 60
            elif popularity == "user_specific":
                # User-specific queries get shorter TTL (30 minutes)
                ttl = 30 * 60
        
        return ttl
    
    def _format_cache_age(self, timestamp_str: str) -> str:
        """
        Format cache age for user display.
        
        Args:
            timestamp_str: ISO format timestamp string
            
        Returns:
            Human-readable cache age (e.g., "2h 15m")
        """
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            delta = datetime.now() - timestamp
            
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            
            if days > 0:
                return f"{days}d {hours}h"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except Exception:
            return "unknown"
    

    
    def is_available(self) -> bool:
        """
        Check if Redis cache is available.
        
        Returns:
            True if Redis is connected and operational
        """
        if not self.redis_client:
            return False
        
        try:
            # Simple ping test to verify connection
            return self.redis_client.ping()
        except Exception:
            return False
    
    async def get_html_cache(self, url: str, limit: int = 1) -> Optional[Dict]:
        """
        Get cached HTML content for a URL with specific page limit.
        
        Args:
            url: URL to retrieve cached content for
            limit: Maximum number of pages crawled (affects cache key)
            
        Returns:
            Dict with cached HTML content or None if not found
        """
        start_time = time.time()
        cache_type = "html_cache"
        
        if not self.is_available():
            cache_logger.debug(f"Cache unavailable for HTML request: {url}")
            self.metrics.track_miss(cache_type, 0)
            return None
        
        try:
            # Generate cache key with page limit
            url_hash = self._get_url_hash(url)
            today = datetime.now().strftime("%Y-%m-%d")
            key = f"html:{url_hash}:{limit}:{today}"
            
            cache_logger.debug(f"Looking for HTML cache with key: {key} (limit={limit})")
            
            # Try to get cached content
            cached_data = self.redis_client.get(key)
            
            if not cached_data:
                # Also check yesterday's cache (for static content)
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                yesterday_key = f"html:{url_hash}:{limit}:{yesterday}"
                cache_logger.debug(f"Checking yesterday's cache: {yesterday_key}")
                cached_data = self.redis_client.get(yesterday_key)
            
            if cached_data:
                # Parse JSON data
                content = json.loads(cached_data)
                
                # Track hit
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.track_hit(cache_type, elapsed_ms)
                
                cache_age = self._format_cache_age(content.get("crawl_timestamp", ""))
                
                cache_logger.info(
                    f"HTML CACHE HIT for {url} (limit={limit}) - Age: {cache_age}, "
                    f"Response: {elapsed_ms:.2f}ms"
                )
                
                # Add cache metadata
                content["_cache"] = {
                    "hit": True,
                    "cache_type": cache_type,
                    "cache_age": cache_age,
                    "response_time_ms": round(elapsed_ms, 2)
                }
                
                return content
            else:
                # Track miss
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.track_miss(cache_type, elapsed_ms)
                cache_logger.debug(f"HTML CACHE MISS for {url} (limit={limit}) - will fetch fresh content")
                return None
        
        except Exception as e:
            cache_logger.error(f"Error retrieving from HTML cache for {url}: {e}")
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.track_miss(cache_type, elapsed_ms)
            return None
    
    async def set_html_cache(self, url: str, content: Dict, limit: int = 1, ttl: int = None) -> bool:
        """
        Cache HTML content with intelligent TTL.
        
        Args:
            url: URL being cached
            content: Dict with HTML content and metadata
            limit: Maximum number of pages crawled (affects cache key)
            ttl: Optional override for TTL in seconds
            
        Returns:
            True if caching was successful
        """
        if not self.is_available():
            cache_logger.debug(f"Cannot cache HTML for {url} - Redis unavailable")
            return False
        
        try:
            # Generate cache key with page limit
            url_hash = self._get_url_hash(url)
            today = datetime.now().strftime("%Y-%m-%d")
            key = f"html:{url_hash}:{limit}:{today}"
            
            # Ensure crawl timestamp exists
            if "crawl_timestamp" not in content:
                content["crawl_timestamp"] = datetime.now().isoformat()
            
            # Detect page type if not provided
            if "page_type" not in content and "html_content" in content:
                content["page_type"] = self._detect_page_type(content["html_content"], url)
            
            # Determine appropriate TTL
            if ttl is None:
                ttl = self._calculate_ttl("html_cache", content)
            
            # Store as JSON
            json_data = json.dumps(content)
            data_size_mb = len(json_data) / (1024 * 1024)
            
            # Update cache size tracking
            self.metrics.update_cache_size("html_cache", 
                                          self.metrics._cache_sizes["html_cache"] + len(json_data))
            
            # Set in Redis with TTL
            success = self.redis_client.setex(key, ttl, json_data)
            
            if success:
                cache_logger.info(
                    f"HTML CACHED for {url} (limit={limit}) - Size: {data_size_mb:.2f}MB, "
                    f"TTL: {ttl}s, Type: {content.get('page_type', 'unknown')}"
                )
            else:
                cache_logger.warning(f"Failed to cache HTML for {url}")
            
            return success
        
        except Exception as e:
            cache_logger.error(f"Error setting HTML cache for {url}: {e}")
            return False
    
    async def get_query_cache(self, query: str, namespace: str, filters: Dict) -> Optional[Dict]:
        """
        Get cached search results for a query.
        
        Args:
            query: Search query text
            namespace: Search namespace (e.g., user-specific namespace)
            filters: Dict of filters applied to the search
            
        Returns:
            Dict with search results or None if not found
        """
        start_time = time.time()
        cache_type = "query_cache"
        
        if not self.is_available():
            cache_logger.debug(f"Cache unavailable for query: {query[:50]}...")
            self.metrics.track_miss(cache_type, 0)
            return None
        
        try:
            # Generate cache key components
            query_hash = self._generate_hash(query)
            filters_hash = self._generate_hash(filters) if filters else "no-filter"
            
            # Create key
            key = f"query:{query_hash}:{namespace}:{filters_hash}"
            
            cache_logger.debug(f"Looking for query cache with key: {key}")
            
            # Try to get cached results
            cached_data = self.redis_client.get(key)
            
            if cached_data:
                # Parse JSON data
                results = json.loads(cached_data)
                
                # Track hit
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.track_hit(cache_type, elapsed_ms)
                
                cache_age = self._format_cache_age(results.get("search_timestamp", ""))
                result_count = len(results.get("results", []))
                
                cache_logger.info(
                    f"QUERY CACHE HIT for '{query[:50]}...' - Age: {cache_age}, "
                    f"Results: {result_count}, Response: {elapsed_ms:.2f}ms"
                )
                
                # Add cache metadata
                results["_cache"] = {
                    "hit": True,
                    "cache_type": cache_type,
                    "cache_age": cache_age,
                    "response_time_ms": round(elapsed_ms, 2)
                }
                
                return results
            else:
                # Track miss
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.track_miss(cache_type, elapsed_ms)
                cache_logger.debug(f"QUERY CACHE MISS for '{query[:50]}...' - will execute search")
                return None
        
        except Exception as e:
            cache_logger.error(f"Error retrieving from query cache for '{query[:50]}...': {e}")
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.track_miss(cache_type, elapsed_ms)
            return None
    
    async def set_query_cache(self, query: str, namespace: str, filters: Dict, 
                             results: Dict, ttl: int = None) -> bool:
        """
        Cache search results with TTL.
        
        Args:
            query: Search query text
            namespace: Search namespace
            filters: Dict of filters applied to the search
            results: Dict with search results
            ttl: Optional override for TTL in seconds
            
        Returns:
            True if caching was successful
        """
        if not self.is_available():
            return False
        
        try:
            # Generate cache key components
            query_hash = self._generate_hash(query)
            filters_hash = self._generate_hash(filters) if filters else "no-filter"
            
            # Create key
            key = f"query:{query_hash}:{namespace}:{filters_hash}"
            
            # Ensure search metadata is present
            if "search_timestamp" not in results:
                results["search_timestamp"] = datetime.now().isoformat()
            
            if "query" not in results:
                results["query"] = query
            
            if "namespace" not in results:
                results["namespace"] = namespace
                
            if "filters" not in results:
                results["filters"] = filters
            
            # Determine appropriate TTL based on query popularity
            # This is a placeholder - in a real system you might
            # track query frequency to determine popularity
            if ttl is None:
                popularity = "normal"  # Could be dynamically determined
                metadata = {"popularity": popularity}
                ttl = self._calculate_ttl("query_cache", metadata)
            
            # Store as JSON
            json_data = json.dumps(results)
            
            # Update cache size tracking
            self.metrics.update_cache_size("query_cache", 
                                          self.metrics._cache_sizes["query_cache"] + len(json_data))
            
            # Set in Redis with TTL
            success = self.redis_client.setex(key, ttl, json_data)
            
            if success:
                result_count = len(results.get("results", []))
                data_size_mb = len(json_data) / (1024 * 1024)
                cache_logger.info(
                    f"QUERY CACHED for '{query[:50]}...' - Results: {result_count}, "
                    f"Size: {data_size_mb:.2f}MB, TTL: {ttl}s"
                )
            else:
                cache_logger.warning(f"Failed to cache query '{query[:50]}...'")
            
            return success
        
        except Exception as e:
            cache_logger.error(f"Error setting query cache for '{query[:50]}...': {e}")
            return False
    
    async def get_embedding_cache(self, text: str, model: str = "default") -> Optional[List[float]]:
        """
        Get cached embedding vector.
        
        Args:
            text: Text to get embedding for
            model: Embedding model name
            
        Returns:
            List of embedding values or None if not found
        """
        start_time = time.time()
        cache_type = "embedding_cache"
        
        if not self.is_available():
            cache_logger.debug(f"Cache unavailable for embedding: {text[:30]}...")
            self.metrics.track_miss(cache_type, 0)
            return None
        
        try:
            # Generate cache key
            text_hash = self._generate_hash(text)
            key = f"embedding:{text_hash}:{model}"
            
            cache_logger.debug(f"Looking for embedding cache with key: {key}")
            
            # Try to get cached embedding
            cached_data = self.redis_client.get(key)
            
            if cached_data:
                # Parse JSON data
                data = json.loads(cached_data)
                embedding = data.get("embedding")
                
                # Track hit
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.track_hit(cache_type, elapsed_ms)
                
                cache_age = self._format_cache_age(data.get("created_timestamp", ""))
                
                cache_logger.info(
                    f"EMBEDDING CACHE HIT for '{text[:30]}...' (model: {model}) - "
                    f"Age: {cache_age}, Response: {elapsed_ms:.2f}ms"
                )
                
                return embedding
            else:
                # Track miss
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.track_miss(cache_type, elapsed_ms)
                cache_logger.debug(f"EMBEDDING CACHE MISS for '{text[:30]}...' - will generate embedding")
                return None
        
        except Exception as e:
            cache_logger.error(f"Error retrieving from embedding cache for '{text[:30]}...': {e}")
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.track_miss(cache_type, elapsed_ms)
            return None
    
    async def set_embedding_cache(self, text: str, embedding: List[float], 
                                 model: str = "default", ttl: int = None) -> bool:
        """
        Cache embedding vector with TTL.
        
        Args:
            text: Text the embedding is for
            embedding: List of embedding values
            model: Embedding model name
            ttl: Optional override for TTL in seconds
            
        Returns:
            True if caching was successful
        """
        if not self.is_available():
            cache_logger.debug(f"Cannot cache embedding for '{text[:30]}...' - Redis unavailable")
            return False
        
        try:
            # Generate cache key
            text_hash = self._generate_hash(text)
            key = f"embedding:{text_hash}:{model}"
            
            # Create data structure
            data = {
                "text": text,
                "embedding": embedding,
                "model": model,
                "created_timestamp": datetime.now().isoformat(),
                "token_count": len(text.split())  # Simple approximation
            }
            
            # Determine TTL
            if ttl is None:
                ttl = self.default_ttls.get("embedding_cache")
            
            # Store as JSON
            json_data = json.dumps(data)
            data_size_mb = len(json_data) / (1024 * 1024)
            
            # Update cache size tracking
            self.metrics.update_cache_size("embedding_cache", 
                                          self.metrics._cache_sizes["embedding_cache"] + len(json_data))
            
            # Set in Redis with TTL
            success = self.redis_client.setex(key, ttl, json_data)
            
            if success:
                cache_logger.info(
                    f"EMBEDDING CACHED for '{text[:30]}...' (model: {model}) - "
                    f"Dimensions: {len(embedding)}, Size: {data_size_mb:.2f}MB, TTL: {ttl}s"
                )
            else:
                cache_logger.warning(f"Failed to cache embedding for '{text[:30]}...'")
            
            return success
        
        except Exception as e:
            cache_logger.error(f"Error setting embedding cache for '{text[:30]}...': {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Redis key pattern to match (e.g., "html:*")
            
        Returns:
            Number of keys invalidated
        """
        if not self.is_available():
            cache_logger.debug(f"Cannot invalidate pattern '{pattern}' - Redis unavailable")
            return 0
        
        try:
            # Find all keys matching the pattern
            keys = self.redis_client.keys(pattern)
            
            if not keys:
                cache_logger.debug(f"No keys found matching pattern '{pattern}'")
                return 0
            
            # Delete all matching keys
            deleted_count = self.redis_client.delete(*keys)
            
            cache_logger.info(f"CACHE INVALIDATION - Pattern: '{pattern}', Deleted: {deleted_count} keys")
            
            return deleted_count
        
        except Exception as e:
            cache_logger.error(f"Error invalidating cache pattern '{pattern}': {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.
        
        Returns:
            Dict with detailed cache statistics
        """
        stats = self.metrics.get_performance_stats()
        
        if self.is_available():
            try:
                # Add Redis server info
                info = self.redis_client.info()
                stats["redis"] = {
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "uptime_in_days": info.get("uptime_in_days", 0),
                    "total_connections_received": info.get("total_connections_received", 0),
                    "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0)
                }
            except Exception as e:
                cache_logger.error(f"Error getting Redis info: {e}")
                stats["redis"] = {"status": "error", "error": str(e)}
        else:
            stats["redis"] = {"status": "unavailable"}
        
        return stats
    
    def log_cache_summary(self):
        """
        Log a comprehensive cache performance summary.
        
        This method provides a detailed overview of cache performance
        including hit rates, response times, and memory usage.
        """
        try:
            # Log performance metrics summary
            self.metrics.log_performance_summary()
            
            # Log Redis connection status
            if self.is_available():
                try:
                    info = self.redis_client.info()
                    cache_logger.info(
                        f"REDIS STATUS - Memory: {info.get('used_memory_human', 'unknown')}, "
                        f"Clients: {info.get('connected_clients', 0)}, "
                        f"Ops/sec: {info.get('instantaneous_ops_per_sec', 0)}"
                    )
                except Exception as e:
                    cache_logger.warning(f"Could not retrieve Redis info: {e}")
            else:
                cache_logger.warning("Redis cache is not available")
                
        except Exception as e:
            cache_logger.error(f"Error logging cache summary: {e}")


# Instantiate the cache service
cache_service = CacheService() 