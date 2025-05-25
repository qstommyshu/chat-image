# Flask Image Search API Documentation

## Overview

The Flask Image Search API provides endpoints for crawling websites and searching for images using natural language queries. It supports real-time status updates via Server-Sent Events (SSE) and maintains session-based vector databases for efficient image searching.

The API has been refactored into a modular architecture with clearly separated responsibilities:

- Route handlers for API endpoints
- Service layer for business logic
- Data models for structured data
- Utility functions for common operations

## Base URL

```
http://127.0.0.1:5000
```

## Endpoints

### 1. Start Website Crawl

**POST** `/crawl`

Initiates a crawling job for the specified website.

#### Request Body

```json
{
  "url": "https://www.apple.com/iphone",
  "limit": 10
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
  "subscribe_url": "/crawl/550e8400-e29b-41d4-a716-446655440000/status"
}
```

#### Error Responses

- `400 Bad Request`: Missing or invalid URL
- `409 Conflict`: Domain already being crawled
- `429 Too Many Requests`: Maximum concurrent crawls reached

### 2. Crawl Status (SSE)

**GET** `/crawl/<session_id>/status`

Subscribe to real-time crawling status updates using Server-Sent Events.

#### Event Types

1. **connected**

   ```json
   {
     "type": "connected",
     "session_id": "550e8400-e29b-41d4-a716-446655440000"
   }
   ```

2. **status**

   ```json
   {
     "type": "status",
     "data": {
       "status": "crawling",
       "message": "Starting to crawl https://www.apple.com/iphone"
     }
   }
   ```

3. **progress**

   ```json
   {
     "type": "progress",
     "data": {
       "message": "Processed 156 images from 10 pages",
       "stats": {
         "formats": {"jpg": 89, "png": 45, "svg": 22},
         "pages": {"https://www.apple.com/iphone": 45, ...}
       }
     }
   }
   ```

4. **completed**

   ```json
   {
     "type": "completed",
     "data": {
       "status": "completed",
       "summary": "I've successfully crawled https://www.apple.com/iphone...",
       "total_images": 156,
       "total_pages": 10,
       "stats": {...}
     }
   }
   ```

5. **error**
   ```json
   {
     "type": "error",
     "data": {
       "status": "error",
       "message": "Crawling failed: Connection timeout"
     }
   }
   ```

#### Example JavaScript Client

```javascript
const eventSource = new EventSource("/crawl/SESSION_ID/status");

eventSource.onmessage = function (event) {
  const data = JSON.parse(event.data);
  console.log("Status update:", data);

  if (data.type === "completed" || data.type === "error") {
    eventSource.close();
  }
};
```

### 3. Chat / Search Images

**POST** `/chat`

Search for images using natural language queries based on the crawled content.

#### Request Body

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "chat_history": [
    {
      "role": "ai",
      "content": "I've crawled https://apple.com/iphone and found 156 images..."
    },
    {
      "role": "human",
      "content": "Show me iPhone camera images"
    }
  ]
}
```

| Field        | Type   | Required | Description                                  |
| ------------ | ------ | -------- | -------------------------------------------- |
| session_id   | string | Yes      | The crawl session ID                         |
| chat_history | array  | Yes      | Array of chat messages with role and content |

#### Response

```json
{
  "response": "I'll help you find iPhone camera images\n\nI found 5 relevant images:",
  "search_results": [
    {
      "url": "https://www.apple.com/images/iphone-camera.jpg",
      "format": "jpg",
      "alt_text": "iPhone 15 Pro Camera System",
      "source_url": "https://www.apple.com/iphone",
      "score": 0.8234
    }
  ],
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Error Responses

- `400 Bad Request`: Missing session_id or invalid chat history
- `404 Not Found`: Session not found or vector database missing
- `400 Bad Request`: Crawling not yet completed

### 4. List Sessions

**GET** `/sessions`

Get a list of all crawl sessions.

#### Response

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

### 5. Delete Session

**DELETE** `/sessions/<session_id>`

Delete a specific session and free its resources.

#### Response

```json
{
  "message": "Session 550e8400-e29b-41d4-a716-446655440000 deleted successfully"
}
```

#### Error Responses

- `404 Not Found`: Session not found

### 6. Clean Up Old Sessions

**POST** `/cleanup`

Clean up old completed sessions to free memory.

#### Request Body

```json
{
  "hours_old": 24
}
```

| Field     | Type    | Required | Description                          |
| --------- | ------- | -------- | ------------------------------------ |
| hours_old | integer | No       | Age threshold in hours (default: 24) |

#### Response

```json
{
  "message": "Cleaned up 3 old sessions",
  "deleted_sessions": ["id1", "id2", "id3"],
  "remaining_sessions": 2
}
```

### 7. Health Check

**GET** `/health`

Check if the server is running.

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "active_sessions": 5,
  "active_crawls": 2
}
```

## Concurrency Controls

The API implements several concurrency controls:

1. **Domain Locking**: Only one crawl per domain is allowed at a time
2. **Maximum Concurrent Crawls**: A limit on the number of simultaneous crawling operations
3. **Session Isolation**: Each session has its own vector database and folder
4. **Resource Cleanup**: Automatic cleanup of old sessions to free resources

## Example Usage Flow

1. **Start a crawl job:**

   ```bash
   curl -X POST http://127.0.0.1:5000/crawl \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.apple.com/iphone", "limit": 10}'
   ```

2. **Subscribe to status updates:**
   Use the `subscribe_url` from the response to connect via SSE and monitor progress.

3. **Search for images:**
   Once crawling is completed, use the chat endpoint with the session_id:

   ```bash
   curl -X POST http://127.0.0.1:5000/chat \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "YOUR_SESSION_ID",
       "chat_history": [
         {"role": "human", "content": "Show me product images"}
       ]
     }'
   ```

4. **Clean up resources:**
   When done, delete the session to free up resources:
   ```bash
   curl -X DELETE http://127.0.0.1:5000/sessions/YOUR_SESSION_ID
   ```

## Project Architecture

The API is built using a modular architecture:

```
app/
├── routes/               # API endpoints
│   ├── admin_routes.py   # Session management
│   ├── crawl_routes.py   # Website crawling
│   └── search_routes.py  # Image search
├── services/             # Business logic
│   ├── crawler.py        # Crawling service
│   └── search.py         # Search service
└── models/               # Data models
    └── session.py        # CrawlSession class
```

## Running the Server

```bash
python server.py
```

The server will start on `http://127.0.0.1:5000` using the configuration from `app/config.py`.
