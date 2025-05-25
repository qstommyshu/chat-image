# Flask Server Modular Architecture v2.0

## Overview

The Flask server has been refactored from a monolithic 1300+ line file into a clean, maintainable modular architecture. This improves code organization, testability, and maintainability.

## Project Structure

```
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration management
│   ├── models/
│   │   ├── __init__.py
│   │   └── session.py           # CrawlSession & SessionManager classes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── crawler.py           # Website crawling logic
│   │   ├── processor.py         # HTML processing & image extraction
│   │   └── search.py            # AI-powered image search
│   ├── api/
│   │   ├── __init__.py
│   │   ├── crawl.py             # Crawl endpoints (/crawl, /sessions)
│   │   ├── chat.py              # Chat/search endpoint (/chat)
│   │   ├── status.py            # Status endpoints (SSE & polling)
│   │   └── health.py            # Health check (/health)
│   └── utils/
│       ├── __init__.py
│       └── html_utils.py        # HTML processing utilities
├── flask_server.py              # Original monolithic file (legacy)
├── flask_server_new.py          # New modular entry point
├── REPLIT_CONFIG.md            # Deployment configuration guide
└── README_MODULAR.md           # This file
```

## Key Improvements

### ✅ **Separation of Concerns**

- **Configuration**: `app/config.py` - All settings and client initialization
- **Models**: `app/models/` - Data structures and state management
- **Services**: `app/services/` - Business logic layer
- **API**: `app/api/` - Route handlers grouped by functionality
- **Utils**: `app/utils/` - Reusable utility functions

### ✅ **Better Testability**

- Each component can be tested independently
- Service layer is decoupled from Flask routes
- Dependency injection through configuration

### ✅ **Improved Maintainability**

- Each file has a single responsibility
- Easier to locate and modify specific functionality
- Clear interfaces between components

### ✅ **Scalability**

- Easy to add new API endpoints
- Service layer can be extended without touching routes
- Configuration is centralized and environment-aware

## Component Details

### Configuration (`app/config.py`)

- **Config class**: Environment variables and settings
- **ClientManager class**: Lazy-loaded external service clients
- **API key validation**: Ensures required keys are present

### Models (`app/models/`)

- **CrawlSession**: Represents individual crawl operations
- **SessionManager**: Thread-safe session management with concurrency controls

### Services (`app/services/`)

- **CrawlerService**: Handles Firecrawl operations and background processing
- **HTMLProcessor**: Extracts images from HTML content (no disk I/O)
- **SearchService**: AI-powered query parsing and semantic search

### API (`app/api/`)

- **crawl.py**: Session creation, listing, deletion, cleanup
- **status.py**: Real-time SSE and polling status endpoints
- **chat.py**: Natural language image search
- **health.py**: Health monitoring

### Utils (`app/utils/`)

- **html_utils.py**: URL/filename conversion, image format detection, context extraction

## Running the Modular Version

### Option 1: Use New Entry Point

```bash
python flask_server_new.py
```

### Option 2: Update Current Entry Point

Replace the content of `flask_server.py` with the content from `flask_server_new.py`.

## Configuration

All configuration is now centralized in `app/config.py`. Set these environment variables:

```bash
# Required API Keys
OPENAI_API_KEY=your_key_here
FIRECRAWL_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here

# Optional Configuration
ENABLE_SSE=true                    # Enable/disable Server-Sent Events
SSE_TIMEOUT_SECONDS=300           # SSE connection timeout
MAX_CONCURRENT_CRAWLS=3           # Maximum simultaneous crawls
FLASK_DEBUG=false                 # Debug mode (production: false)
PORT=5001                         # Server port
```

## Benefits of the New Architecture

### 🚀 **Performance**

- Direct memory processing (no disk I/O)
- Optimized Pinecone batching
- Efficient session management

### 🛠️ **Developer Experience**

- Clear code organization
- Easy to find and modify specific features
- Comprehensive type hints
- Detailed documentation

### 🔧 **Production Ready**

- Environment-aware configuration
- Robust error handling
- Graceful resource cleanup
- Production/development modes

### 📊 **Monitoring & Debugging**

- Centralized logging
- Health check endpoints
- Session management tools
- Error tracking

## API Compatibility

The modular version is **100% backward compatible** with the original API. All endpoints work exactly the same:

- `POST /crawl` - Start crawling
- `GET /crawl/{id}/status` - SSE status updates
- `GET /crawl/{id}/status-simple` - Polling status
- `POST /chat` - Image search
- `GET /sessions` - List sessions
- `DELETE /sessions/{id}` - Delete session
- `POST /cleanup` - Clean old sessions
- `GET /health` - Health check

## Migration Guide

1. **No Breaking Changes**: The API is fully compatible
2. **Environment Variables**: Same as before, optionally add new config options
3. **Dependencies**: No new dependencies required
4. **Deployment**: Can deploy the new version directly

## Future Enhancements

The modular architecture makes it easy to add:

- ✨ Authentication & authorization
- ✨ Rate limiting per user
- ✨ Image processing pipelines
- ✨ Multiple search backends
- ✨ Caching layers
- ✨ Metrics and analytics
- ✨ Background job queues
- ✨ API versioning

## Development Workflow

### Adding New API Endpoints

1. Create new function in appropriate `app/api/` file
2. Add route to blueprint
3. Import in `app/__init__.py` if new blueprint

### Adding New Services

1. Create new service class in `app/services/`
2. Import in `app/services/__init__.py`
3. Use in API handlers or other services

### Adding Configuration

1. Add to `Config` class in `app/config.py`
2. Add environment variable
3. Use via `Config.VARIABLE_NAME`

## Testing

The modular structure enables comprehensive testing:

```python
# Test service layer independently
from app.services.search import SearchService
search_service = SearchService()

# Test with mock dependencies
from unittest.mock import Mock
crawler_service.firecrawl_app = Mock()

# Test API endpoints
from app import create_app
app = create_app()
client = app.test_client()
```

This modular architecture provides a solid foundation for maintaining and extending the Flask server while keeping the complexity manageable.
