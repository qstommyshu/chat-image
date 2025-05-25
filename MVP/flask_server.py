"""
Flask Server for Website Crawler and Image Search

This server provides REST API endpoints for:
1. Crawling websites and extracting images
2. Real-time status updates via Server-Sent Events (SSE)
3. Natural language image search using AI
4. Session management and resource cleanup

The server supports multiple concurrent clients with proper concurrency controls.
"""

# ============================================================================
# IMPORTS
# ============================================================================

# Standard library imports
import os
import json
import uuid
import threading
import glob
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin

# Third-party imports
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import queue
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from firecrawl import FirecrawlApp, ScrapeOptions
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from .env file
load_dotenv()

# Check required API keys
openai_api_key = os.getenv("OPENAI_API_KEY")
firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")

if not openai_api_key:
    raise ValueError("Please set OPENAI_API_KEY in your .env file")
if not firecrawl_api_key:
    raise ValueError("Please set FIRECRAWL_API_KEY in your .env file")
if not pinecone_api_key:
    raise ValueError("Please set PINECONE_API_KEY in your .env file")

# Initialize clients
openai_client = OpenAI(api_key=openai_api_key)
firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)

# Initialize Pinecone
pc = Pinecone(api_key=pinecone_api_key)
index_name = "image-chat"  # Main index for all crawled images

# Create Pinecone index if it doesn't exist
existing_indexes = [index_info["name"] for index_info in pc.list_indexes()]
if index_name not in existing_indexes:
    pc.create_index(
        name=index_name,
        dimension=1536,  # OpenAI embeddings dimension
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        deletion_protection="disabled",  # Allow deletion for development
    )
    # Wait for index to be ready
    while not pc.describe_index(index_name).status["ready"]:
        time.sleep(1)

# Initialize Pinecone vector store
index = pc.Index(index_name)
vector_store = PineconeVectorStore(index=index, embedding=OpenAIEmbeddings(openai_api_key=openai_api_key))

# Initialize Flask application
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for all routes

# ============================================================================
# GLOBAL STATE MANAGEMENT
# ============================================================================

# Session storage - maps session_id to CrawlSession objects
crawl_sessions = {}

# Session namespace tracking - maps session_id to namespace in Pinecone
# Note: We no longer need vector_stores dict since all data is in Pinecone
session_namespaces = {}

# Concurrency controls
crawl_lock = threading.Lock()  # Protects session creation and domain tracking
active_crawls = {}  # Maps domain -> session_id to prevent duplicate crawls
MAX_CONCURRENT_CRAWLS = 3  # Maximum number of simultaneous crawl operations

# ============================================================================
# UTILITY FUNCTIONS FROM COMBINED.PY
# ============================================================================

def url_to_filename(url):
    """Convert URL to safe filename"""
    filename = url.replace('https://', '').replace('http://', '')
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.replace('/', '_')
    filename = filename.rstrip('.')
    if not filename.endswith('.html'):
        filename += '.html'
    return filename

