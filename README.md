# Image Chat - An Intelligent Website Crawler and AI-Powered Image Search System

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
│   ├── crawl.py          # Crawling operations (/crawl)
│   ├── status.py         # Real-time status monitoring (SSE & polling)
│   ├── chat.py           # Natural language image search
│   └── health.py         # Health checks & monitoring


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

### 🔄 Complete System Logic Flow

```
1. 📥 CRAWL REQUEST
   ├── User submits URL + limit
   ├── System creates unique session + namespace
   ├── Validates concurrency limits
   └── Starts background crawling thread

2. 🕷️ WEBSITE CRAWLING (Firecrawl)
   ├── JavaScript rendering enabled
   ├── 3-second wait for lazy loading
   ├── Extracts raw HTML from all pages
   └── Real-time progress updates via SSE

3. 🔄 DIRECT MEMORY PROCESSING
   ├── Fix relative → absolute image URLs
   ├── Extract img, source, picture, video tags
   ├── Build rich context from alt text + surroundings
   └── Create Document objects (no disk I/O)

4. 🧠 EMBEDDING GENERATION
   ├── Document content: "Alt: iPhone camera | Title: Features | Context: ..."
   ├── OpenAI text-embedding-ada-002 → 1536D vectors
   ├── Batch processing (100 docs at a time)
   └── Direct upload to Pinecone namespace

5. 🔍 SEARCH REQUEST
   ├── AI parses user query → extract intent + format filters
   ├── Generate query embedding (same OpenAI model)
   ├── Two-layer search: Semantic + Keyword scoring
   ├── Smart deduplication + format preference
   └── Return ranked results with relevance scores
```

### 🚀 Crawling & Embedding Pipeline

The system uses a **zero-disk-storage** approach for maximum efficiency:

#### Phase 1: Website Crawling

```python
# Firecrawl configuration for optimal results
crawl_result = firecrawl_app.crawl_url(
    url,
    limit=page_limit,
    scrape_options={
        "formats": ["rawHtml"],
        "renderJs": True,           # Execute JavaScript
        "waitFor": 3000,           # Wait for lazy loading
        "includeTags": ["img", "source", "picture", "video"],
        "removeBase64Images": False  # Keep embedded images
    }
)
```

#### Phase 2: Direct HTML Processing

```python
# No temporary files - pure memory processing
for page_data in crawl_result.data:
    # Fix relative paths to absolute URLs
    fixed_html = fix_image_paths(page_data.rawHtml, page_url)

    # Extract all image elements
    soup = BeautifulSoup(fixed_html, 'html.parser')
    images = soup.find_all(['img', 'source'])

    # Build rich document content
    for img in images:
        context = extract_context(img)  # Alt + title + surrounding text
        doc = Document(
            page_content=f"Alt: {alt} | Title: {title} | Context: {context}",
            metadata={
                'img_url': absolute_url,
                'img_format': detect_format(url),
                'alt_text': alt_text,
                'source_url': page_url,
                'session_id': session_id
            }
        )
```

#### Phase 3: Embedding & Vector Storage

```python
# Batch embedding generation for efficiency
for batch in chunks(all_documents, batch_size=100):
    # OpenAI automatically generates embeddings for page_content
    vector_store.add_documents(
        batch,
        namespace=f"session_{session_id[:8]}"
    )

    # Each document becomes:
    # - 1536-dimensional vector (from page_content)
    # - Metadata stored alongside (URLs, format, alt text)
    # - Isolated in session-specific namespace
```

### 🎯 Two-Layer Search System

The search combines **semantic understanding** with **keyword precision**:

#### Layer 1: Semantic Vector Search

```python
# Query embedding generation
user_query = "iPhone 15 Pro camera features"
query_vector = openai_embeddings.embed_query(user_query)

# Pinecone similarity search
similar_docs = pinecone_index.query(
    vector=query_vector,
    top_k=50,
    namespace=f"session_{session_id}",
    include_metadata=True
)

# Returns documents with cosine similarity scores
# Finds semantically related content even with different wording
```

#### Layer 2: Keyword Relevance Boosting

