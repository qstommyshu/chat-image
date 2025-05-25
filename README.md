# Intelligent Website Crawler and AI-Powered Image Search System

A production-ready, modular system that intelligently crawls websites, extracts images, and provides powerful natural language search capabilities. Built with performance, scalability, and real-world applications in mind.

## ✨ Key Features

- 🕷️ **Smart Website Crawling**: Automatically crawls multiple pages with JavaScript rendering support
- 🖼️ **Comprehensive Image Extraction**: Extracts images from all HTML elements (img, source, picture, video tags)
- 🔍 **AI-Powered Search**: Natural language search interface powered by OpenAI embeddings
- 🧹 **Intelligent Deduplication**: Advanced duplicate detection using semantic similarity and metadata
- 💬 **Multiple Interfaces**: CLI, Web UI, and REST API for maximum flexibility
- 📊 **Vector Search**: Semantic search using embeddings for contextual image discovery
- 🔄 **Real-time Updates**: Server-Sent Events with polling fallback for live progress monitoring
- 🔒 **Concurrency Controls**: Domain locking and session isolation for safe parallel operations

## 🎯 Intelligent Design Choices

### Memory-Efficient Architecture

- **URL-Only Vector Storage**: Only image URLs and metadata are stored in the vector database, keeping it lightweight and fast
- **Lazy Image Loading**: Images are loaded on-demand from their original sources, reducing storage costs
- **Direct Processing Pipeline**: HTML content is processed in memory without disk I/O, eliminating bottlenecks

### Production-Ready Modularity

- **Service Layer Pattern**: Clean separation between business logic and API endpoints
- **Blueprint Architecture**: Organized API routes for maintainability and testing
- **Lazy Client Initialization**: External services (OpenAI, Pinecone, Firecrawl) are initialized only when needed
- **Thread-Safe Session Management**: Concurrent crawl operations with proper resource isolation

### Smart Crawling Strategy

- **JavaScript Rendering**: Waits for dynamic content to load, capturing lazy-loaded images
- **Context-Aware Extraction**: Captures alt text, titles, and surrounding content for better search relevance
- **Format-Aware Processing**: Prioritizes high-quality formats (JPG, PNG) while supporting all web formats

## 🚀 Advanced Use Cases

### Dynamic Website Construction

```python
# Example: Building a personalized product catalog
search_results = search_service.search_images_with_dedup(
    "modern minimalist furniture living room",
    namespace="furniture_site",
    format_filter=["jpg", "png"],
    max_results=20
)

# Use results to dynamically populate website sections
hero_images = [img for img in search_results if "hero" in img['context']]
product_grid = [img for img in search_results if img['alt_match_score'] > 1.0]
```

### Competitive Analysis & Research

- **Multi-Domain Crawling**: Compare image strategies across competitor websites
- **Trend Analysis**: Identify popular visual themes and design patterns
- **Content Auditing**: Find missing alt text, outdated images, or format inconsistencies

### Content Management & SEO

- **Image Inventory**: Catalog all images across large websites
- **Alt Text Optimization**: Identify images lacking proper accessibility descriptions
- **Format Optimization**: Find opportunities to convert to modern formats (WebP, AVIF)

## 🏗️ Project Architecture

```
app/
├── __init__.py           # Flask application factory with blueprint registration
├── config.py             # Centralized configuration with lazy-loaded clients
├── models/               # Data models and session management
│   ├── __init__.py
│   └── session.py        # CrawlSession class & thread-safe SessionManager
├── services/             # Business logic layer
│   ├── __init__.py
│   ├── crawler.py        # Website crawling orchestration
│   ├── processor.py      # HTML parsing & image extraction
│   └── search.py         # AI-powered search & deduplication
├── api/                  # RESTful API endpoints
│   ├── __init__.py
│   ├── crawl.py          # Crawling operations (/crawl, /sessions, /cleanup)
│   ├── status.py         # Real-time status monitoring (SSE & polling)
│   ├── chat.py           # Natural language image search
│   └── health.py         # Health checks & monitoring
└── utils/                # Shared utilities
    ├── __init__.py
    └── html_utils.py     # URL processing, format detection, context extraction

server.py                 # Application entry point
requirements.txt          # Python dependencies
.env                      # Environment configuration (create this)
```

## 📋 Prerequisites

1. **Python 3.8+**
2. **API Keys**:
   - OpenAI API key (for embeddings and natural language processing)
   - Firecrawl API key (for website crawling with JavaScript support)
   - Pinecone API key (for vector database storage)

## ⚡ Quick Start

### 1. Installation

```bash
# Clone and install dependencies
git clone <repository-url>
cd website-crawler
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file with your API keys:

```env
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here

# Optional Configuration
ENABLE_SSE=true                    # Enable Server-Sent Events (disable for Replit/Heroku)
SSE_TIMEOUT_SECONDS=300           # SSE connection timeout
MAX_CONCURRENT_CRAWLS=3           # Maximum simultaneous crawl operations
FLASK_DEBUG=false                 # Debug mode (set to false for production)
PORT=5001                         # Server port
```

### 3. Launch Options

#### Option A: Flask Server (Recommended)

```bash
python server.py
```

Then open `client_example.html` in your browser or use the REST API.

#### Option B: Command Line Interface

```bash
python app.py https://www.apple.com/iphone 20
```

## 🔌 API Documentation

### Core Endpoints

| Endpoint                    | Method | Description             | Response                 |
| --------------------------- | ------ | ----------------------- | ------------------------ |
| `/crawl`                    | POST   | Start website crawling  | Session ID + status URLs |
| `/crawl/{id}/status`        | GET    | Real-time SSE updates   | Event stream             |
| `/crawl/{id}/status-simple` | GET    | Polling-based status    | JSON status              |
| `/chat`                     | POST   | Natural language search | Search results           |
| `/sessions`                 | GET    | List all sessions       | Session summaries        |
| `/sessions/{id}`            | DELETE | Delete session          | Confirmation             |
| `/cleanup`                  | POST   | Remove old sessions     | Cleanup stats            |
| `/health`                   | GET    | Health check            | Service status           |

### Example Usage

#### 1. Start Crawling

```bash
curl -X POST http://localhost:5001/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.apple.com/iphone",
    "limit": 15
  }'
