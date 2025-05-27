"""
Unit Tests for Cache Service

This module contains comprehensive tests for the Redis caching service
including metrics tracking, cache operations, and error handling.
"""

import json
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from app.services.cache import CacheService, CacheMetrics


class TestCacheMetrics:
    """Test cases for CacheMetrics class."""
    
    def test_init(self):
        """Test CacheMetrics initialization."""
        metrics = CacheMetrics()
        
        assert metrics._hits["html_cache"] == 0
        assert metrics._hits["query_cache"] == 0
        assert metrics._hits["embedding_cache"] == 0
        assert metrics._misses["html_cache"] == 0
        assert isinstance(metrics._start_time, datetime)
    
    def test_track_hit(self):
        """Test tracking cache hits."""
        metrics = CacheMetrics()
        
        # Track a hit
        metrics.track_hit("html_cache", 50.0)
        
        assert metrics._hits["html_cache"] == 1
        assert metrics._response_times["html_cache"] == [50.0]
    
    def test_track_miss(self):
        """Test tracking cache misses."""
        metrics = CacheMetrics()
        
        # Track a miss
        metrics.track_miss("query_cache", 100.0)
        
        assert metrics._misses["query_cache"] == 1
        assert metrics._response_times["query_cache"] == [100.0]
    
    def test_get_hit_rate_single_cache(self):
        """Test hit rate calculation for single cache type."""
        metrics = CacheMetrics()
        
        # Add some hits and misses
        metrics.track_hit("html_cache", 50.0)
        metrics.track_hit("html_cache", 60.0)
        metrics.track_miss("html_cache", 200.0)
        
        hit_rate = metrics.get_hit_rate("html_cache")
        assert hit_rate == 2/3  # 2 hits out of 3 total
    
    def test_get_hit_rate_all_caches(self):
        """Test hit rate calculation for all cache types."""
        metrics = CacheMetrics()
        
        # Add data to multiple caches
        metrics.track_hit("html_cache", 50.0)
        metrics.track_miss("html_cache", 200.0)
        metrics.track_hit("query_cache", 30.0)
        metrics.track_hit("query_cache", 40.0)
        
        hit_rates = metrics.get_hit_rate()
        assert hit_rates["html_cache"] == 0.5  # 1/2
        assert hit_rates["query_cache"] == 1.0  # 2/2
        assert hit_rates["embedding_cache"] == 0.0  # 0/0
    
    def test_get_avg_response_time(self):
        """Test average response time calculation."""
        metrics = CacheMetrics()
        
        # Add response times
        metrics.track_hit("html_cache", 50.0)
        metrics.track_hit("html_cache", 100.0)
        metrics.track_miss("html_cache", 200.0)
        
        avg_time = metrics.get_avg_response_time("html_cache")
        assert avg_time == (50.0 + 100.0 + 200.0) / 3
    
    def test_update_cache_size(self):
        """Test cache size tracking."""
        metrics = CacheMetrics()
        
        # Update cache size
        metrics.update_cache_size("html_cache", 1024 * 1024)  # 1MB
        
        assert metrics._cache_sizes["html_cache"] == 1024 * 1024
    
    def test_get_performance_stats(self):
        """Test comprehensive performance statistics."""
        metrics = CacheMetrics()
        
        # Add some test data
        metrics.track_hit("html_cache", 50.0)
        metrics.track_miss("html_cache", 200.0)
        metrics.update_cache_size("html_cache", 1024 * 1024)
        
        stats = metrics.get_performance_stats()
        
        assert "html_cache" in stats
        assert "overall" in stats
        assert stats["html_cache"]["hit_rate"] == 0.5
        assert stats["html_cache"]["total_hits"] == 1
        assert stats["html_cache"]["total_misses"] == 1
        assert stats["overall"]["overall_hit_rate"] == 0.5


