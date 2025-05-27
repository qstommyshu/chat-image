"""
Crawler Service

This module handles website crawling operations and background processing
using Firecrawl and manages the complete crawl workflow.
"""

import threading
import logging
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlparse
from firecrawl import ScrapeOptions

from app.config import clients
from app.models.session import session_manager, CrawlSession
from app.services.processor import HTMLProcessor
from app.services.cache import cache_service

# Set up crawler-specific logger
crawler_logger = logging.getLogger('crawler')
crawler_logger.setLevel(logging.INFO)

# Create console handler if it doesn't exist
if not crawler_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    crawler_logger.addHandler(console_handler)


class CrawlerService:
    """Service class for managing website crawling operations."""
    
    def __init__(self):
        self.html_processor = HTMLProcessor()
        self.cache_service = cache_service
    
    def start_crawl(self, session: CrawlSession) -> None:
        """
        Start a background crawl operation for the given session.
        
        Args:
            session: The CrawlSession to process
        """
        thread = threading.Thread(target=self._perform_crawl, args=(session,))
        thread.daemon = True  # Allow server shutdown even if thread is running
        thread.start()
    
    async def check_html_cache(self, url: str, limit: int = 1) -> Optional[Dict]:
        """
        Check if the URL's HTML content is available in the cache.
        
        Args:
            url: URL to check in cache
            limit: Maximum number of pages crawled (affects cache key)
            
        Returns:
            Cached HTML content or None if not found
        """
        return await self.cache_service.get_html_cache(url, limit)
    
    async def store_html_cache(self, url: str, html_content: str, page_data: Dict, limit: int = 1) -> bool:
        """
        Store HTML content in the cache.
        
        Args:
            url: URL being cached
            html_content: Raw HTML content
            page_data: Additional page metadata
            limit: Maximum number of pages crawled (affects cache key)
            
        Returns:
            True if caching was successful
        """
        # Create cache entry with relevant metadata
        cache_entry = {
            "url": url,
            "html_content": html_content,
            "crawl_timestamp": datetime.now().isoformat(),
            "page_type": self._detect_page_type(url),
            "firecrawl_metadata": page_data
        }
        
        # Set dynamic TTL based on page type
        page_type = cache_entry["page_type"]
        ttl = 7 * 24 * 60 * 60 if page_type == "static" else 24 * 60 * 60
        
        return await self.cache_service.set_html_cache(url, cache_entry, limit, ttl)
    
    def _detect_page_type(self, url: str) -> str:
        """
        Detect if a URL is likely to be static or dynamic content.
        
        Args:
            url: URL to analyze
            
        Returns:
            "static" or "dynamic"
        """
        # Simple heuristics for detecting page type
        dynamic_indicators = [
            "news", "blog", "article", "post",
            "rss", "feed", "update", "latest"
        ]
        
        # Check URL for dynamic indicators
        url_lower = url.lower()
        if any(indicator in url_lower for indicator in dynamic_indicators):
            return "dynamic"
        
        # Check for date patterns in URL (common in news/blogs)
        if any(str(year) in url for year in range(2020, datetime.now().year + 1)):
            return "dynamic"
        
        # Default to static for most corporate/product pages
        return "static"
    
    def _perform_crawl(self, session: CrawlSession) -> None:
        """
        Execute the complete crawling workflow in a background thread.
        
        This function handles the entire crawl lifecycle:
        1. Website crawling using Firecrawl or cache retrieval
        2. Direct HTML processing and image extraction (no disk storage)
        3. Vector database indexing for search with session isolation
        4. Status updates via SSE
        
        Each session gets its own isolated namespace, allowing multiple users
        to crawl the same domain simultaneously without conflicts.
        
        Args:
            session: The CrawlSession to process
        """
        domain = None
        try:
            # Phase 1: Website Crawling or Cache Retrieval
            session.status = "crawling"
            session.add_message("status", {
                "status": "crawling", 
                "message": f"Starting to crawl {session.url}"
            })
            
            # Get domain for tracking
            parsed_url = urlparse(session.url)
            domain = parsed_url.netloc.replace('www.', '')
            
            # Check cache for existing content if cache is enabled
            cache_hit = False
            cached_html = None
            
            if self.cache_service.is_available() and not session.skip_cache:
                # Async operation requires proper handling in threaded context
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    cached_html = loop.run_until_complete(self.cache_service.get_html_cache(session.url, session.limit))
                    
                    if cached_html:
                        cache_hit = True
                        cache_info = cached_html.get("_cache", {})
                        
                        # Log cache hit for server logs
                        crawler_logger.info(
                            f"CRAWLER CACHE HIT for {session.url} - "
                            f"Age: {cache_info.get('cache_age', 'unknown')}"
                        )
                        
                        session.add_message("progress", {
                            "message": f"Cache hit! Using cached content from {cache_info.get('cache_age', 'previous crawl')}",
                            "cache_hit": True,
                            "cache_info": cache_info
                        })
                finally:
                    loop.close()
            
            if cache_hit:
                # Use cached content
                crawler_logger.info(f"🔄 Using cached content for {session.url} - skipping firecrawl")
                
                # Extract data from cache
                html_content = cached_html.get("html_content", "")
                firecrawl_metadata = cached_html.get("firecrawl_metadata", {})
                
                # Create a mock crawl result with the cached data that matches FirecrawlDocument interface
                from types import SimpleNamespace
                
                # Create a mock page object that matches the interface expected by HTMLProcessor
                mock_page = SimpleNamespace()
                mock_page.rawHtml = html_content
                mock_page.metadata = {
                    "url": session.url,
                    **firecrawl_metadata
                }
                
                crawl_result = SimpleNamespace()
                crawl_result.data = [mock_page]
                
                session.total_pages = 1
                session.cache_hits = 1
                cache_age = cached_html.get("_cache", {}).get("cache_age", "unknown")
                
                session.add_message("progress", {
                    "message": f"Using cached content - {cache_age} old",
                    "cache_hit": True
                })
                
                crawler_logger.info(
                    f"Cache content utilized successfully for {session.url} - "
                    f"Age: {cache_age} old"
                )
            else:
                # Execute the crawl directly using Firecrawl
                crawler_logger.info(f"🕷️ Starting fresh crawl for {session.url} (limit: {session.limit} pages) - no cache hit")
                print(f"\n🕷️ Starting to crawl {session.url} (limit: {session.limit} pages)...")
                
                crawl_result = clients.firecrawl_app.crawl_url(
                    session.url,
                    limit=session.limit,
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
                
                # Create crawl success message with cache info if applicable
                crawl_message = f"Successfully crawled {len(crawl_result.data)} pages"
                if cache_hit:
                    cache_age = cached_html.get("_cache", {}).get("cache_age", "unknown")
                    crawl_message += f" 🚀 (Cache hit! Content was {cache_age} old)"
                
                print(f"✅ {crawl_message}")
                session.total_pages = len(crawl_result.data)
                
                session.add_message("progress", {
                    "message": crawl_message,
                    "cache_hit": cache_hit if cache_hit else None
                })
                
                # Cache the HTML content if cache is available
                if self.cache_service.is_available() and len(crawl_result.data) > 0:
                    # Set up async event loop
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        # Cache each page's HTML content
                        for page in crawl_result.data:
                            try:
                                # Access FirecrawlDocument attributes properly
                                # Based on HTMLProcessor usage: page.metadata.get('url') and page.rawHtml
                                url = None
                                html = ""
                                
                                if hasattr(page, 'metadata') and page.metadata:
                                    url = page.metadata.get('url', None)
                                
                                if hasattr(page, 'rawHtml'):
                                    html = page.rawHtml or ""
                                
                                if url and html:
                                    # Create page metadata from FirecrawlDocument attributes
                                    page_data = {}
                                    
                                    # Extract metadata from the FirecrawlDocument
                                    if hasattr(page, 'metadata') and page.metadata:
                                        for key, value in page.metadata.items():
                                            if key not in ['rawHtml'] and value is not None:
                                                page_data[key] = value
                                    
                                    success = loop.run_until_complete(
                                        self.store_html_cache(url, html, page_data, session.limit)
                                    )
                                    
                                    if success:
                                        crawler_logger.info(f"📦 HTML content cached for {url}")
                                        print(f"📦 Cached HTML content for {url}")
                                    else:
                                        crawler_logger.warning(f"Failed to cache HTML content for {url}")
                                        
                            except Exception as page_error:
                                crawler_logger.error(f"Error caching page content: {page_error}")
                                crawler_logger.debug(f"Page object type: {type(page)}")
                                crawler_logger.debug(f"Page attributes: {dir(page) if hasattr(page, '__dict__') else 'No attributes'}")
                                # Continue with next page instead of failing the entire crawl
                    finally:
                        loop.close()
            
            # Phase 2: Direct Image Processing (no disk I/O)
            session.status = "processing"
            session.add_message("status", {
                "status": "processing", 
                "message": "Extracting images directly from crawled content"
            })
            
            # Process crawl results directly without saving to disk
            all_docs = self.html_processor.process_crawl_results_directly(crawl_result)
            session.total_images = len(all_docs)
            
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
            
            # Add cache info to the stats if applicable
            if cache_hit:
                session.image_stats["cache"] = {
                    "hit": True,
                    "cache_age": cached_html.get("_cache", {}).get("cache_age", "unknown")
                }
            
            session.add_message("progress", {
                "message": f"Processed {session.total_images} images from {session.total_pages} pages (no disk storage needed)",
                "stats": session.image_stats,
                "cache_hit": cache_hit if cache_hit else None
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
                # Add cache info to metadata if applicable
                if cache_hit:
                    doc.metadata['cache_hit'] = True
                    doc.metadata['cache_age'] = cached_html.get("_cache", {}).get("cache_age", "unknown")
            
            # Add documents to Pinecone in batches to avoid size limits
            self._index_documents_in_batches(all_docs, namespace, session)
            
            # Store the namespace for later search operations
            session_manager.set_namespace(session.session_id, namespace)
            
            # Phase 4: Completion
            summary = self._generate_crawl_summary(session)
            
            # Print final completion message with cache info
            completion_msg = f"Crawling completed! Found {session.total_images} images across {session.total_pages} pages"
            if hasattr(session, 'cache_hits') and session.cache_hits > 0:
                cache_age = session.image_stats.get('cache', {}).get('cache_age', 'unknown')
                completion_msg += f" 🚀 (Cache hit! Content was {cache_age} old)"
            
            print(f"✅ {completion_msg}")
            crawler_logger.info(f"CRAWL COMPLETED - {completion_msg}")
            
            session.status = "completed"
            session.completed = True
            session.add_message("completed", {
                "status": "completed",
                "summary": summary,
                "completion_message": completion_msg,  # Add the formatted completion message
                "total_images": session.total_images,
                "total_pages": session.total_pages,
                "stats": session.image_stats,
                "cache_hit": cache_hit if cache_hit else None
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
            # Cleanup complete - session isolation means no domain tracking needed
            pass
    
    def _index_documents_in_batches(self, all_docs: list, namespace: str, session: CrawlSession) -> None:
        """Index documents in Pinecone in batches to avoid size limits."""
        batch_size = 100  # Process 100 documents at a time
        total_docs = len(all_docs)
        
        for i in range(0, total_docs, batch_size):
            batch = all_docs[i:i + batch_size]
            try:
                print(f"Uploading batch {i//batch_size + 1}/{(total_docs + batch_size - 1)//batch_size} ({len(batch)} documents)")
                clients.vector_store.add_documents(batch, namespace=namespace)
                
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
    
    def _generate_crawl_summary(self, session: CrawlSession) -> str:
        """
        Generate a human-readable summary of crawl results.
        
        Args:
            session: The completed crawl session
            
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
        if hasattr(session, 'cache_hits') and session.cache_hits > 0:
            # Include cache hit information in summary
            cache_age = session.image_stats.get('cache', {}).get('cache_age', 'unknown')
            summary = f"✅ Successfully crawled {session.url} and found {session.total_images} images across {session.total_pages} pages"
            summary += f" 🚀 (Cache hit! Content was {cache_age} old). "
        else:
            summary = f"I've successfully crawled {session.url} and found {session.total_images} images across {session.total_pages} pages. "
            
        summary += f"The images include {formats_str}. "
        summary += f"Main pages include: {pages_str}. "
        summary += "You can now search for specific images by describing what you're looking for!"
        
        return summary 