```python
def calculate_keyword_boost(doc, query):
    alt_text = doc.metadata['alt_text'].lower()
    title_text = doc.metadata['title'].lower()
    query_lower = query.lower()

    boost_score = 0

    # Exact phrase matching (highest priority)
    if query_lower in alt_text:
        boost_score += 2.0
    if query_lower in title_text:
        boost_score += 1.0

    # Individual word matching
    for word in query.split():
        if len(word) > 2:  # Skip short words
            if word in alt_text:
                boost_score += 0.5
            if word in title_text:
                boost_score += 0.3

    return boost_score

# Final ranking combines both layers
final_score = semantic_similarity + keyword_boost_score
```

#### Smart Result Ranking

```python
# Multi-factor ranking algorithm
results.sort(key=lambda x: (
    -x['keyword_boost_score'],     # Exact matches first
    x['format'] not in ['jpg', 'png'],  # Prefer common formats
    x['format'] != 'jpg',          # JPG preferred over PNG
    -x['semantic_score']           # Then semantic similarity
))

# Deduplication using normalized alt text
# Format preference: JPG > PNG > WebP > SVG
# Quality scoring based on context richness
```

### 🧠 Intelligent Image Processing

#### Multi-Source Extraction

```python
# Comprehensive image discovery
img_sources = [
    soup.find_all('img'),                    # Standard images
    soup.find_all('source'),                 # Responsive images
    soup.find_all('picture'),                # Modern picture elements
    soup.find_all('video', poster=True)      # Video poster frames
]

# Advanced attribute processing
for img in images:
    urls = extract_urls_from([
        img.get('src'),
        img.get('data-src'),                 # Lazy loading
        img.get('data-lazy-src'),            # Alternative lazy loading
        img.get('srcset'),                   # Responsive sets
        img.get('data-srcset')               # Deferred responsive sets
    ])
```

#### Context-Aware Document Creation

```python
def build_rich_context(img_element):
    context_parts = []

    # Direct attributes
    if img_element.get('alt'):
        context_parts.append(f"Alt: {img_element['alt'][:500]}")
    if img_element.get('title'):
        context_parts.append(f"Title: {img_element['title'][:200]}")

    # CSS classes (design intent)
    classes = ' '.join(img_element.get('class', []))
    if classes:
        context_parts.append(f"Class: {classes[:300]}")

    # Surrounding content (page context)
    parent = img_element.parent
    if parent:
        parent_text = parent.get_text(strip=True)[:150]
        context_parts.append(f"Context: {parent_text}")

    return " | ".join(context_parts)

# Result: Rich semantic content for embedding
# "Alt: iPhone 15 Pro camera system | Title: Camera Features | Class: hero-image product-photo | Context: Advanced photography with 48MP main camera"
```

### 🔒 Session Isolation & Concurrency

#### Namespace Management

```python
# Each user gets isolated vector space
namespace = f"session_{session_id[:8]}"  # e.g., "session_550e8400"

# Benefits:
# - No cross-contamination between users
# - Parallel crawls of same domain allowed
# - Easy cleanup when session ends
# - Scalable multi-tenant architecture
```

#### Thread-Safe Operations

```python
class SessionManager:
    def __init__(self):
        self.crawl_sessions = {}
        self.session_namespaces = {}
        self.crawl_lock = threading.Lock()

    def create_session(self, session_id, url, limit):
        with self.crawl_lock:
            # Concurrency controls
            active_count = len([s for s in self.crawl_sessions.values()
                              if s.status in ["crawling", "processing"]])

            if active_count >= MAX_CONCURRENT_CRAWLS:
                return None, "Server capacity reached"

            # Session isolation
            session = CrawlSession(session_id, url, limit)
            self.crawl_sessions[session_id] = session
            return session, None
```

### 📊 Performance Optimizations

#### Batch Processing Strategy

```python
def index_documents_in_batches(documents, namespace):
    batch_size = 100  # Optimal for Pinecone

    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]

        try:
            # Efficient bulk upload
            vector_store.add_documents(batch, namespace=namespace)

            # Progress tracking
            progress = ((i + len(batch)) / len(documents)) * 100
            session.add_message("progress", {
                "message": f"Indexing: {progress:.1f}%",
                "progress_percent": progress
            })
        except Exception as e:
            # Continue on batch failure
            log_error(f"Batch {i//batch_size + 1} failed: {e}")
            continue
```

