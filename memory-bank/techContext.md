# Technical Context

## Technology Stack

### Backend Framework
- **Flask**: Lightweight web framework with Blueprint architecture
- **Gunicorn**: WSGI HTTP Server for production deployment
- **Flask-CORS**: Cross-Origin Resource Sharing support

### AI/ML Technologies
- **OpenAI**: GPT models for embeddings and natural language processing
- **LangChain**: Framework for orchestrating AI/ML workflows
- **LangChain-OpenAI**: OpenAI integration for LangChain
- **LangChain-Community**: Community-driven LangChain extensions

### Vector Database
- **Pinecone**: Cloud-based vector database for semantic search
- **ChromaDB**: Alternative vector database (included in dependencies)

### Web Crawling
- **Firecrawl**: Advanced web crawler with JavaScript rendering
- **BeautifulSoup4**: HTML parsing and extraction
- **Requests**: HTTP library for web requests

### Development Tools
- **Python-dotenv**: Environment variable management
- **SSEClient-py**: Server-Sent Events client library

## Architecture Patterns

### Service Layer Pattern
- **CrawlerService**: Orchestrates website crawling operations
- **ProcessorService**: Handles HTML parsing and image extraction
- **SearchService**: Manages AI-powered search and deduplication

### Blueprint Architecture
- **crawl_bp**: Crawling operations endpoints
- **status_bp**: Real-time status monitoring
- **chat_bp**: Natural language search interface
- **health_bp**: Health checks and monitoring

### Session Management
- **Thread-safe SessionManager**: Concurrent operation handling
- **CrawlSession**: Individual crawling session state
- **Domain locking**: Prevents concurrent crawls of same domain

## Key Technical Decisions

### Memory Efficiency
- URL-only vector storage instead of full image storage
- In-memory HTML processing without disk I/O
- Lazy image loading from original sources

### Real-time Communication
- Server-Sent Events (SSE) for live updates
- Polling fallback for environments that dont support SSE
- Configurable timeout and connection management

### Scalability Considerations
- Concurrent crawl limits with configurable maximums
- Session isolation with unique namespaces
- Lazy client initialization for external services

## External Dependencies
- **OpenAI API**: Embeddings and language processing
- **Firecrawl API**: Website crawling with JavaScript support
- **Pinecone API**: Vector database storage and search

## Environment Configuration
- **ENABLE_SSE**: Toggle Server-Sent Events support
- **SSE_TIMEOUT_SECONDS**: SSE connection timeout
- **MAX_CONCURRENT_CRAWLS**: Concurrent operation limit
- **FLASK_DEBUG**: Debug mode toggle
- **PORT**: Server port configuration