class TestCacheService:
    """Test cases for CacheService class."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = None
        mock_client.setex.return_value = True
        mock_client.delete.return_value = 1
        mock_client.keys.return_value = []
        mock_client.info.return_value = {
            'used_memory_human': '10MB',
            'connected_clients': 5,
            'uptime_in_days': 1
        }
        return mock_client
    
    @pytest.fixture
    def cache_service(self, mock_redis):
        """Create a CacheService instance with mocked Redis."""
        with patch('app.services.cache.CacheService._init_redis', return_value=mock_redis):
            service = CacheService()
            return service
    
    def test_init_redis_success(self):
        """Test successful Redis initialization."""
        with patch('app.services.cache.CacheService._init_redis') as mock_init:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_init.return_value = mock_client
            
            service = CacheService()
            
            assert service.redis_client == mock_client
            assert service.is_available() is True
    
    def test_init_redis_failure(self):
        """Test Redis initialization failure."""
        with patch('redis.ConnectionPool.from_url', side_effect=Exception("Connection failed")):
            service = CacheService()
            assert service.redis_client is None
    
    def test_is_available_true(self, cache_service):
        """Test cache availability when Redis is connected."""
        assert cache_service.is_available() is True
    
    def test_is_available_false(self):
        """Test cache availability when Redis is not connected."""
        with patch('app.services.cache.CacheService._init_redis', return_value=None):
            service = CacheService()
            assert service.is_available() is False
    
    def test_generate_hash(self, cache_service):
        """Test hash generation for cache keys."""
        # Test string input
        hash1 = cache_service._generate_hash("test string")
        hash2 = cache_service._generate_hash("test string")
        hash3 = cache_service._generate_hash("different string")
        
        assert hash1 == hash2  # Same input should produce same hash
        assert hash1 != hash3  # Different input should produce different hash
        assert len(hash1) == 8  # Hash should be 8 characters
        
        # Test dict input
        dict_hash = cache_service._generate_hash({"key": "value", "num": 123})
        assert len(dict_hash) == 8
    
    def test_get_url_hash_normalization(self, cache_service):
        """Test URL hash generation with normalization."""
        # Test trailing slash normalization
        hash1 = cache_service._get_url_hash("https://example.com/page")
        hash2 = cache_service._get_url_hash("https://example.com/page/")
        hash3 = cache_service._get_url_hash("https://example.com/")
        hash4 = cache_service._get_url_hash("https://example.com")
        
        assert hash1 == hash2  # Trailing slash should be normalized
        assert hash3 == hash4  # Root path normalization
        
        # Different paths should produce different hashes
        hash5 = cache_service._get_url_hash("https://example.com/different")
        assert hash1 != hash5
    
    def test_detect_page_type(self, cache_service):
        """Test page type detection for TTL determination."""
        # Test static page detection
        static_type = cache_service._detect_page_type("", "https://example.com/products")
        assert static_type == "static"
        
        # Test dynamic page detection
        dynamic_type = cache_service._detect_page_type("", "https://example.com/news/latest")
        assert dynamic_type == "dynamic"
        
        # Test date-based detection
        current_year = datetime.now().year
        date_type = cache_service._detect_page_type("", f"https://example.com/{current_year}/article")
        assert date_type == "dynamic"
    
    def test_calculate_ttl(self, cache_service):
        """Test TTL calculation based on content type."""
        # Test HTML cache TTL for static content
        static_ttl = cache_service._calculate_ttl("html_cache", {"page_type": "static"})
        assert static_ttl == 7 * 24 * 60 * 60  # 7 days
        
        # Test HTML cache TTL for dynamic content
        dynamic_ttl = cache_service._calculate_ttl("html_cache", {"page_type": "dynamic"})
        assert dynamic_ttl == 24 * 60 * 60  # 24 hours
        
        # Test query cache TTL for high popularity
        popular_ttl = cache_service._calculate_ttl("query_cache", {"popularity": "high"})
        assert popular_ttl == 6 * 60 * 60  # 6 hours
    
    def test_format_cache_age(self, cache_service):
        """Test cache age formatting."""
        # Test recent timestamp (minutes)
        recent = (datetime.now() - timedelta(minutes=30)).isoformat()
        age = cache_service._format_cache_age(recent)
        assert "30m" in age
        
        # Test older timestamp (hours)
        older = (datetime.now() - timedelta(hours=2, minutes=15)).isoformat()
        age = cache_service._format_cache_age(older)
        assert "2h 15m" in age
        
        # Test very old timestamp (days)
        very_old = (datetime.now() - timedelta(days=3, hours=5)).isoformat()
        age = cache_service._format_cache_age(very_old)
        assert "3d 5h" in age
    

    
    @pytest.mark.asyncio
    async def test_get_html_cache_hit(self, cache_service):
        """Test HTML cache retrieval with cache hit."""
        # Mock successful cache retrieval
        cache_data = {
            "url": "https://example.com",
            "html_content": "<html>test</html>",
            "crawl_timestamp": datetime.now().isoformat(),
            "page_type": "static"
        }
        cache_service.redis_client.get.return_value = json.dumps(cache_data)
        
        result = await cache_service.get_html_cache("https://example.com", 1)
        
        assert result is not None
        assert result["url"] == "https://example.com"
        assert "_cache" in result
        assert result["_cache"]["hit"] is True
        assert result["_cache"]["cache_type"] == "html_cache"
        assert "cache_age" in result["_cache"]
        
        # Verify Redis was called with correct key pattern
        cache_service.redis_client.get.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_html_cache_miss(self, cache_service):
        """Test HTML cache retrieval with cache miss."""
        # Mock cache miss
        cache_service.redis_client.get.return_value = None
        
        result = await cache_service.get_html_cache("https://example.com", 1)
        
        assert result is None
        
        # Should check both today and yesterday
        assert cache_service.redis_client.get.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_set_html_cache(self, cache_service):
        """Test HTML cache storage."""
        content = {
            "url": "https://example.com",
            "html_content": "<html>test</html>"
        }
        
        # Mock successful storage
        cache_service.redis_client.setex.return_value = True
        
        result = await cache_service.set_html_cache("https://example.com", content, 1)
        
        assert result is True
        cache_service.redis_client.setex.assert_called_once()
        
        # Verify the stored data includes crawl_timestamp
        call_args = cache_service.redis_client.setex.call_args
        stored_data = json.loads(call_args[0][2])  # Third argument is the JSON data
        assert "crawl_timestamp" in stored_data
    
    @pytest.mark.asyncio
    async def test_get_query_cache_hit(self, cache_service):
        """Test query cache retrieval with cache hit."""
        cache_data = {
            "query": "test query",
            "results": [{"url": "img1.jpg"}, {"url": "img2.jpg"}],
            "search_timestamp": datetime.now().isoformat()
        }
        cache_service.redis_client.get.return_value = json.dumps(cache_data)
        
        result = await cache_service.get_query_cache("test query", "namespace", {"max_results": 5})
        
        assert result is not None
        assert len(result["results"]) == 2
        assert "_cache" in result
        assert result["_cache"]["hit"] is True
        assert result["_cache"]["cache_type"] == "query_cache"
        assert "cache_age" in result["_cache"]
    
    @pytest.mark.asyncio
    async def test_set_query_cache(self, cache_service):
        """Test query cache storage."""
        results = {
            "results": [{"url": "img1.jpg"}],
            "result_count": 1
        }
        
        cache_service.redis_client.setex.return_value = True
        
        result = await cache_service.set_query_cache("test query", "namespace", {}, results)
        
        assert result is True
        cache_service.redis_client.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_embedding_cache_hit(self, cache_service):
        """Test embedding cache retrieval with cache hit."""
        cache_data = {
            "text": "test text",
            "embedding": [0.1, 0.2, 0.3],
            "created_timestamp": datetime.now().isoformat()
        }
        cache_service.redis_client.get.return_value = json.dumps(cache_data)
        
        result = await cache_service.get_embedding_cache("test text")
        
        assert result == [0.1, 0.2, 0.3]
    
    @pytest.mark.asyncio
    async def test_set_embedding_cache(self, cache_service):
        """Test embedding cache storage."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        cache_service.redis_client.setex.return_value = True
        
        result = await cache_service.set_embedding_cache("test text", embedding)
        
        assert result is True
        cache_service.redis_client.setex.assert_called_once()
        
        # Verify stored data structure
        call_args = cache_service.redis_client.setex.call_args
        stored_data = json.loads(call_args[0][2])
        assert stored_data["embedding"] == embedding
        assert "created_timestamp" in stored_data
    
    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, cache_service):
        """Test cache invalidation by pattern."""
        # Mock finding and deleting keys
        cache_service.redis_client.keys.return_value = ["html:key1", "html:key2"]
        cache_service.redis_client.delete.return_value = 2
        
        result = await cache_service.invalidate_pattern("html:*")
        
        assert result == 2
        cache_service.redis_client.keys.assert_called_once_with("html:*")
        cache_service.redis_client.delete.assert_called_once_with("html:key1", "html:key2")
    
    @pytest.mark.asyncio
    async def test_cache_unavailable_scenarios(self):
        """Test cache operations when Redis is unavailable."""
        # Create service with no Redis connection
        with patch('app.services.cache.CacheService._init_redis', return_value=None):
            service = CacheService()
            
            # All operations should handle unavailable cache gracefully
            html_result = await service.get_html_cache("https://example.com")
            assert html_result is None
            
            set_result = await service.set_html_cache("https://example.com", {})
            assert set_result is False
            
            query_result = await service.get_query_cache("query", "ns", {})
            assert query_result is None
            
            embedding_result = await service.get_embedding_cache("text")
            assert embedding_result is None
    
    @pytest.mark.asyncio
    async def test_redis_exceptions_handling(self, cache_service):
        """Test handling of Redis exceptions."""
        # Mock Redis operations to raise exceptions
        cache_service.redis_client.get.side_effect = Exception("Redis error")
        cache_service.redis_client.setex.side_effect = Exception("Redis error")
        
        # Operations should handle exceptions gracefully
        html_result = await cache_service.get_html_cache("https://example.com")
        assert html_result is None
        
        set_result = await cache_service.set_html_cache("https://example.com", {})
        assert set_result is False
    
    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache_service):
        """Test comprehensive cache statistics."""
        # Add some metrics data
        cache_service.metrics.track_hit("html_cache", 50.0)
        cache_service.metrics.track_miss("query_cache", 100.0)
        
        stats = await cache_service.get_cache_stats()
        
        assert "html_cache" in stats
        assert "query_cache" in stats
        assert "overall" in stats
        assert "redis" in stats
        
        # Should include Redis server info
        assert stats["redis"]["used_memory_human"] == "10MB"
    
    def test_log_cache_summary(self, cache_service):
        """Test cache summary logging."""
        # Add some test data
        cache_service.metrics.track_hit("html_cache", 50.0)
        cache_service.metrics.track_miss("html_cache", 200.0)
        
        # Should not raise any exceptions
        cache_service.log_cache_summary()
        
        # Verify metrics summary was called
        assert cache_service.metrics._hits["html_cache"] == 1
        assert cache_service.metrics._misses["html_cache"] == 1