#### Memory-Efficient Pipeline

```python
# No intermediate file storage
crawl_result = firecrawl.crawl_url(url)          # → Memory
fixed_html = fix_image_paths(html_content)       # → Memory
documents = process_html_content(fixed_html)     # → Memory
vector_store.add_documents(documents)            # → Pinecone

# Benefits:
# - Faster processing (no disk I/O)
# - Lower storage costs
# - Better scalability
# - Reduced complexity
```

### 🎛️ Production-Ready Architecture

#### Error Recovery & Resilience

```python
try:
    # Phase 1: Crawling
    crawl_result = firecrawl_app.crawl_url(url, limit=limit)

    # Phase 2: Processing
    all_docs = processor.process_crawl_results_directly(crawl_result)

    # Phase 3: Indexing
    crawler._index_documents_in_batches(all_docs, namespace, session)

except Exception as e:
    session.status = "error"
    session.error = str(e)
    session.add_message("error", {
        "status": "error",
        "message": f"Crawling failed: {str(e)}"
    })
finally:
    # Always clean up resources
    cleanup_session_resources(session_id)
```

#### Real-Time Monitoring

```python
# Server-Sent Events with fallback
@app.route('/crawl/<session_id>/status')
def stream_status(session_id):
    def generate():
        session = session_manager.get_session(session_id)
        timeout = time.time() + SSE_TIMEOUT_SECONDS

        while time.time() < timeout:
            if not session.messages.empty():
                message = session.messages.get()
                yield f"data: {json.dumps(message)}\n\n"

                if message['type'] in ['completed', 'error']:
                    break
            else:
                # Heartbeat to keep connection alive
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                time.sleep(2)

    return Response(generate(), mimetype='text/plain')

# Polling fallback for platforms without SSE support
@app.route('/crawl/<session_id>/status-simple')
def poll_status(session_id):
    session = session_manager.get_session(session_id)
    return jsonify({
        "session_id": session_id,
        "status": session.status,
        "completed": session.completed,
        "total_images": session.total_images,
        "messages": list(session.messages.queue)
    })
```

## 🧭 Code Walkthrough

### 📁 **Quick Navigation Guide**

For developers wanting to understand or modify the system, here's a practical walkthrough of the key files:

#### **🚀 Starting Point**

```bash
server.py                 # Main entry point - Flask app initialization
├── from app import create_app()    # Uses app factory pattern
└── Runs on configurable port      # Default: 5001
```

#### **🏗️ Core Architecture Files**

```bash
app/__init__.py           # App factory + blueprint registration
├── create_app()         # Main factory function
├── register_blueprints() # API route organization
└── CORS + error handling # Production-ready setup

app/config.py            # Single source of truth for configuration
├── Config class         # Environment variables + validation
└── ClientManager class  # Lazy-loaded external service clients
```

#### **📊 Data Layer**

```bash
app/models/session.py    # Session management and state tracking
├── CrawlSession        # Individual crawl state + progress
├── SessionManager      # Thread-safe session operations
└── Concurrency control # Rate limiting + cleanup
```

#### **⚙️ Business Logic**

```bash
app/services/crawler.py  # Orchestrates the complete crawl workflow
├── start_crawl()       # Entry point for background crawling
├── _perform_crawl()    # Main workflow: crawl → process → index
└── _index_documents_in_batches() # Efficient Pinecone uploads

app/services/processor.py # HTML processing and document creation
├── process_crawl_results_directly() # No-disk-storage processing
├── process_html_content() # Soup parsing + context extraction
└── _process_img_tags()   # Multi-source image discovery

app/services/search.py   # AI-powered search with deduplication
├── search_images_with_dedup() # Main search entry point
├── parse_user_query_with_ai() # Natural language understanding
└── _deduplicate_results()     # Smart duplicate removal
```

#### **🌐 API Layer**

```bash
app/api/crawl.py        # Crawling operations
└── POST /crawl         # Start new crawl session

app/api/status.py       # Real-time progress monitoring
├── GET /crawl/{id}/status        # Server-Sent Events stream
└── GET /crawl/{id}/status-simple # Polling fallback

app/api/chat.py         # Natural language image search
└── POST /chat          # AI-powered search endpoint
```

