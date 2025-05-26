"""
Crawler Service

This module handles website crawling operations and background processing
using Firecrawl and manages the complete crawl workflow.
"""

import threading
from datetime import datetime
from urllib.parse import urlparse
from firecrawl import ScrapeOptions

from app.config import clients
from app.models.session import session_manager, CrawlSession
from app.services.processor import HTMLProcessor


class CrawlerService:
    """Service class for managing website crawling operations."""
    
    def __init__(self):
        self.html_processor = HTMLProcessor()
    
    def start_crawl(self, session: CrawlSession) -> None:
        """
        Start a background crawl operation for the given session.
        
        Args:
            session: The CrawlSession to process
        """
        thread = threading.Thread(target=self._perform_crawl, args=(session,))
        thread.daemon = True  # Allow server shutdown even if thread is running
        thread.start()
    
    def _perform_crawl(self, session: CrawlSession) -> None:
        """
        Execute the complete crawling workflow in a background thread.
        
        This function handles the entire crawl lifecycle:
        1. Website crawling using Firecrawl
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
            # Phase 1: Website Crawling
            session.status = "crawling"
            session.add_message("status", {
                "status": "crawling", 
                "message": f"Starting to crawl {session.url}"
            })
            
            # Get domain for tracking
            parsed_url = urlparse(session.url)
            domain = parsed_url.netloc.replace('www.', '')
            
            # Execute the crawl directly using Firecrawl
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
            
            print(f"✅ Successfully crawled {len(crawl_result.data)} pages")
            session.total_pages = len(crawl_result.data)
            
            session.add_message("progress", {
                "message": f"Successfully crawled {session.total_pages} pages"
            })
            
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
            
            session.add_message("progress", {
                "message": f"Processed {session.total_images} images from {session.total_pages} pages (no disk storage needed)",
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
            self._index_documents_in_batches(all_docs, namespace, session)
            
            # Store the namespace for later search operations
            session_manager.set_namespace(session.session_id, namespace)
            
            # Phase 4: Completion
            summary = self._generate_crawl_summary(session)
            
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
        summary = f"I've successfully crawled {session.url} and found {session.total_images} images across {session.total_pages} pages. "
        summary += f"The images include {formats_str}. "
        summary += f"Main pages include: {pages_str}. "
        summary += "You can now search for specific images by describing what you're looking for!"
        
        return summary 