```

#### 2. Monitor Progress (SSE)

```javascript
const eventSource = new EventSource(`/crawl/${sessionId}/status`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Progress:", data);
};
```

#### 3. Search Images

```bash
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "chat_history": [
      {
        "role": "human",
        "content": "Show me high-quality iPhone camera images in JPG format"
      }
    ]
  }'
```

## 🎨 Search Examples

The AI understands natural language and can extract intent, format preferences, and context:

```
"Show me iPad Pro images"                    → Searches for iPad Pro
"I need high-resolution iPhone photos"       → Prioritizes image quality
"Find PNG images of Apple Watch"             → Filters by PNG format
"Camera feature screenshots in dark mode"    → Contextual search
"Product photos without people"               → Advanced filtering
```

## 🔧 Advanced Configuration

### Performance Tuning

```env
# Crawler settings
MAX_CONCURRENT_CRAWLS=5           # Increase for powerful servers
FIRECRAWL_WAIT_TIME=5000         # Wait longer for slow sites

# Vector database settings
PINECONE_BATCH_SIZE=200          # Larger batches for faster indexing
PINECONE_DIMENSION=1536          # OpenAI embedding dimension

# Memory management
SESSION_CLEANUP_HOURS=6          # Automatic session cleanup interval
```

### Deployment Options

- **Development**: `FLASK_DEBUG=true` for hot reloading
- **Production**: `ENABLE_SSE=false` for platforms that don't support SSE
- **High Traffic**: Increase `MAX_CONCURRENT_CRAWLS` based on server capacity

## 🌟 Unique Capabilities

### 1. Contextual Understanding

The system doesn't just find images—it understands context:

```python
# Finds images specifically used as hero banners
"large banner images on homepage"

# Identifies product vs. lifestyle photography
"product shots without lifestyle context"

# Understands technical requirements
"high-resolution images suitable for print"
```

### 2. Dynamic Website Generation

Use crawled data to build personalized experiences:

```python
# Auto-generate gallery pages
gallery_images = search_by_theme("minimalist design")

# Create contextual image recommendations
related_images = search_by_similarity(current_image_context)

# Build responsive image sets
responsive_set = find_image_variants(base_image_url)
```

### 3. Content Strategy Insights

- **Visual Trend Analysis**: Identify popular design patterns
- **Competitor Benchmarking**: Compare image strategies
- **SEO Optimization**: Find images lacking proper alt text
- **Performance Auditing**: Identify oversized or poorly formatted images

## 🔍 Under the Hood

### Intelligent Image Processing

- **Multi-Source Extraction**: Processes `<img>`, `<source>`, `<picture>`, and even `<video>` poster frames
- **Context Aggregation**: Combines alt text, titles, captions, and surrounding content
- **Smart Deduplication**: Uses filename similarity and semantic analysis to remove duplicates
- **Format Intelligence**: Automatically detects and prioritizes modern web formats

### Scalable Vector Search

- **Semantic Embeddings**: Uses OpenAI's text-embedding-ada-002 for deep understanding
- **Namespace Isolation**: Each crawl session gets its own vector space
- **Efficient Storage**: Only URLs and metadata stored, not binary image data
- **Relevance Scoring**: Combines semantic similarity with metadata matching

### Production-Ready Architecture

- **Error Recovery**: Graceful handling of failed pages or network issues
- **Resource Management**: Automatic cleanup of completed sessions
- **Monitoring**: Health checks and detailed logging for production deployment
- **Security**: Input validation and rate limiting built-in

## 🚨 Troubleshooting

### Common Issues

1. **SSE Connection Problems**: Set `ENABLE_SSE=false` for Replit/Heroku deployment
2. **Memory Usage**: Reduce `limit` parameter for large websites
3. **API Rate Limits**: Increase delays between requests for rate-limited sites
4. **No Images Found**: Some sites use lazy loading—increase `FIRECRAWL_WAIT_TIME`

### Performance Optimization

- **Batch Processing**: System automatically batches vector operations for efficiency
- **Memory Management**: Direct processing eliminates temporary file storage
- **Connection Pooling**: Reuses HTTP connections for better performance
- **Lazy Loading**: External clients initialized only when needed

## 🔮 Future Possibilities

This system's modular architecture enables exciting extensions:

- **🎨 Visual AI**: Integrate computer vision for automatic image tagging
- **📱 Mobile SDK**: Package core functionality for mobile app integration
- **🔄 Real-time Sync**: Monitor websites for new images and auto-update
- **📊 Analytics Dashboard**: Visual insights into crawling and search patterns
- **🌐 Multi-language**: Expand natural language search to multiple languages
- **🎯 Smart Caching**: Intelligent image caching based on access patterns

## 📄 License

This project is built for both personal and commercial use. Please ensure compliance with the terms of service of crawled websites and respect robots.txt files.

---

**Built with ❤️ using Flask, OpenAI, Pinecone, and Firecrawl**
