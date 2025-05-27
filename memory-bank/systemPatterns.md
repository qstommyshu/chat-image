# System Patterns

## Architectural Patterns

### Service Layer Pattern

**Benefits:**

- Clean separation of concerns
- Testable business logic
- Reusable service components
- Clear dependency injection

### Blueprint Architecture

**Benefits:**

- Modular route organization
- Independent feature development
- Easy testing and maintenance
- Clear API structure

## Data Flow Patterns

### Crawling Pipeline

### Search Pipeline

### Real-time Updates

## Concurrency Patterns

### Session Management

- **Thread-safe SessionManager** with concurrent operation limits
- **Domain locking** prevents simultaneous crawls of same domain
- **Session isolation** with unique namespaces per user

### Resource Management

- **Lazy client initialization** for external services
- **Connection pooling** for HTTP requests
- **Timeout management** for long-running operations

## Error Handling Patterns

### Graceful Degradation

- SSE fallback to polling for incompatible environments
- Partial results on crawling failures
- Continuation on individual page failures

### Circuit Breaker Pattern

- Rate limiting for external API calls
- Retry logic with exponential backoff
- Fallback strategies for service unavailability

## Performance Patterns

### Memory Optimization

- **URL-only storage** instead of full image storage
- **Streaming processing** for large HTML documents
- **Lazy loading** of images from original sources

### Caching Strategies

- **Session state caching** for active crawls
- **Vector embedding reuse** for similar queries
- **HTTP response caching** for static resources
- **Multi-layer Redis caching** with HTML, query, and embedding caches
- **Intelligent TTL management** based on content type and freshness requirements
- **Cache hit indicators** for user experience and performance monitoring

### Redis Caching Architecture

- **HTML Page Cache**: 24-hour TTL for crawled content with URL-based keys
- **Search Query Cache**: 1-hour TTL for search results with query+filter hashing
- **Embedding Cache**: 30-day TTL for OpenAI embeddings with text+model keys
- **Cache-aside pattern**: Check cache first, populate on miss
- **Write-through caching**: Update cache immediately after data changes
- **Cache warming**: Pre-populate frequently accessed data

## Security Patterns

### API Key Management

- Environment variable configuration
- Lazy initialization to prevent exposure
- Secure storage practices

### Input Validation

- URL format validation
- Parameter sanitization
- Rate limiting per session

### Cross-Origin Security

- CORS configuration for web clients
- Content Security Policy headers
- Request origin validation