#### **🔧 Utilities**

```bash
app/services/processor.py # HTML processing & document creation
├── fix_image_paths()     # Relative → absolute URL conversion
├── get_image_format()    # Format detection from URLs
├── extract_context()     # Rich context building for embeddings
└── HTMLProcessor class   # Complete HTML processing pipeline
```

### 🔍 **Key Code Patterns**

#### **1. Adding a New API Endpoint**

```python
# Create new blueprint file: app/api/my_feature.py
from flask import Blueprint, request, jsonify
from app.config import clients

my_feature_bp = Blueprint('my_feature', __name__)

@my_feature_bp.route('/my-endpoint', methods=['POST'])
def my_endpoint():
    # Business logic here
    return jsonify({"status": "success"})

# Register in app/__init__.py
from app.api.my_feature import my_feature_bp
app.register_blueprint(my_feature_bp)
```

#### **2. Extending Search Functionality**

```python
# Modify app/services/search.py
class SearchService:
    def new_search_method(self, query, filters):
        # Use existing patterns
        retriever = clients.vector_store.as_retriever(
            search_kwargs={"k": 50, "namespace": namespace}
        )
        results = retriever.invoke(query)
        # Add your custom logic
        return processed_results
```

#### **3. Adding New Image Processing**

```python
# Extend app/services/processor.py
def _process_new_element_type(self, elements, base_url, source_url):
    docs = []
    for element in elements:
        # Extract URLs
        urls = self._extract_urls(element)

        # Build context
        context = extract_context(element)

        # Create document
        doc = Document(
            page_content=f"Context: {context}",
            metadata={
                'img_url': url,
                'source_url': source_url,
                # Add your metadata
            }
        )
        docs.append(doc)
    return docs
```

### 📚 **Understanding the Data Flow**

#### **Request → Response Journey**

```python
# 1. User starts crawl
POST /crawl {"url": "example.com", "limit": 10}

# 2. Session creation (app/api/crawl.py)
session_manager.create_session(session_id, url, limit)

# 3. Background processing (app/services/crawler.py)
crawler.start_crawl(session)
└── _perform_crawl(session)
    ├── firecrawl_app.crawl_url()      # External API
    ├── processor.process_crawl_results_directly()
    └── _index_documents_in_batches()  # Pinecone upload

# 4. Real-time updates (app/api/status.py)
GET /crawl/{id}/status  # SSE stream of progress

# 5. Search functionality (app/api/chat.py)
POST /chat → search_service.search_images_with_dedup()
```

#### **Configuration Management**

```python
# Environment variables → app/config.py
OPENAI_API_KEY → clients.openai_client
PINECONE_API_KEY → clients.vector_store
FIRECRAWL_API_KEY → clients.firecrawl_app

# Lazy loading pattern
class ClientManager:
    @property
    def openai_client(self):
        if not self._openai_client:
            self._openai_client = OpenAI(api_key=self.config.OPENAI_API_KEY)
        return self._openai_client
```

### 🛠️ **Development Workflow**

#### **1. Local Development Setup**

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env  # Add your API keys

# Run in debug mode
FLASK_DEBUG=true python server.py
```

#### **2. Testing New Features**

```python
# Test individual components
from app.services.processor import HTMLProcessor
processor = HTMLProcessor()
docs = processor.process_html_content(html_string, base_url)

# Test API endpoints
curl -X POST http://localhost:5001/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "limit": 5}'
```

#### **3. Common Customizations**

- **Add new image sources**: Extend `_process_img_tags()` in `processor.py`
- **Modify search ranking**: Update sorting logic in `search.py`
- **Add new API endpoints**: Create new blueprint in `app/api/`
- **Change embedding model**: Update `ClientManager` in `config.py`

### 🔧 **Extension Points**

The modular architecture makes these extensions straightforward:

1. **New Crawl Sources**: Add clients to `ClientManager`
2. **Additional Image Formats**: Extend `get_image_format()`
3. **Custom Search Filters**: Modify `search_images_with_dedup()`
4. **Alternative Storage**: Replace `vector_store` in `ClientManager`
5. **New API Versions**: Add versioned blueprints

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
