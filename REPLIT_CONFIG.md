# Replit Deployment Configuration

This guide helps you configure the Flask server for optimal performance on Replit.

## Environment Variables

Add these to your Replit secrets or `.env` file:

```bash
# Disable SSE if having issues with Gunicorn
ENABLE_SSE=false

# Reduce SSE timeout for better stability (in seconds)
SSE_TIMEOUT_SECONDS=120

# Flask configuration
FLASK_DEBUG=false
PORT=5001
```

## Replit Configuration

### Option 1: Use Polling Instead of SSE (Recommended for Replit)

If you're having SSE issues, disable SSE and use the polling endpoint:

```python
# Set in your environment
ENABLE_SSE=false
```

Then use the polling endpoint in your frontend:

```javascript
// Instead of SSE connection
const response = await fetch(`/crawl/${sessionId}/status-simple`);
const status = await response.json();
```

### Option 2: Configure Gunicorn for SSE

If you want to keep SSE, create a `gunicorn_config.py`:

```python
# gunicorn_config.py
bind = "0.0.0.0:5001"
workers = 1
worker_class = "gevent"
worker_connections = 1000
timeout = 300
keepalive = 60
max_requests = 1000
max_requests_jitter = 100
```

Then run with:

```bash
gunicorn -c gunicorn_config.py flask_server:app
```

## API Endpoints

The server now provides both SSE and polling options:

### SSE Endpoint (Real-time)

```
GET /crawl/{session_id}/status
```

### Polling Endpoint (Reliable)

```
GET /crawl/{session_id}/status-simple
```

### Usage Example

```javascript
// Check if SSE is available
async function getStatus(sessionId) {
  try {
    // Try SSE first
    const eventSource = new EventSource(`/crawl/${sessionId}/status`);
    return eventSource;
  } catch (error) {
    // Fall back to polling
    return setInterval(async () => {
      const response = await fetch(`/crawl/${sessionId}/status-simple`);
      const status = await response.json();
      handleStatusUpdate(status);
    }, 2000); // Poll every 2 seconds
  }
}
```

## Troubleshooting

### If you see "SystemExit: 1" errors:

1. Set `ENABLE_SSE=false`
2. Use the polling endpoint
3. Consider using gevent workers

### If crawling seems slow:

1. Check your Pinecone quota
2. Reduce crawl limits
3. Monitor memory usage

### For production deployment:

1. Always set `FLASK_DEBUG=false`
2. Use environment variables for API keys
3. Configure proper timeouts
4. Monitor resource usage