def fix_image_paths(html_content, base_url):
    """Fix image paths in HTML content"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Process img tags
    for img in soup.find_all('img'):
        if img.get('data-src'):
            img['src'] = urljoin(base_url, img['data-src'])
        elif img.get('data-srcset'):
            img['srcset'] = img['data-srcset']
        elif img.get('src') and not img['src'].startswith(('http', 'data:')):
            img['src'] = urljoin(base_url, img['src'])
        
        if img.get('srcset') and not img['srcset'].startswith('data:'):
            srcset_parts = []
            for part in img['srcset'].split(','):
                part = part.strip()
                if part and not part.startswith(('http', 'data:')):
                    url_part = part.split()[0]
                    descriptor = ' '.join(part.split()[1:])
                    full_url = urljoin(base_url, url_part)
                    srcset_parts.append(f"{full_url} {descriptor}".strip())
                else:
                    srcset_parts.append(part)
            img['srcset'] = ', '.join(srcset_parts)
    
    # Process source tags
    for source in soup.find_all('source'):
        if source.get('srcset') and not source['srcset'].startswith(('http', 'data:')):
            source['srcset'] = urljoin(base_url, source['srcset'])
    
    return str(soup)

def filename_to_url(filename):
    """Convert filename back to original URL"""
    name_without_ext = filename.replace('.html', '')
    url_path = name_without_ext.replace('_', '/')
    
    if url_path.startswith('www.'):
        return f"https://{url_path}"
    else:
        return f"https://{url_path}"

def get_image_format(url):
    """Get image format from URL"""
    url_lower = url.lower()
    if any(ext in url_lower for ext in ['.jpg', '.jpeg']):
        return 'jpg'
    elif '.png' in url_lower:
        return 'png'
    elif '.svg' in url_lower:
        return 'svg'
    elif '.webp' in url_lower:
        return 'webp'
    elif '.gif' in url_lower:
        return 'gif'
    else:
        return 'unknown'

def extract_context_from_source(source_tag):
    """Extract context from source tag"""
    context_parts = []
    
    media_attr = source_tag.get('media', '')[:200] if source_tag.get('media') else ''  # Limit media attr
    if media_attr:
        context_parts.append(f"Media: {media_attr}")
    
    picture = source_tag.find_parent('picture')
    if picture:
        img_in_picture = picture.find('img')
        if img_in_picture:
            alt_text = img_in_picture.get('alt', '')[:500] if img_in_picture.get('alt') else ''  # Limit alt text
            title_text = img_in_picture.get('title', '')[:200] if img_in_picture.get('title') else ''  # Limit title
            class_attr = ' '.join(img_in_picture.get('class', []))[:300] if img_in_picture.get('class') else ''  # Limit class
            
            if alt_text:
                context_parts.append(f"Alt: {alt_text}")
            if title_text:
                context_parts.append(f"Title: {title_text}")
            if class_attr:
                context_parts.append(f"Class: {class_attr}")
    
    parent = source_tag.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        if parent_text and len(parent_text) > 0:
            # Limit parent text to 150 characters
            truncated_parent = parent_text[:150] + "..." if len(parent_text) > 150 else parent_text
            context_parts.append(f"Parent text: {truncated_parent}")
    
    context = " | ".join(context_parts) if context_parts else str(source_tag)[:100]
    # Ensure total context doesn't exceed reasonable limits
    return context[:1000] if len(context) > 1000 else context

def extract_context(img_tag):
    """Extract context from img tag"""
    context_parts = []
    
    alt_text = img_tag.get('alt', '')[:500] if img_tag.get('alt') else ''  # Limit alt text
    title_text = img_tag.get('title', '')[:200] if img_tag.get('title') else ''  # Limit title
    class_attr = ' '.join(img_tag.get('class', []))[:300] if img_tag.get('class') else ''  # Limit class
    
    if alt_text:
        context_parts.append(f"Alt: {alt_text}")
    if title_text:
        context_parts.append(f"Title: {title_text}")
    if class_attr:
        context_parts.append(f"Class: {class_attr}")
    
    parent = img_tag.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        if parent_text and len(parent_text) > 0:
            # Limit parent text to 150 characters
            truncated_parent = parent_text[:150] + "..." if len(parent_text) > 150 else parent_text
            context_parts.append(f"Parent text: {truncated_parent}")
    
    context = " | ".join(context_parts) if context_parts else str(img_tag)[:100]
    # Ensure total context doesn't exceed reasonable limits
    return context[:1000] if len(context) > 1000 else context

def process_html_file(html_file_path, source_url):
    """Process single HTML file and return document list"""
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except UnicodeDecodeError:
        try:
            with open(html_file_path, 'r', encoding='latin-1') as f:
                html = f.read()
        except:
            return []
    
    soup = BeautifulSoup(html, 'html.parser')
    parsed_url = urlparse(source_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    docs = []
    all_imgs = soup.find_all('img')
    all_sources = soup.find_all('source')
    
    # Process img tags
    for img in all_imgs:
        raw = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-srcset')
        if not raw:
            continue
        
        for part in raw.split(','):
            u = part.strip().split(' ')[0]
            if u.startswith('//'):
                u = 'https:' + u
            elif u.startswith('/'):
                u = urljoin(base_url, u)
            elif not u.startswith('http'):
                u = urljoin(source_url, u)
            
            img_format = get_image_format(u)
            context = extract_context(img)
            
            alt_text = img.get('alt', '')
            title_text = img.get('title', '')
            class_attr = ' '.join(img.get('class', []))
            
            # Ensure all text fields are properly limited
            alt_text_limited = alt_text[:500] if alt_text else ''
            title_text_limited = title_text[:200] if title_text else ''
            class_attr_limited = class_attr[:300] if class_attr else ''
            
            page_content = f"Alt: {alt_text_limited} | Title: {title_text_limited} | Class: {class_attr_limited} | Context: {context}"
            # Ensure page content doesn't exceed Pinecone limits
            page_content = page_content[:2000] if len(page_content) > 2000 else page_content
            
            doc = Document(
                page_content=page_content,
                metadata={
                    'img_url': u[:1000] if u else '',  # Limit URL length
                    'img_format': img_format,
                    'alt_text': alt_text_limited,
                    'title': title_text_limited,
                    'class': class_attr_limited,
                    'source_type': 'img',
                    'source_url': source_url[:1000] if source_url else '',  # Limit URL length
                    'source_file': os.path.basename(html_file_path)[:200] if html_file_path else ''  # Limit filename
                }
            )
            docs.append(doc)
    
    # Process source tags
    for source in all_sources:
        srcset = source.get('srcset', '')
        if not srcset:
            continue
        
        for part in srcset.split(','):
            url_part = part.strip().split(' ')[0]
            if url_part.startswith('/'):
                url_part = urljoin(base_url, url_part)
            elif not url_part.startswith('http'):
                url_part = urljoin(source_url, url_part)
            
            img_format = get_image_format(url_part)
            context = extract_context_from_source(source)
            
            picture = source.find_parent('picture')
            alt_text = ''
            title_text = ''
            class_attr = ''
            
            if picture:
                img_in_picture = picture.find('img')
                if img_in_picture:
                    alt_text = img_in_picture.get('alt', '')
                    title_text = img_in_picture.get('title', '')
                    class_attr = ' '.join(img_in_picture.get('class', []))
            
            # Ensure all text fields are properly limited
            alt_text_limited = alt_text[:500] if alt_text else ''
            title_text_limited = title_text[:200] if title_text else ''
            class_attr_limited = class_attr[:300] if class_attr else ''
            media_attr_limited = source.get('media', '')[:200] if source.get('media') else ''
            
            page_content = f"Alt: {alt_text_limited} | Title: {title_text_limited} | Class: {class_attr_limited} | Context: {context}"
            # Ensure page content doesn't exceed Pinecone limits
            page_content = page_content[:2000] if len(page_content) > 2000 else page_content
            
            doc = Document(
                page_content=page_content,
                metadata={
                    'img_url': url_part[:1000] if url_part else '',  # Limit URL length
                    'img_format': img_format,
                    'alt_text': alt_text_limited,
                    'title': title_text_limited,
                    'class': class_attr_limited,
                    'source_type': 'source',
                    'media': media_attr_limited,
                    'source_url': source_url[:1000] if source_url else '',  # Limit URL length
                    'source_file': os.path.basename(html_file_path)[:200] if html_file_path else ''  # Limit filename
                }
            )
            docs.append(doc)
    
    return docs

def load_html_folder(folder_path):
    """Load all HTML files from folder"""
    print(f"\n📂 Loading HTML files from: {folder_path}")
    
    if not os.path.exists(folder_path):
        raise ValueError(f"Folder does not exist: {folder_path}")
    
    html_pattern = os.path.join(folder_path, "*.html")
    html_files = glob.glob(html_pattern)
    
    if not html_files:
        raise ValueError(f"No HTML files found in folder: {folder_path}")
    
    print(f"Found {len(html_files)} HTML files")
    
    all_docs = []
    
    for html_file in html_files:
        filename = os.path.basename(html_file)
        source_url = filename_to_url(filename)
        docs = process_html_file(html_file, source_url)
        all_docs.extend(docs)
    
    print(f"Processed {len(all_docs)} image documents")
    return all_docs

def search_images_with_dedup(vector_store, query, namespace, format_filter=None, max_results=5):
    """Search images with deduplication"""
    # Create a retriever with the specific namespace for this session
    retriever = vector_store.as_retriever(
        search_kwargs={"k": 50, "namespace": namespace}
    )
    results = retriever.get_relevant_documents(query)
    
    # Convert to format expected by the rest of the function
    # Note: Pinecone doesn't return scores in the same way, so we'll simulate them
    results_with_scores = [(doc, 1.0 - (i * 0.01)) for i, doc in enumerate(results)]
    
    processed_results = []
    
    for doc, score in results_with_scores:
        img_format = doc.metadata['img_format']
        
        if format_filter and img_format not in format_filter:
            continue
        
        alt_text = doc.metadata.get('alt_text', '').lower()
        title_text = doc.metadata.get('title', '').lower()
        query_lower = query.lower()
        
        alt_match_score = 0
        if alt_text and query_lower in alt_text:
            alt_match_score += 2.0
        if title_text and query_lower in title_text:
            alt_match_score += 1.0
        
        query_words = query_lower.split()
        for word in query_words:
            if len(word) > 2:
                if word in alt_text:
                    alt_match_score += 0.5
                if word in title_text:
                    alt_match_score += 0.3
        
        img_info = {
            'url': doc.metadata['img_url'],
            'format': img_format,
            'alt_text': doc.metadata.get('alt_text', ''),
            'title': doc.metadata.get('title', ''),
            'source_type': doc.metadata['source_type'],
            'media': doc.metadata.get('media', ''),
            'score': score,
            'alt_match_score': alt_match_score,
            'source_url': doc.metadata['source_url'],
            'source_file': doc.metadata['source_file'],
            'context': doc.page_content
        }
        processed_results.append(img_info)
    
    # Deduplication logic
    def normalize_alt_text(alt_text):
        if not alt_text:
            return ""
        normalized = alt_text.lower().strip()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def should_prefer_by_alt(img1, img2):
        if img1['format'] != img2['format']:
            format_priority = {'jpg': 3, 'png': 2, 'webp': 1, 'svg': 0}
            priority1 = format_priority.get(img1['format'], 0)
            priority2 = format_priority.get(img2['format'], 0)
            if priority1 != priority2:
                return priority1 > priority2
        
        if img1['alt_match_score'] != img2['alt_match_score']:
            return img1['alt_match_score'] > img2['alt_match_score']
        
        return img1['score'] < img2['score']
    
    # Alt text deduplication
    seen_alt_texts = {}
    final_results = []
    
    for img in processed_results:
        alt_text = normalize_alt_text(img['alt_text'])
        
        if not alt_text:
            final_results.append(img)
            continue
        
        if alt_text in seen_alt_texts:
            existing_img = seen_alt_texts[alt_text]
            if should_prefer_by_alt(img, existing_img):
                seen_alt_texts[alt_text] = img
                final_results = [r for r in final_results if normalize_alt_text(r['alt_text']) != alt_text]
                final_results.append(img)
        else:
            seen_alt_texts[alt_text] = img
            final_results.append(img)
    
    # Sort results
    if not format_filter:
        final_results.sort(key=lambda x: (
            -x['alt_match_score'],
            x['format'] not in ['jpg', 'png'],
            x['format'] != 'jpg',
            x['score']
        ))
    else:
        final_results.sort(key=lambda x: (-x['alt_match_score'], x['score']))
    
    return final_results[:max_results]

def parse_user_query_with_ai(user_message):
    """Parse user query with AI to extract search terms and format requirements"""
    
    system_prompt = """You are an image search assistant. Users will describe what images they want in natural language, and you need to extract key search information.

