"""
Flask Server for Website Crawler and Image Search
Provides API endpoints for crawling websites and searching images via chat
"""
import os
import json
import uuid
import threading
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import queue
import time
from dotenv import load_dotenv
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from firecrawl import ScrapeOptions

# Import our combined functionality
from combined import (
    crawl_website, 
    load_html_folder, 
    search_images_with_dedup,
    parse_user_query_with_ai,
    format_search_results_with_ai,
    OpenAIEmbeddings,
    Chroma,
    openai_api_key,
    firecrawl_app,
    fix_image_paths,
    url_to_filename
)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Storage for crawl sessions
crawl_sessions = {}
vector_stores = {}

# Concurrency controls
crawl_lock = threading.Lock()  # Protect session creation
active_crawls = {}  # Track active crawls by domain
MAX_CONCURRENT_CRAWLS = 3  # Limit concurrent crawls

def crawl_website_with_folder(start_url, limit, folder_name):
    """Crawl website and save HTML files to specified folder"""
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"✔ Created folder: {folder_name}")
    
    print(f"\n🕷️ Starting to crawl {start_url} (limit: {limit} pages)...")
    
    # Crawl pages
    crawl_result = firecrawl_app.crawl_url(
        start_url,
        limit=limit,
        scrape_options=ScrapeOptions(
            formats=['rawHtml'],
            onlyMainContent=False,
            includeTags=['img', 'source', 'picture', 'video'],
            renderJs=True,
            waitFor=3000,
            skipTlsVerification=False,
            removeBase64Images=False
        ),
    )
    
    print(f"✅ Successfully crawled {len(crawl_result.data)} pages")
    
    for i, page_data in enumerate(crawl_result.data, 1):
        url = page_data.metadata.get('url', f'page_{i}')
        print(f"Saving page {i}: {url}")
        
        filename = url_to_filename(url)
        filepath = os.path.join(folder_name, filename)
        
        fixed_html = fix_image_paths(page_data.rawHtml, url)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_html)
        
        print(f"  ✔ Saved as: {filepath}")
        
        soup = BeautifulSoup(fixed_html, 'html.parser')
        img_count = len(soup.find_all('img'))
        source_count = len(soup.find_all('source'))
        print(f"    Contains {img_count} img tags, {source_count} source tags")
    
    print(f"\n✔ All pages saved to {folder_name} folder")
    return folder_name

class CrawlSession:
    def __init__(self, session_id, url, limit):
        self.session_id = session_id
        self.url = url
        self.limit = limit
        self.status = "initializing"
        self.messages = queue.Queue()
        self.folder_name = None
        self.total_images = 0
        self.total_pages = 0
        self.error = None
        self.completed = False
        self.image_stats = {}
        
    def add_message(self, message_type, data):
        self.messages.put({
            "type": message_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })

def perform_crawl(session):
    """Perform the crawling operation in a background thread"""
    domain = None
    try:
        session.status = "crawling"
        session.add_message("status", {"status": "crawling", "message": f"Starting to crawl {session.url}"})
        
        # Create unique folder name using session ID
        parsed_url = urlparse(session.url)
        domain = parsed_url.netloc.replace('www.', '')
        base_folder = f"crawled_pages_{domain.replace('.', '_')}"
        unique_folder = f"{base_folder}_{session.session_id[:8]}"
        
        # Crawl the website with unique folder
        folder_name = crawl_website_with_folder(session.url, session.limit, unique_folder)
        session.folder_name = folder_name
        
        session.add_message("progress", {
            "message": f"Successfully crawled {session.limit} pages",
            "folder": folder_name
        })
        
        # Load and process HTML files
        session.status = "processing"
        session.add_message("status", {"status": "processing", "message": "Extracting images from HTML files"})
        
        all_docs = load_html_folder(folder_name)
        session.total_images = len(all_docs)
        
        # Count pages
        import glob
        html_files = glob.glob(os.path.join(folder_name, "*.html"))
        session.total_pages = len(html_files)
        
        # Gather statistics
        format_stats = {}
        page_stats = {}
        
        for doc in all_docs:
            # Format statistics
            fmt = doc.metadata['img_format']
            format_stats[fmt] = format_stats.get(fmt, 0) + 1
            
            # Page statistics
            source_url = doc.metadata['source_url']
            page_stats[source_url] = page_stats.get(source_url, 0) + 1
        
        session.image_stats = {
            "formats": format_stats,
            "pages": page_stats
        }
        
        session.add_message("progress", {
            "message": f"Processed {session.total_images} images from {session.total_pages} pages",
            "stats": session.image_stats
        })
        
        # Create vector store
        session.status = "indexing"
        session.add_message("status", {"status": "indexing", "message": "Creating vector database for image search"})
        
        embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        chroma_db = Chroma.from_documents(
            all_docs,
            embedding=embeddings,
            collection_name=f'crawl_{session.session_id}'
        )
        
        # Store the vector database
        vector_stores[session.session_id] = chroma_db
        
        # Generate summary
        summary = generate_crawl_summary(session)
        
        session.status = "completed"
        session.completed = True
        session.add_message("completed", {
            "status": "completed",
            "summary": summary,
            "total_images": session.total_images,
            "total_pages": session.total_pages,
            "stats": session.image_stats
        })
        
    except Exception as e:
        session.status = "error"
        session.error = str(e)
        session.add_message("error", {
            "status": "error",
            "message": f"Crawling failed: {str(e)}"
        })
    finally:
        # Clean up domain tracking
        if domain:
            with crawl_lock:
                active_crawls.pop(domain, None)

