# Image Chat API Documentation

## Overview

The Intelligent Image Search API provides a comprehensive set of endpoints for crawling websites and searching for images using AI-powered natural language queries. Built with a modular, production-ready architecture, it offers real-time status updates, semantic search capabilities, and intelligent resource management.

### Key Features

- **Memory-Efficient Processing**: Direct HTML processing without disk I/O
- **AI-Powered Search**: Natural language understanding with OpenAI embeddings
- **Real-Time Updates**: Server-Sent Events with polling fallback
- **Session Isolation**: Each crawl gets its own vector database namespace
- **Smart Deduplication**: Advanced duplicate detection using semantic analysis
- **Production-Ready**: Comprehensive error handling and resource management

## Base URL

```
http://localhost:5001
```

## Architecture Overview

The API follows a modular blueprint-based architecture:

```
app/
├── api/                  # Flask blueprints for API endpoints
│   ├── crawl.py         # Crawling operations & session management
│   ├── status.py        # Real-time status monitoring (SSE & polling)
│   ├── chat.py          # Natural language image search
│   └── health.py        # Health checks & monitoring
├── services/            # Business logic layer
│   ├── crawler.py       # Website crawling orchestration
│   ├── processor.py     # HTML parsing & image extraction
│   └── search.py        # AI-powered search & deduplication
├── models/              # Data models
│   └── session.py       # Session management & concurrency controls
└── config.py            # Configuration & lazy-loaded clients
```

## Authentication

Currently, no authentication is required. The API uses internal API keys for external services (OpenAI, Firecrawl, Pinecone) configured via environment variables.

## Core Endpoints

### 1. Start Website Crawl

**POST** `/crawl`

Initiates an intelligent crawling operation that processes content directly in memory and indexes images for semantic search.

#### Request Body

```json
{
  "url": "https://www.apple.com/iphone",
  "limit": 15
}
```

| Field | Type    | Required | Description                                    |
| ----- | ------- | -------- | ---------------------------------------------- |
| url   | string  | Yes      | The URL to start crawling from                 |
| limit | integer | No       | Maximum number of pages to crawl (default: 10) |

#### Response

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Crawling started",
  "subscribe_url": "/crawl/550e8400-e29b-41d4-a716-446655440000/status",
  "status_url_sse": "/crawl/550e8400-e29b-41d4-a716-446655440000/status",
  "status_url_polling": "/crawl/550e8400-e29b-41d4-a716-446655440000/status-simple"
}
```

#### Error Responses

- `400 Bad Request`: Missing or invalid URL format
- `429 Too Many Requests`: Maximum concurrent crawls reached (server-wide limit)

#### Example

```bash
curl -X POST http://localhost:5001/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.apple.com/iphone",
    "limit": 15
  }'
```

### 2. Real-Time Crawl Status (SSE)

**GET** `/crawl/<session_id>/status`

Subscribe to real-time crawling status updates using Server-Sent Events. Provides live progress monitoring with automatic timeout and graceful connection handling.

#### Event Types

1. **connected** - Initial connection confirmation

   ```json
   {
     "type": "connected",
     "session_id": "550e8400-e29b-41d4-a716-446655440000"
   }
   ```

2. **status** - Phase transitions (crawling → processing → indexing)

   ```json
   {
     "type": "status",
     "data": {
       "status": "processing",
       "message": "Extracting images directly from crawled content"
     }
   }
   ```

3. **progress** - Detailed progress with statistics

   ```json
   {
     "type": "progress",
     "data": {
       "message": "Processed 156 images from 10 pages (no disk storage needed)",
       "stats": {
         "formats": { "jpg": 89, "png": 45, "svg": 22 },
         "pages": { "https://www.apple.com/iphone": 45 }
       },
       "progress_percent": 75.5
     }
   }
   ```

4. **completed** - Success with comprehensive summary

   ```json
   {
     "type": "completed",
     "data": {
       "status": "completed",
       "summary": "I've successfully crawled https://www.apple.com/iphone and found 156 images across 10 pages...",
       "total_images": 156,
       "total_pages": 10,
       "stats": {
         "formats": { "jpg": 89, "png": 45, "svg": 22 }
       }
     }
   }
   ```

5. **error** - Error details with recovery information

   ```json
   {
     "type": "error",
     "data": {
       "status": "error",
       "message": "Crawling failed: Connection timeout"
     }
   }
   ```

6. **heartbeat** - Keep-alive signals during long operations
   ```json
   {
     "type": "heartbeat",
     "time": 45
   }
   ```

#### JavaScript Client Example

```javascript
const eventSource = new EventSource(`/crawl/${sessionId}/status`);

eventSource.onmessage = function (event) {
  const data = JSON.parse(event.data);
  console.log("Status update:", data);

  switch (data.type) {
    case "progress":
      updateProgressBar(data.data.progress_percent);
      break;
    case "completed":
      showResults(data.data);
      eventSource.close();
      break;
    case "error":
      showError(data.data.message);
      eventSource.close();
      break;
  }
};