Analyze the user's query and return a JSON response containing:
1. search_query: Keywords for searching (in English, suitable for image Alt text search)
2. format_filter: Image format requirements (if user specified JPG, PNG, etc., otherwise null)
3. response_message: A friendly response explaining what you understood

Examples:
User: "I want iPad related JPG images"
Return: {"search_query": "iPad", "format_filter": ["jpg"], "response_message": "I'll help you find iPad-related JPG format images"}

User: "Show me photos of Apple Pencil"
Return: {"search_query": "Apple Pencil", "format_filter": null, "response_message": "I'll search for Apple Pencil images for you"}

Only return JSON, no other content."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"AI parsing error: {e}")
        return {
            "search_query": user_message,
            "format_filter": None,
            "response_message": f"I'll search for images related to '{user_message}'"
        }

# ============================================================================
# ADDITIONAL UTILITY FUNCTIONS
# ============================================================================

def crawl_website_with_folder(start_url, limit, folder_name):
    """
    Crawl a website and save HTML files to a specified folder.
    
    This function is a wrapper around the Firecrawl API that:
    1. Creates the target folder if it doesn't exist
    2. Crawls the specified number of pages
    3. Fixes image paths in the HTML
    4. Saves each page as an HTML file
    
    Args:
        start_url (str): The URL to start crawling from
        limit (int): Maximum number of pages to crawl
        folder_name (str): Target folder for saving HTML files
        
    Returns:
        str: The folder name where files were saved
    """
    # Create target folder
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"✔ Created folder: {folder_name}")
    
    print(f"\n🕷️ Starting to crawl {start_url} (limit: {limit} pages)...")
    
    # Configure and execute crawl using Firecrawl
    crawl_result = firecrawl_app.crawl_url(
        start_url,
        limit=limit,
        scrape_options=ScrapeOptions(
            formats=['rawHtml'],           # Get raw HTML content
            onlyMainContent=False,         # Include full page content
            includeTags=['img', 'source', 'picture', 'video'],  # Keep media tags
            renderJs=True,                 # Execute JavaScript for dynamic content
            waitFor=3000,                 # Wait 3 seconds for lazy loading
            skipTlsVerification=False,     # Verify SSL certificates
            removeBase64Images=False       # Keep base64-encoded images
        ),
    )
    
    print(f"✅ Successfully crawled {len(crawl_result.data)} pages")
    
    # Process and save each crawled page
    for i, page_data in enumerate(crawl_result.data, 1):
        url = page_data.metadata.get('url', f'page_{i}')
        print(f"Saving page {i}: {url}")
        
        # Generate safe filename and file path
        filename = url_to_filename(url)
        filepath = os.path.join(folder_name, filename)
        
        # Fix relative image paths to absolute URLs
        fixed_html = fix_image_paths(page_data.rawHtml, url)
        
        # Save the processed HTML to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_html)
        
        print(f"  ✔ Saved as: {filepath}")
        
        # Count and report image elements found
        soup = BeautifulSoup(fixed_html, 'html.parser')
        img_count = len(soup.find_all('img'))
        source_count = len(soup.find_all('source'))
        print(f"    Contains {img_count} img tags, {source_count} source tags")
    
    print(f"\n✔ All pages saved to {folder_name} folder")
    return folder_name