def generate_crawl_summary(session):
    """Generate a summary of what was crawled"""
    format_list = []
    for fmt, count in session.image_stats['formats'].items():
        if count > 0:
            format_list.append(f"{count} {fmt.upper()}")
    
    formats_str = ", ".join(format_list) if format_list else "various formats"
    
    # Get main pages
    main_pages = list(session.image_stats['pages'].keys())[:3]
    pages_str = ", ".join([p.split('/')[-1] or "homepage" for p in main_pages])
    
    summary = f"I've successfully crawled {session.url} and found {session.total_images} images across {session.total_pages} pages. "
    summary += f"The images include {formats_str}. "
    summary += f"Main pages include: {pages_str}. "
    summary += "You can now search for specific images by describing what you're looking for!"
    
    return summary

@app.route('/crawl', methods=['POST'])
def crawl():
    """Endpoint to start crawling a website"""
    data = request.json
    url = data.get('url')
    limit = data.get('limit', 10)
    
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    # Parse domain for tracking
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
    except:
        return jsonify({"error": "Invalid URL format"}), 400
    
    with crawl_lock:
        # Check concurrent crawl limits
        if len([s for s in crawl_sessions.values() if s.status in ["crawling", "processing", "indexing"]]) >= MAX_CONCURRENT_CRAWLS:
            return jsonify({"error": f"Maximum {MAX_CONCURRENT_CRAWLS} concurrent crawls allowed. Please try again later."}), 429
        
        # Check if same domain is already being crawled
        if domain in active_crawls:
            return jsonify({
                "error": f"Domain {domain} is already being crawled",
                "existing_session": active_crawls[domain],
                "message": "Please wait for the current crawl to complete or use the existing session"
            }), 409
        
        # Create a new crawl session
        session_id = str(uuid.uuid4())
        session = CrawlSession(session_id, url, limit)
        crawl_sessions[session_id] = session
        
        # Track domain as active
        active_crawls[domain] = session_id
    
    # Start crawling in background thread
    thread = threading.Thread(target=perform_crawl, args=(session,))
    thread.daemon = True  # Allow server to exit even if thread is running
    thread.start()
    
    return jsonify({
        "session_id": session_id,
        "message": "Crawling started",
        "subscribe_url": f"/crawl/{session_id}/status"
    })