class TestCacheIntegration:
    """Integration tests for cache service."""
    
    @pytest.mark.asyncio
    async def test_html_cache_workflow(self):
        """Test complete HTML cache workflow."""
        with patch('app.services.cache.CacheService._init_redis') as mock_init:
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.get.return_value = None  # Cache miss initially
            mock_redis.setex.return_value = True  # Successful storage
            mock_init.return_value = mock_redis
            
            service = CacheService()
            
            # Test cache miss
            result = await service.get_html_cache("https://example.com", 1)
            assert result is None
            
            # Test cache storage
            content = {
                "url": "https://example.com",
                "html_content": "<html>test</html>",
                "page_type": "static"
            }
            
            success = await service.set_html_cache("https://example.com", content, 1)
            assert success is True
            
            # Mock cache hit for next retrieval
            stored_content = content.copy()
            stored_content["crawl_timestamp"] = datetime.now().isoformat()
            mock_redis.get.return_value = json.dumps(stored_content)
            
            # Test cache hit
            cached_result = await service.get_html_cache("https://example.com", 1)
            assert cached_result is not None
            assert cached_result["url"] == "https://example.com"
            assert "_cache" in cached_result
            assert cached_result["_cache"]["hit"] is True
    
    @pytest.mark.asyncio 
    async def test_metrics_tracking_integration(self):
        """Test that metrics are properly tracked during cache operations."""
        with patch('app.services.cache.CacheService._init_redis') as mock_init:
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.get.return_value = json.dumps({
                "test": "data",
                "crawl_timestamp": datetime.now().isoformat()
            })
            mock_init.return_value = mock_redis
            
            service = CacheService()
            
            # Perform cache hit operation
            await service.get_html_cache("https://example.com", 1)
            
            # Verify metrics were tracked
            assert service.metrics._hits["html_cache"] == 1
            assert len(service.metrics._response_times["html_cache"]) == 1
            
            # Check hit rate calculation
            hit_rate = service.metrics.get_hit_rate("html_cache")
            assert hit_rate == 1.0  # 100% hit rate


if __name__ == "__main__":
    pytest.main([__file__]) 