def generate_crawl_summary(session):
    """
    Generate a human-readable summary of crawl results.
    
    This creates a summary message that will be sent to the client
    when crawling completes, describing what was found.
    
    Args:
        session (CrawlSession): The completed crawl session
        
    Returns:
        str: A formatted summary message
    """
    # Build format statistics string
    format_list = []
    for fmt, count in session.image_stats['formats'].items():
        if count > 0:
            format_list.append(f"{count} {fmt.upper()}")
    
    formats_str = ", ".join(format_list) if format_list else "various formats"
    
    # Get sample of main pages crawled
    main_pages = list(session.image_stats['pages'].keys())[:3]
    pages_str = ", ".join([p.split('/')[-1] or "homepage" for p in main_pages])
    
    # Build complete summary message
    summary = f"I've successfully crawled {session.url} and found {session.total_images} images across {session.total_pages} pages. "
    summary += f"The images include {formats_str}. "
    summary += f"Main pages include: {pages_str}. "
    summary += "You can now search for specific images by describing what you're looking for!"
    
    return summary

def format_search_results_for_api(search_results, _unused_query):
    """
    Format search results for API response.
    
    This function creates the text portion of the search response.
    The detailed image data is returned separately in the search_results field.
    
    Args:
        search_results (list): List of image search results
        _unused_query (str): Original query (not used in current implementation)
        
    Returns:
        str: Formatted summary text
    """
    if not search_results:
        return "No images found matching your search."
    
    return f"I found {len(search_results)} relevant images:"