@app.route('/crawl/<session_id>/status')
def crawl_status(session_id):
    """SSE endpoint for crawl status updates"""
    session = crawl_sessions.get(session_id)
    
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    def generate():
        # Send initial status
        yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
        
        # Send queued messages
        while True:
            try:
                # Check for new messages (timeout after 1 second)
                message = session.messages.get(timeout=1)
                yield f"data: {json.dumps(message)}\n\n"
                
                # If crawling is completed, close the connection
                if message.get('type') == 'completed' or message.get('type') == 'error':
                    break
                    
            except queue.Empty:
                # Send heartbeat to keep connection alive
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                
                # Check if we should continue
                if session.completed or session.error:
                    break
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint for chatting about crawled images"""
    data = request.json
    chat_history = data.get('chat_history', [])
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    # Check if session exists and has completed
    session = crawl_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    if not session.completed:
        return jsonify({"error": "Crawling not yet completed"}), 400
    
    # Get the vector store for this session
    chroma_db = vector_stores.get(session_id)
    if not chroma_db:
        return jsonify({"error": "Vector database not found"}), 404
    
    # Get the last human message
    last_human_message = None
    for message in reversed(chat_history):
        if message.get('role') == 'human':
            last_human_message = message.get('content', '')
            break
    
    if not last_human_message:
        return jsonify({"error": "No human message found in chat history"}), 400
    
    # Parse the query with AI
    parsed_query = parse_user_query_with_ai(last_human_message)
    
    # Search for images
    search_results = search_images_with_dedup(
        chroma_db,
        parsed_query['search_query'],
        format_filter=parsed_query['format_filter'],
        max_results=5
    )
    
    # Generate response
    if not search_results:
        response = "I couldn't find any images matching your search. Try describing what you're looking for differently, or ask about the types of images available."
    else:
        # Create a custom response that includes the search understanding
        response = f"{parsed_query['response_message']}\n\n"
        response += format_search_results_for_api(search_results, last_human_message)
    
    # Add session context if this is the first message
    if len(chat_history) == 1:  # Only the AI's initial message
        response = f"Based on my crawl of {session.url}, " + response
    
    return jsonify({
        "response": response,
        "search_results": [
            {
                "url": img['url'],
                "format": img['format'],
                "alt_text": img['alt_text'],
                "source_url": img['source_url'],
                "score": img['score']
            } for img in search_results[:5]
        ] if search_results else [],
        "session_id": session_id
    })

def format_search_results_for_api(search_results, query):
    """Format search results for API response"""
    if not search_results:
        return "No images found matching your search."
    
    result = f"I found {len(search_results)} relevant images:"
    
    return result

@app.route('/sessions', methods=['GET'])
def list_sessions():
    """List all crawl sessions"""
    sessions = []
    for session_id, session in crawl_sessions.items():
        sessions.append({
            "session_id": session_id,
            "url": session.url,
            "status": session.status,
            "total_images": session.total_images,
            "total_pages": session.total_pages,
            "completed": session.completed,
            "created_at": session.messages.queue[0]['timestamp'] if not session.messages.empty() else None
        })
    
    return jsonify({"sessions": sessions})

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "version": "1.0.0"})

@app.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a specific session and free resources"""
    if session_id not in crawl_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    # Clean up session data
    if session_id in vector_stores:
        del vector_stores[session_id]
    
    session = crawl_sessions[session_id]
    
    # Clean up domain tracking if still active
    try:
        parsed_url = urlparse(session.url)
        domain = parsed_url.netloc.replace('www.', '')
        with crawl_lock:
            active_crawls.pop(domain, None)
    except:
        pass
    
    del crawl_sessions[session_id]
    
    return jsonify({"message": f"Session {session_id} deleted successfully"})

@app.route('/cleanup', methods=['POST'])
def cleanup_old_sessions():
    """Clean up old completed sessions to free memory"""
    from datetime import datetime, timedelta
    
    data = request.json or {}
    hours_old = data.get('hours_old', 24)  # Default: clean sessions older than 24 hours
    
    cutoff_time = datetime.now() - timedelta(hours=hours_old)
    sessions_to_delete = []
    
    for session_id, session in crawl_sessions.items():
        # Check if session is old and completed/errored
        if session.status in ["completed", "error"]:
            try:
                # Get first message timestamp as creation time
                if not session.messages.empty():
                    first_message = session.messages.queue[0]
                    created_at = datetime.fromisoformat(first_message['timestamp'])
                    if created_at < cutoff_time:
                        sessions_to_delete.append(session_id)
            except:
                # If we can't parse timestamp, assume it's old
                sessions_to_delete.append(session_id)
    
    # Delete old sessions
    deleted_count = 0
    for session_id in sessions_to_delete:
        try:
            if session_id in vector_stores:
                del vector_stores[session_id]
            del crawl_sessions[session_id]
            deleted_count += 1
        except:
            pass
    
    return jsonify({
        "message": f"Cleaned up {deleted_count} old sessions",
        "deleted_sessions": sessions_to_delete,
        "remaining_sessions": len(crawl_sessions)
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True) 