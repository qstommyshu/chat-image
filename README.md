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
python flask_server.py
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

## File Structure

```
.
├── app.py                 # CLI entry point
├── combined.py            # Core crawler and search functionality
├── flask_server.py        # Flask API server
├── client_example.html    # Web UI example
├── API_DOCUMENTATION.md   # Detailed API docs
├── crawled_pages_*/       # Folders with crawled HTML files (auto-created)
├── requirements.txt       # Python dependencies
└── .env                  # API keys (create this)
```

## API Endpoints

| Endpoint             | Method | Description                         |
| -------------------- | ------ | ----------------------------------- |
| `/crawl`             | POST   | Start crawling a website            |
| `/crawl/<id>/status` | GET    | Real-time crawl status (SSE)        |
| `/chat`              | POST   | Search images with natural language |
| `/sessions`          | GET    | List all crawl sessions             |
| `/health`            | GET    | Health check                        |

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

## Troubleshooting

1. **API Key Errors**: Make sure your `.env` file contains valid API keys
2. **Crawling Issues**: Some websites may block crawlers; try reducing the number of pages
3. **Memory Issues**: For large websites, consider crawling fewer pages at once
4. **No Images Found**: Some websites load images dynamically; the crawler waits for JS but may miss some

## Advanced Usage

### Direct Module Usage

```python
from combined import crawl_website, load_html_folder, conversational_search

# Crawl a website
folder = crawl_website("https://example.com", limit=10)

# Load and process HTML files
docs = load_html_folder(folder)

# Start search interface
conversational_search(chroma_db)
```

### Using with Your Own Frontend

The Flask server provides a simple REST API that can be integrated with any frontend framework. See the `client_example.html` for a reference implementation.

## Notes

- The system creates a folder named `crawled_pages_<domain>` for each website
- Images are deduplicated based on filenames and alt text
- Search prioritizes JPG and PNG formats by default
- The AI assistant understands various phrasings and languages
- Each crawl session maintains its own vector database