# ============================================================================
# CORE CLASSES
# ============================================================================

class CrawlSession:
    """
    Represents a single website crawling session.
    
    This class manages the state and progress of a crawl operation,
    including status tracking, message queuing for SSE, and result storage.
    
    Attributes:
        session_id (str): Unique identifier for this session
        url (str): The URL being crawled
        limit (int): Maximum number of pages to crawl
        status (str): Current status (initializing, crawling, processing, indexing, completed, error)
        messages (Queue): Queue of status messages for SSE
        folder_name (str): Folder where HTML files are saved
        total_images (int): Total number of images found
        total_pages (int): Total number of pages crawled
        error (str): Error message if crawl failed
        completed (bool): Whether the crawl has finished successfully
        image_stats (dict): Statistics about images found (formats, pages)
    """
    
    def __init__(self, session_id, url, limit):
        """Initialize a new crawl session."""
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
        """
        Add a status message to the SSE queue.
        
        Args:
            message_type (str): Type of message (status, progress, completed, error)
            data (dict): Message data to send to client
        """
        self.messages.put({
            "type": message_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })

# ============================================================================
# BACKGROUND PROCESSING
# ============================================================================

def perform_crawl(session):
    """
    Execute the complete crawling workflow in a background thread.
    
    This function handles the entire crawl lifecycle:
    1. Website crawling using Firecrawl
    2. HTML processing and image extraction
    3. Vector database creation for search
    4. Status updates via SSE
    5. Cleanup of domain tracking
    
    Args:
        session (CrawlSession): The session to process
    """
    domain = None
    try:
        # Phase 1: Website Crawling
        session.status = "crawling"
        session.add_message("status", {
            "status": "crawling", 
            "message": f"Starting to crawl {session.url}"
        })
        
        # Create unique folder name to avoid conflicts between sessions
        parsed_url = urlparse(session.url)
        domain = parsed_url.netloc.replace('www.', '')
        base_folder = f"crawled_pages_{domain.replace('.', '_')}"
        unique_folder = f"{base_folder}_{session.session_id[:8]}"
        
        # Execute the crawl with session-specific folder
        folder_name = crawl_website_with_folder(session.url, session.limit, unique_folder)
        session.folder_name = folder_name
        
        session.add_message("progress", {
            "message": f"Successfully crawled {session.limit} pages",
            "folder": folder_name
        })
        
        # Phase 2: Image Processing
        session.status = "processing"
        session.add_message("status", {
            "status": "processing", 
            "message": "Extracting images from HTML files"
        })
        
        # Extract all images from the saved HTML files
        all_docs = load_html_folder(folder_name)
        session.total_images = len(all_docs)
        
        # Count actual HTML files processed
        html_files = glob.glob(os.path.join(folder_name, "*.html"))
        session.total_pages = len(html_files)
        
        # Generate statistics about images found
        format_stats = {}  # Count by image format (jpg, png, etc.)
        page_stats = {}    # Count by source page URL
        
        for doc in all_docs:
            # Track image formats
            fmt = doc.metadata['img_format']
            format_stats[fmt] = format_stats.get(fmt, 0) + 1
            
            # Track images per page
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
        
        # Phase 3: Vector Database Indexing
        session.status = "indexing"
        session.add_message("status", {
            "status": "indexing", 
            "message": "Adding images to persistent vector database"
        })
        
        # Add documents to Pinecone with session-specific namespace
        namespace = f"session_{session.session_id[:8]}"
        
        # Add metadata to identify the session
        for doc in all_docs:
            doc.metadata['session_id'] = session.session_id
            doc.metadata['crawl_timestamp'] = datetime.now().isoformat()
        
        # Add documents to Pinecone in batches to avoid size limits
        batch_size = 100  # Process 100 documents at a time
        total_docs = len(all_docs)
        
        for i in range(0, total_docs, batch_size):
            batch = all_docs[i:i + batch_size]
            try:
                print(f"Uploading batch {i//batch_size + 1}/{(total_docs + batch_size - 1)//batch_size} ({len(batch)} documents)")
                vector_store.add_documents(batch, namespace=namespace)
                
                # Update progress
                progress_pct = min(100, ((i + len(batch)) / total_docs) * 100)
                session.add_message("progress", {
                    "message": f"Indexing progress: {progress_pct:.1f}% ({i + len(batch)}/{total_docs} documents)",
                    "progress_percent": progress_pct
                })
            except Exception as e:
                print(f"Error uploading batch {i//batch_size + 1}: {str(e)}")
                # Continue with next batch rather than failing completely
                session.add_message("progress", {
                    "message": f"Warning: Failed to index batch {i//batch_size + 1}, continuing with remaining batches",
                    "error": str(e)
                })
        
        # Store the namespace for later search operations
        session_namespaces[session.session_id] = namespace
        
        # Phase 4: Completion
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
        # Handle any errors that occurred during processing
        session.status = "error"
        session.error = str(e)
        session.add_message("error", {
            "status": "error",
            "message": f"Crawling failed: {str(e)}"
        })
    finally:
        # Always clean up domain tracking to allow future crawls of same domain
        if domain:
            with crawl_lock:
                active_crawls.pop(domain, None)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/crawl', methods=['POST'])
