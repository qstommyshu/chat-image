# Creative Design: Redis Cloud Caching Architecture

## Design Overview

### Caching Strategy Framework

We'll implement a **multi-layer caching strategy** that optimizes both crawl operations and search queries while maintaining data freshness and system reliability.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Query    │───▶│  Redis Cache    │───▶│  Data Source    │
│                 │    │                 │    │                 │
│ • Search Query  │    │ • Query Cache   │    │ • Firecrawl API │
│ • Page Request  │    │ • HTML Cache    │    │ • Vector DB     │
│ • Image Search  │    │ • Embedding     │    │ • OpenAI API    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │ Cache Analytics │
                       │ • Hit Rate      │
                       │ • Performance   │
                       │ • TTL Metrics   │
                       └─────────────────┘
```

## Cache Types & Key Design

### 1. HTML Page Cache

**Purpose**: Store crawled HTML content to avoid re-crawling identical pages

**Cache Key Pattern**:

```
html:{url_hash}:{timestamp_day}
```

**Example**:

```
html:a5f2d9e8:2024-01-15
```

**TTL Strategy**:

- **Default TTL**: 24 hours (news/dynamic content)
- **Extended TTL**: 7 days (static/corporate pages)
- **Auto-detect TTL**: Based on page meta tags or URL patterns

**Storage Structure**:

```json
{
  "url": "https://example.com/page",
  "html_content": "<!DOCTYPE html>...",
  "crawl_timestamp": "2024-01-15T10:30:00Z",
  "page_type": "dynamic|static",
  "image_count": 25,
  "size_bytes": 45000,
  "firecrawl_metadata": {...}
}
```

### 2. Search Query Cache

**Purpose**: Cache search results for identical queries to improve response time

**Cache Key Pattern**:

```
query:{query_hash}:{namespace}:{filters_hash}
```

**Example**:

```
query:d4e7f8c2:user-123:img-jpg-only
```

**TTL Strategy**:

- **Default TTL**: 1 hour (frequent updates)
- **Popular Query TTL**: 6 hours (trending searches)
- **User-specific TTL**: 30 minutes (personalized results)

**Storage Structure**:

```json
{
  "query": "red sports cars",
  "namespace": "user-123-crawl",
  "filters": {"format": "jpg", "min_size": 1024},
  "results": [
    {
      "url": "https://example.com/car1.jpg",
      "score": 0.89,
      "metadata": {...}
    }
  ],
  "result_count": 15,
  "search_timestamp": "2024-01-15T10:30:00Z",
  "embedding_version": "v1.0"
}
```

### 3. Embedding Cache

**Purpose**: Cache OpenAI embeddings to reduce API costs and latency

**Cache Key Pattern**:

```
embedding:{text_hash}:{model_version}
```

**Example**:

```
embedding:f9a3b7e1:text-embedding-ada-002
```

**TTL Strategy**:

- **Default TTL**: 30 days (embeddings are deterministic)
- **Model Update TTL**: 7 days (when model versions change)

**Storage Structure**:

```json
{
  "text": "red sports car with leather interior",
  "model": "text-embedding-ada-002",
  "embedding": [0.1, -0.3, 0.7, ...],
  "created_timestamp": "2024-01-15T10:30:00Z",
  "token_count": 8
}
```

## Cache Service Architecture

### Core Cache Service

```python
class CacheService:
    """Centralized caching service with Redis Cloud integration"""

    def __init__(self):
        self.redis_client = self._init_redis()
        self.metrics = CacheMetrics()

    async def get_html_cache(self, url: str) -> Optional[dict]:
        """Get cached HTML content for URL"""

    async def set_html_cache(self, url: str, content: dict, ttl: int = None):
        """Cache HTML content with intelligent TTL"""

    async def get_query_cache(self, query: str, namespace: str, filters: dict) -> Optional[dict]:
        """Get cached search results"""

    async def set_query_cache(self, query: str, results: dict, ttl: int = None):
        """Cache search results with TTL"""

    async def get_embedding_cache(self, text: str, model: str) -> Optional[list]:
        """Get cached embedding vector"""

    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern"""
```

### Cache Integration Layers

#### 1. Crawler Service Integration

```python
class CachedCrawlerService(CrawlerService):
    """Enhanced crawler with cache integration"""

    async def crawl_with_cache(self, url: str) -> dict:
        # Check cache first
        cached_html = await self.cache.get_html_cache(url)
        if cached_html:
            return {
                **cached_html,
                "cache_hit": True,
                "cache_age": self._calculate_age(cached_html)
            }

        # Crawl fresh content
        fresh_content = await self.crawl_url(url)

        # Cache for future use
        await self.cache.set_html_cache(url, fresh_content)

        return {
            **fresh_content,
            "cache_hit": False,
            "cached_at": datetime.now().isoformat()
        }
```

#### 2. Search Service Integration

```python
class CachedSearchService(SearchService):
    """Enhanced search with query result caching"""

    async def search_with_cache(self, query: str, namespace: str, filters: dict) -> dict:
        # Check query cache
        cached_results = await self.cache.get_query_cache(query, namespace, filters)
        if cached_results:
            return {
                **cached_results,
                "cache_hit": True,
                "cache_source": "query_cache"
            }

        # Check embedding cache
        cached_embedding = await self.cache.get_embedding_cache(query)
        if cached_embedding:
            # Use cached embedding for fresh search
            results = await self.vector_search(cached_embedding, namespace, filters)
            cache_source = "embedding_cache"
        else:
            # Generate fresh embedding and search
            results = await self.search_fresh(query, namespace, filters)
            cache_source = "fresh"

        # Cache results
        await self.cache.set_query_cache(query, results)

        return {
            **results,
            "cache_hit": False,
            "cache_source": cache_source
        }
```

## Cache Hit Indicators & User Experience

### API Response Enhancement

```json
{
  "data": {...},
  "cache_info": {
    "cache_hit": true,
    "cache_type": "html_cache",
    "cache_age": "2h 15m",
    "cache_ttl_remaining": "21h 45m",
    "performance_gain": "85% faster"
  },
  "metrics": {
    "response_time_ms": 150,
    "without_cache_estimate_ms": 1000
  }
}
```

### UI Cache Indicators

- **🚀 Cache Hit Badge**: Green indicator showing cache hit
- **⚡ Performance Boost**: Shows time saved (e.g., "85% faster")
- **🕐 Cache Age**: Shows when data was originally fetched
- **📊 Cache Stats**: Dashboard showing hit rates and performance

### Real-time Cache Status

```javascript
// SSE message for cache status
{
  "type": "cache_status",
  "data": {
    "session_id": "abc123",
    "url": "https://example.com",
    "cache_hit": true,
    "time_saved_ms": 850,
    "cache_age": "1h 30m"
  }
}
```

## Cache Configuration & Monitoring

### Environment Configuration

```python
# Redis Cloud Configuration
REDIS_CLOUD_URL = "redis://username:password@host:port"
REDIS_MAX_CONNECTIONS = 20
REDIS_CONNECTION_POOL_SIZE = 10

# Cache TTL Configuration
HTML_CACHE_TTL = 86400  # 24 hours
QUERY_CACHE_TTL = 3600  # 1 hour
EMBEDDING_CACHE_TTL = 2592000  # 30 days

# Cache Size Limits
MAX_HTML_CACHE_SIZE_MB = 100
MAX_QUERY_CACHE_SIZE_MB = 50
MAX_EMBEDDING_CACHE_SIZE_MB = 200

# Performance Thresholds
CACHE_HIT_RATE_TARGET = 0.7  # 70% hit rate
CACHE_RESPONSE_TIME_TARGET_MS = 100
```

### Cache Metrics & Analytics

```python
class CacheMetrics:
    """Cache performance monitoring"""

    def track_hit(self, cache_type: str, response_time: float):
        """Track cache hit metrics"""

    def track_miss(self, cache_type: str, response_time: float):
        """Track cache miss metrics"""

    def get_hit_rate(self, cache_type: str = None) -> float:
        """Calculate cache hit rate"""

    def get_performance_stats(self) -> dict:
        """Get comprehensive performance statistics"""
        return {
            "html_cache": {
                "hit_rate": 0.82,
                "avg_response_time_ms": 95,
                "total_hits": 1250,
                "total_misses": 275,
                "cache_size_mb": 75.5
            },
            "query_cache": {
                "hit_rate": 0.65,
                "avg_response_time_ms": 120,
                "total_hits": 890,
                "total_misses": 480,
                "cache_size_mb": 32.1
            }
        }
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

- [x] Redis Cloud setup and connection
- [x] Base CacheService implementation
- [x] Cache key strategy implementation
- [x] Basic TTL management

### Phase 2: Crawler Integration (Week 2)

- [x] HTML page caching in CrawlerService
- [x] Cache hit/miss tracking
- [x] TTL-based cache invalidation
- [x] Fallback mechanisms

### Phase 3: Search Integration (Week 3)

- [x] Query result caching
- [x] Embedding caching
- [x] Search performance optimization
- [x] Cache-aware search flow

### Phase 4: User Experience (Week 4)

- [x] Cache hit indicators in API
- [x] UI cache status displays
- [x] Performance metrics dashboard
- [x] Cache management controls

### Phase 5: Monitoring & Optimization (Week 5)

- [x] Cache analytics and reporting
- [x] Automatic cache optimization
- [x] Performance tuning
- [x] Production monitoring setup

## Risk Mitigation

### Redis Unavailability

- **Graceful degradation**: Continue operation without cache
- **Circuit breaker**: Temporarily disable cache on repeated failures
- **Health checks**: Monitor Redis connectivity
- **Fallback strategy**: Local in-memory cache for critical operations

### Cache Consistency

- **TTL management**: Automatic expiration of stale data
- **Invalidation strategies**: Smart cache clearing on updates
- **Version tracking**: Embedding model version tracking
- **Data validation**: Verify cached data integrity

### Performance Impact

- **Connection pooling**: Efficient Redis connection management
- **Async operations**: Non-blocking cache operations
- **Size limits**: Prevent cache from growing too large
- **Monitoring**: Real-time performance tracking
