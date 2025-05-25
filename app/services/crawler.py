"""
Crawler service for website crawling functionality.

This module handles the actual crawling of websites, HTML processing, and
storage of crawled content.
"""
import os
import glob
import threading
from bs4 import BeautifulSoup
from firecrawl import ScrapeOptions

from app.config import DEFAULT_WAIT_TIME
from app.utils.helpers import count_media_tags, generate_crawl_summary, create_unique_folder_name
from app.models.session import CrawlSession

# Import combined functionality
from combined import (
    load_html_folder,
    OpenAIEmbeddings,
    Chroma,
    openai_api_key,
    firecrawl_app,
    fix_image_paths,
    url_to_filename
)

# Global state
crawl_sessions = {}
vector_stores = {}
crawl_lock = threading.Lock()
active_crawls = {}


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
            waitFor=DEFAULT_WAIT_TIME,     # Wait for lazy loading
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
        img_count, source_count = count_media_tags(fixed_html)
        print(f"    Contains {img_count} img tags, {source_count} source tags")
    
    print(f"\n✔ All pages saved to {folder_name} folder")
    return folder_name


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
        from app.utils.helpers import get_domain_from_url
        domain = get_domain_from_url(session.url)
        unique_folder = create_unique_folder_name(domain, session.session_id)
        
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
        
        # Phase 3: Vector Database Creation
        session.status = "indexing"
        session.add_message("status", {
            "status": "indexing", 
            "message": "Creating vector database for image search"
        })
        
        # Create embeddings and vector database for semantic search
        embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        chroma_db = Chroma.from_documents(
            all_docs,
            embedding=embeddings,
            collection_name=f'crawl_{session.session_id}'  # Unique collection per session
        )
        
        # Store the vector database for later search operations
        vector_stores[session.session_id] = chroma_db
        
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