eventSource.onerror = function (event) {
  console.log("SSE connection error, falling back to polling");
  eventSource.close();
  startPolling(sessionId);
};
```

### 3. Polling-Based Status (Alternative to SSE)

**GET** `/crawl/<session_id>/status-simple`

Simple JSON-based status endpoint for environments where SSE doesn't work reliably (e.g., Replit, Heroku).

#### Response

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "completed": false,
  "error": null,
  "total_images": 89,
  "total_pages": 7,
  "messages": [
    {
      "type": "progress",
      "data": {
        "message": "Indexing progress: 45.2% (67/156 documents)"
      },
      "timestamp": "2024-01-15T10:35:22.123Z"
    }
  ],
  "image_stats": {
    "formats": { "jpg": 45, "png": 30, "svg": 14 }
  }
}
```

#### Polling Example

```javascript
async function pollStatus(sessionId) {
  while (true) {
    const response = await fetch(`/crawl/${sessionId}/status-simple`);
    const data = await response.json();

    updateUI(data);

    if (data.completed || data.error) {
      break;
    }

    await new Promise((resolve) => setTimeout(resolve, 2000)); // Poll every 2 seconds
  }
}
```

### 4. Natural Language Image Search

**POST** `/chat`

Search for images using AI-powered natural language understanding. The system parses intent, format preferences, and context to provide highly relevant results.

#### Request Body

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "chat_history": [
    {
      "role": "human",
      "content": "Show me high-quality iPhone camera images in JPG format"
    }
  ]
}
```

| Field        | Type   | Required | Description                                  |
| ------------ | ------ | -------- | -------------------------------------------- |
| session_id   | string | Yes      | The crawl session ID to search within        |
| chat_history | array  | Yes      | Array of chat messages with role and content |

#### Response

```json
{
  "response": "I'll help you find high-quality iPhone camera images in JPG format\n\nI found 5 relevant images:",
  "search_results": [
    {
      "url": "https://www.apple.com/images/iphone-15-pro-camera-system.jpg",
      "format": "jpg",
      "alt_text": "iPhone 15 Pro Advanced Camera System with 48MP Main Camera",
      "source_url": "https://www.apple.com/iphone/",
      "score": 0.8234
    }
  ],
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Advanced Search Examples

```bash
# Format-specific search
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "chat_history": [
      {"role": "human", "content": "Find PNG images of Apple Watch"}
    ]
  }'

# Contextual search
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "chat_history": [
      {"role": "human", "content": "Show me hero banner images from the homepage"}
    ]
  }'

# Quality-focused search
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "chat_history": [
      {"role": "human", "content": "High-resolution product photos suitable for print"}
    ]
  }'
```

#### Error Responses

- `400 Bad Request`: Missing session_id or invalid chat history
- `404 Not Found`: Session not found or vector database missing
- `400 Bad Request`: Crawling not yet completed

### 5. Session Management

#### List All Sessions

**GET** `/sessions`

Get a comprehensive list of all crawl sessions with status and statistics.

```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "url": "https://www.apple.com/iphone",
      "status": "completed",
      "total_images": 156,
      "total_pages": 10,
      "completed": true,
      "created_at": "2024-01-15T10:30:00.000Z"
    }
  ]
}
```

#### Delete Specific Session

**DELETE** `/sessions/<session_id>`

Delete a session and free all associated resources including vector database and domain tracking.

```json
{
  "message": "Session 550e8400-e29b-41d4-a716-446655440000 deleted successfully"
}
```

#### Cleanup Old Sessions

**POST** `/cleanup`

Automatically clean up old completed sessions to free memory and resources.

**Request Body:**

```json
{
  "hours_old": 24
}
```

**Response:**

```json
{
  "message": "Cleaned up 3 old sessions",
  "deleted_sessions": ["id1", "id2", "id3"],
  "remaining_sessions": 2
}
```

### 6. Health Check & Monitoring

**GET** `/health`

Check server health and get system status information.

```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

## Intelligent Design Features

### Memory-Efficient Processing

- **URL-Only Storage**: Vector database stores only URLs and metadata, not binary image data
- **Direct Processing**: HTML content processed in memory without disk I/O
- **Lazy Loading**: Images loaded on-demand from original sources

### AI-Powered Search Intelligence

```python
# Example search queries the AI understands:
"Show me iPad Pro images"                    # → Product-specific search
"I need high-resolution iPhone photos"       # → Quality-focused search
"Find PNG images of Apple Watch"             # → Format-filtered search
"Camera feature screenshots in dark mode"    # → Contextual search
"Product photos without people"              # → Advanced content filtering
```

### Smart Deduplication

- **Filename Analysis**: Identifies similar images with different resolutions
- **Semantic Similarity**: Uses alt text and context for duplicate detection
- **Format Prioritization**: Prefers JPG/PNG over other formats
- **Context Awareness**: Considers surrounding HTML content

### Production-Ready Architecture

- **Session Isolation**: Each crawl gets its own vector database namespace
- **Concurrency Controls**: Domain locking prevents duplicate crawls
- **Resource Management**: Automatic cleanup of old sessions
- **Error Recovery**: Graceful handling of failed pages or network issues

## Rate Limits & Concurrency

| Resource          | Limit            | Description                              |
| ----------------- | ---------------- | ---------------------------------------- |
| Concurrent Crawls | 3 (configurable) | Maximum simultaneous crawl operations    |
| Domain Locking    | 1 per domain     | Prevents duplicate crawls of same domain |
| Session Isolation | Unlimited        | Each session gets isolated vector space  |
| SSE Timeout       | 300 seconds      | Auto-disconnect for idle SSE connections |

## Error Handling

### HTTP Status Codes

| Code | Meaning             | Description                                |
| ---- | ------------------- | ------------------------------------------ |
| 200  | Success             | Request completed successfully             |
| 400  | Bad Request         | Invalid parameters or malformed request    |
| 404  | Not Found           | Session or resource not found              |
| 429  | Too Many Requests   | Server-wide concurrent crawl limit reached |
| 503  | Service Unavailable | SSE disabled, use polling endpoint         |

### Error Response Format

```json
{
  "error": "Maximum 3 concurrent crawls allowed. Please try again later."
}
```

## Configuration Options

Configure via environment variables:

```env
# Server Configuration
PORT=5001                         # Server port
ENABLE_SSE=true                   # Enable/disable Server-Sent Events
SSE_TIMEOUT_SECONDS=300          # SSE connection timeout

# Performance Tuning
MAX_CONCURRENT_CRAWLS=3          # Maximum simultaneous crawls
FIRECRAWL_WAIT_TIME=3000         # Wait time for JavaScript rendering

# API Keys (Required)
OPENAI_API_KEY=your_key_here
FIRECRAWL_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here
```

## Complete Usage Example

### 1. Start Crawling

```bash
curl -X POST http://localhost:5001/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.apple.com/iphone", "limit": 15}'
```

### 2. Monitor Progress (Choose SSE or Polling)

**Option A: Server-Sent Events**

```javascript
const eventSource = new EventSource(`/crawl/${sessionId}/status`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Progress:", data);
};
```

**Option B: Polling (Replit/Heroku Compatible)**

```javascript
async function checkStatus() {
  const response = await fetch(`/crawl/${sessionId}/status-simple`);
  const data = await response.json();
  return data;
}
```

### 3. Search Images with Natural Language

```bash
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "chat_history": [
      {"role": "human", "content": "Show me iPhone camera features in high quality"}
    ]
  }'