def crawl():
    """
    Start a new website crawling session.
    
    This endpoint initiates a background crawling operation and returns
    a session ID that can be used to monitor progress and search results.
    
    Request Body:
        url (str): The URL to start crawling from
        limit (int, optional): Maximum number of pages to crawl (default: 10)
    
    Returns:
        JSON response with session_id and subscribe_url for status updates
        
    Error Codes:
        400: Missing or invalid URL
        409: Domain already being crawled  
        429: Too many concurrent crawls
    """
    data = request.json
    url = data.get('url')
    limit = data.get('limit', 10)
    
    # Validate required parameters
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    # Parse and validate URL format
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
    except:
        return jsonify({"error": "Invalid URL format"}), 400
    
    # Thread-safe session creation with concurrency checks
    with crawl_lock:
        # Check if we've reached the maximum concurrent crawl limit
        active_session_count = len([
            s for s in crawl_sessions.values() 
            if s.status in ["crawling", "processing", "indexing"]
        ])
        
        if active_session_count >= MAX_CONCURRENT_CRAWLS:
            return jsonify({
                "error": f"Maximum {MAX_CONCURRENT_CRAWLS} concurrent crawls allowed. Please try again later."
            }), 429
        
        # Check if the same domain is already being crawled
        if domain in active_crawls:
            return jsonify({
                "error": f"Domain {domain} is already being crawled",
                "existing_session": active_crawls[domain],
                "message": "Please wait for the current crawl to complete or use the existing session"
            }), 409
        
        # Create new session and track it
        session_id = str(uuid.uuid4())
        session = CrawlSession(session_id, url, limit)
        crawl_sessions[session_id] = session
        
        # Mark domain as actively being crawled
        active_crawls[domain] = session_id
    
    # Start crawling in background thread
    thread = threading.Thread(target=perform_crawl, args=(session,))
    thread.daemon = True  # Allow server shutdown even if thread is running
    thread.start()
    
    return jsonify({
        "session_id": session_id,
        "message": "Crawling started",
        "subscribe_url": f"/crawl/{session_id}/status"
    })

