# Combined Website Crawler and Image Search System

This system crawls any website to extract images and provides multiple interfaces to search for them using natural language.

## Features

- 🕷️ **Website Crawling**: Automatically crawls multiple pages from any website
- 🖼️ **Image Extraction**: Extracts all images from HTML pages (img, source, picture tags)
- 🔍 **AI-Powered Search**: Natural language search interface powered by OpenAI
- 🧹 **Smart Deduplication**: Removes duplicate images based on filenames and alt text
- 💬 **Multiple Interfaces**: CLI, Web UI, and REST API
- 📊 **Vector Search**: Uses embeddings for semantic image search
- 🔄 **Real-time Updates**: Server-Sent Events for crawl progress monitoring
- 🔒 **Concurrency Controls**: Domain locking and session isolation

## Prerequisites

1. Python 3.8+
2. API Keys:
   - OpenAI API key
   - Firecrawl API key

## Installation

1. Install required packages:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your API keys:

```env
OPENAI_API_KEY=your_openai_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
```

## Usage Options

### Option 1: Command Line Interface

Run the app with a URL:

```bash
python app.py https://www.apple.com/iphone
```

Or with a specific number of pages:

```bash
python app.py https://www.apple.com/iphone 20
```

### Option 2: Flask Server (API + Web UI)

Start the Flask server:

```bash
python server.py
```

Then either:

- Open `client_example.html` in your browser for the web interface
- Use the REST API endpoints (see [API Documentation](API_DOCUMENTATION.md))

#### Quick API Example:

1. Start a crawl:

```bash
curl -X POST http://127.0.0.1:5000/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.apple.com/iphone", "limit": 10}'
```

2. Search for images:

```bash
curl -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "chat_history": [
      {"role": "human", "content": "Show me iPhone camera images"}
    ]
  }'
```

## Search Examples

Once the system is ready, you can search using natural language:

- "Show me iPad images"
- "I want JPG photos of Apple Pencil"
- "Find iPhone camera pictures"
- "Apple Watch PNG images"

## Project Architecture

The application has been refactored into a modular, maintainable architecture:

```
app/
├── __init__.py           # Application factory
├── config.py             # Configuration settings
├── models/               # Data models
│   └── session.py        # CrawlSession class
├── routes/               # API endpoints
│   ├── admin_routes.py   # Session management
│   ├── crawl_routes.py   # Website crawling
│   └── search_routes.py  # Image search
├── services/             # Business logic
│   ├── crawler.py        # Crawling service
│   └── search.py         # Search service
└── utils/                # Helper functions
    └── helpers.py        # Utility functions
server.py                 # Entry point
combined.py               # Core functionality
requirements.txt          # Dependencies
.env                      # API keys (create this)
```

## Key Components

1. **Flask Application**: The main application using blueprints for route organization
2. **Services Layer**: Business logic for crawling and searching
3. **Models**: Data models for sessions and results
4. **Routes**: API endpoints organized by function
5. **Utils**: Shared utility functions

## API Endpoints

| Endpoint             | Method | Description                         |
| -------------------- | ------ | ----------------------------------- |
| `/crawl`             | POST   | Start crawling a website            |
| `/crawl/<id>/status` | GET    | Real-time crawl status (SSE)        |
| `/chat`              | POST   | Search images with natural language |
| `/sessions`          | GET    | List all crawl sessions             |
| `/health`            | GET    | Health check                        |
| `/sessions/<id>`     | DELETE | Delete a specific session           |
| `/cleanup`           | POST   | Clean up old sessions               |

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for detailed API usage.

## Features in Detail

### Smart Image Deduplication

- Removes duplicate images based on filenames
- Identifies similar images with different resolutions
- Prioritizes JPG and PNG formats
- Filters by Alt text similarity

### Real-time Progress Monitoring

- Server-Sent Events for live updates
- Track crawling progress
- See image extraction statistics
- Get notified when ready to search

### Natural Language Understanding

- AI parses your search intent
- Understands format preferences
- Contextual search based on Alt text
- Semantic similarity matching

### Concurrency Management

- Domain locking prevents duplicate crawls
- Session isolation with unique vector databases
- Resource limiting to prevent overload
- Automatic cleanup of old sessions

## Troubleshooting

1. **API Key Errors**: Make sure your `.env` file contains valid API keys
2. **Crawling Issues**: Some websites may block crawlers; try reducing the number of pages
3. **Memory Issues**: For large websites, consider crawling fewer pages at once
4. **No Images Found**: Some websites load images dynamically; the crawler waits for JS but may miss some
5. **Concurrent Crawls**: If you get a 429 error, wait for some crawls to complete

## Advanced Usage

### Using with Your Own Frontend

The Flask server provides a RESTful API that can be integrated with any frontend framework:

```javascript
// Start a crawl
fetch("http://127.0.0.1:5000/crawl", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ url: "https://example.com", limit: 5 }),
})
  .then((response) => response.json())
  .then((data) => {
    const sessionId = data.session_id;
    // Use session_id for status updates and searching
  });

// Subscribe to SSE updates
const eventSource = new EventSource(`/crawl/${sessionId}/status`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Status update:", data);
};
```

## Notes

- The system creates a folder named `crawled_pages_<domain>` for each website
- Images are deduplicated based on filenames and alt text
- Search prioritizes JPG and PNG formats by default
- The AI assistant understands various phrasings and languages
- Each crawl session maintains its own vector database