```

### 4. Advanced Search Examples

```bash
# Find specific image types
curl -X POST http://localhost:5001/chat \
  -d '{"session_id": "id", "chat_history": [{"role": "human", "content": "Hero banner images suitable for homepage"}]}'

# Format-specific search
curl -X POST http://localhost:5001/chat \
  -d '{"session_id": "id", "chat_history": [{"role": "human", "content": "High-res PNG logos with transparent background"}]}'

# Contextual search
curl -X POST http://localhost:5001/chat \
  -d '{"session_id": "id", "chat_history": [{"role": "human", "content": "Product photography without lifestyle context"}]}'
```

### 5. Clean Up Resources

```bash
# Delete specific session
curl -X DELETE http://localhost:5001/sessions/your-session-id

# Cleanup old sessions
curl -X POST http://localhost:5001/cleanup \
  -H "Content-Type: application/json" \
  -d '{"hours_old": 6}'
```

## Integration Examples

### React/Next.js Integration

```javascript
import { useState, useEffect } from "react";

function ImageCrawler() {
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("idle");
  const [results, setResults] = useState([]);

  const startCrawl = async (url) => {
    const response = await fetch("/crawl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, limit: 10 }),
    });
    const data = await response.json();
    setSession(data.session_id);

    // Start monitoring
    monitorProgress(data.session_id);
  };

  const monitorProgress = (sessionId) => {
    const eventSource = new EventSource(`/crawl/${sessionId}/status`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data.type);

      if (data.type === "completed") {
        setStatus("ready");
        eventSource.close();
      }
    };
  };

  const searchImages = async (query) => {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session,
        chat_history: [{ role: "human", content: query }],
      }),
    });
    const data = await response.json();
    setResults(data.search_results);
  };

  return <div>{/* Your UI components */}</div>;
}
```

### Dynamic Website Generation

```python
# Example: Building personalized product pages
from app.services.search import SearchService

search_service = SearchService()

# Get hero images for homepage
hero_images = search_service.search_images_with_dedup(
    "large banner hero images homepage",
    namespace=f"session_{session_id}",
    format_filter=["jpg", "png"],
    max_results=3
)

# Get product grid images
product_images = search_service.search_images_with_dedup(
    "product photography clean background",
    namespace=f"session_{session_id}",
    max_results=20
)

# Build responsive image sets
for img in hero_images:
    responsive_variants = search_service.search_images_with_dedup(
        f"similar to {img['alt_text']} different sizes",
        namespace=f"session_{session_id}",
        max_results=5
    )
```

---

**API Version:** 2.0.0  
**Last Updated:** January 2024  
**Built with Flask, OpenAI, Pinecone, and Firecrawl**