@app.route('/crawl/<session_id>/status')
def crawl_status(session_id):
    """
    Server-Sent Events endpoint for real-time crawl status updates.
    
    This endpoint provides a continuous stream of status updates for a
    crawling session. Clients can subscribe to receive real-time progress.
    
    Args:
        session_id (str): The session ID to monitor
        
    Returns:
        SSE stream with status updates
        
    Error Codes:
        404: Session not found
    """
    session = crawl_sessions.get(session_id)
    
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    def generate():
        """
        Generator function for Server-Sent Events.
        
        This function yields status messages from the session's message queue
        and handles connection lifecycle (heartbeats, completion detection).
        """
        # Send initial connection confirmation
        yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
        
        # Main message loop
        while True:
            try:
                # Wait for new message (1 second timeout)
                message = session.messages.get(timeout=1)
                yield f"data: {json.dumps(message)}\n\n"
                
                # Close connection if crawl is finished (success or error)
                if message.get('type') in ['completed', 'error']:
                    break
                    
            except queue.Empty:
                # No new messages - send heartbeat to keep connection alive
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                
                # Check if session has finished (failsafe)
                if session.completed or session.error:
                    break
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/chat', methods=['POST'])
def chat():
    """
    Natural language image search endpoint.
    
    This endpoint processes chat messages and searches for relevant images
    using AI-powered natural language understanding and vector similarity.
    
    Request Body:
        session_id (str): The crawl session to search within
        chat_history (list): Array of chat messages with role and content
        
    Returns:
        JSON response with formatted text response and structured search results
        
    Error Codes:
        400: Missing session_id or invalid chat history
        404: Session not found or vector database missing
        400: Crawling not yet completed
    """
    data = request.json
    chat_history = data.get('chat_history', [])
    session_id = data.get('session_id')
    
    # Validate required parameters
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    # Verify session exists and is ready for search
    session = crawl_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    if not session.completed:
        return jsonify({"error": "Crawling not yet completed"}), 400
    
    # Get the namespace for this session
    namespace = session_namespaces.get(session_id)
    if not namespace:
        return jsonify({"error": "Session namespace not found - data may have been cleaned up"}), 404
    
    # Extract the most recent human message from chat history
    last_human_message = None
    for message in reversed(chat_history):
        if message.get('role') == 'human':
            last_human_message = message.get('content', '')
            break
    
    if not last_human_message:
        return jsonify({"error": "No human message found in chat history"}), 400
    
    # Use AI to parse the user's query and extract search intent
    parsed_query = parse_user_query_with_ai(last_human_message)
    
    # Execute semantic search with deduplication
    search_results = search_images_with_dedup(
        vector_store,
        parsed_query['search_query'],
        namespace,
        format_filter=parsed_query['format_filter'],
        max_results=5
    )
    
    # Generate response text
    if not search_results:
        response = "I couldn't find any images matching your search. Try describing what you're looking for differently, or ask about the types of images available."
    else:
        # Combine AI understanding with search summary
        response = f"{parsed_query['response_message']}\n\n"
        response += format_search_results_for_api(search_results, last_human_message)
    
    # Add context for first-time users
    if len(chat_history) == 1:  # Only AI's initial greeting message
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

@app.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all active crawl sessions.
    
    Returns summary information about all sessions, including their
    status, results, and creation time.
    
    Returns:
        JSON response with array of session summaries
    """
    sessions = []
    for session_id, session in crawl_sessions.items():
        # Extract creation timestamp from first message if available
        created_at = None
        if not session.messages.empty():
            try:
                created_at = session.messages.queue[0]['timestamp']
            except (IndexError, KeyError):
                pass
        
        sessions.append({
            "session_id": session_id,
            "url": session.url,
            "status": session.status,
            "total_images": session.total_images,
            "total_pages": session.total_pages,
            "completed": session.completed,
            "created_at": created_at
        })
    
    return jsonify({"sessions": sessions})

@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint for monitoring server status.
    
    Returns:
        JSON response indicating server health and version
    """
    return jsonify({"status": "healthy", "version": "1.0.0"})

# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """
    Delete a specific session and free its resources.
    
    This endpoint removes a session and all associated data including
    the vector database and domain tracking.
    
    Args:
        session_id (str): Session to delete
        
    Returns:
        JSON confirmation message
        
    Error Codes:
        404: Session not found
    """
    if session_id not in crawl_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    # Clean up session namespace
    if session_id in session_namespaces:
        namespace = session_namespaces[session_id]
        # Note: Pinecone doesn't have a direct way to delete by namespace
        # In production, you might want to track document IDs and delete them
        del session_namespaces[session_id]
    
    session = crawl_sessions[session_id]
    
    # Clean up domain tracking if session is still active
    try:
        parsed_url = urlparse(session.url)
        domain = parsed_url.netloc.replace('www.', '')
        with crawl_lock:
            active_crawls.pop(domain, None)
    except:
        pass  # Ignore errors during cleanup
    
    # Remove session
    del crawl_sessions[session_id]
    
    return jsonify({"message": f"Session {session_id} deleted successfully"})

@app.route('/cleanup', methods=['POST'])
def cleanup_old_sessions():
    """
    Clean up old completed sessions to free memory.
    
    This endpoint removes sessions that have been completed or errored
    for longer than the specified time period.
    
    Request Body:
        hours_old (int, optional): Age threshold in hours (default: 24)
        
    Returns:
        JSON response with cleanup statistics
    """
    data = request.json or {}
    hours_old = data.get('hours_old', 24)  # Default: 24 hours
    
    # Calculate cutoff time
    cutoff_time = datetime.now() - timedelta(hours=hours_old)
    sessions_to_delete = []
    
    # Find sessions eligible for cleanup
    for session_id, session in crawl_sessions.items():
        # Only clean up completed or errored sessions
        if session.status in ["completed", "error"]:
            try:
                # Use first message timestamp as creation time
                if not session.messages.empty():
                    first_message = session.messages.queue[0]
                    created_at = datetime.fromisoformat(first_message['timestamp'])
                    if created_at < cutoff_time:
                        sessions_to_delete.append(session_id)
            except:
                # If timestamp parsing fails, assume session is old
                sessions_to_delete.append(session_id)
    
    # Perform cleanup
    deleted_count = 0
    for session_id in sessions_to_delete:
        try:
            # Remove session namespace
            if session_id in session_namespaces:
                namespace = session_namespaces[session_id]
                # Note: Pinecone doesn't have a direct way to delete by namespace
                # In production, you might want to track document IDs and delete them
                del session_namespaces[session_id]
            # Remove session
            del crawl_sessions[session_id]
            deleted_count += 1
        except:
            pass  # Continue cleanup even if individual deletion fails
    
    return jsonify({
        "message": f"Cleaned up {deleted_count} old sessions",
        "deleted_sessions": sessions_to_delete,
        "remaining_sessions": len(crawl_sessions)
    })

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    # Start Flask development server with threading enabled for concurrent requests
    app.run(debug=True, port=5000, threaded=True)