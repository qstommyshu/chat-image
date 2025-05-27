"""
HTML Processing Service

This module handles processing HTML content and extracting image documents
for vector database indexing.
"""


from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from langchain.schema import Document

from app.utils.html_utils import (
    fix_image_paths, get_image_format, extract_context, 
    extract_context_from_source
)


class HTMLProcessor:
    """Service class for processing HTML content and extracting image documents."""
    
    def process_html_content(self, html_content: str, source_url: str) -> list[Document]:
        """Process HTML content directly and return document list."""
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        parsed_url = urlparse(source_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        docs = []
        all_imgs = soup.find_all('img')
        all_sources = soup.find_all('source')
        
        # Process img tags
        docs.extend(self._process_img_tags(all_imgs, base_url, source_url))
        
        # Process source tags
        docs.extend(self._process_source_tags(all_sources, base_url, source_url))
        
        return docs
    
    def process_crawl_results_directly(self, crawl_result) -> list[Document]:
        """Process Firecrawl results directly without saving to disk."""
        print(f"\n🔄 Processing {len(crawl_result.data)} pages directly from crawl results")
        
        all_docs = []
        
        for i, page_data in enumerate(crawl_result.data, 1):
            try:
                # Handle both FirecrawlDocument objects and mock objects with defensive coding
                url = None
                html_content = None
                
                # Try to get URL - handle both attribute access and dict access
                if hasattr(page_data, 'metadata') and page_data.metadata:
                    url = page_data.metadata.get('url', f'page_{i}')
                elif isinstance(page_data, dict) and 'url' in page_data:
                    url = page_data.get('url', f'page_{i}')
                else:
                    url = f'page_{i}'
                
                # Try to get HTML content - handle both attribute access and dict access
                if hasattr(page_data, 'rawHtml'):
                    html_content = page_data.rawHtml
                elif isinstance(page_data, dict) and 'rawHtml' in page_data:
                    html_content = page_data.get('rawHtml', '')
                else:
                    print(f"  ⚠ Warning: No HTML content found for page {i}")
                    continue
                
                print(f"Processing page {i}: {url}")
                
                # Fix relative image paths to absolute URLs
                fixed_html = fix_image_paths(html_content, url)
                
                # Process HTML content directly
                docs = self.process_html_content(fixed_html, url)
                all_docs.extend(docs)
                
                # Count and report image elements found
                soup = BeautifulSoup(fixed_html, 'html.parser')
                img_count = len(soup.find_all('img'))
                source_count = len(soup.find_all('source'))
                print(f"  ✔ Found {img_count} img tags, {source_count} source tags")
                
            except Exception as e:
                print(f"  ⚠ Error processing page {i}: {e}")
                print(f"  Page data type: {type(page_data)}")
                # Continue with next page instead of failing entire processing
                continue
        
        print(f"Processed {len(all_docs)} image documents")
        return all_docs
    
    def _process_img_tags(self, img_tags, base_url: str, source_url: str) -> list[Document]:
        """Process img tags and create documents."""
        docs = []
        
        for img in img_tags:
            raw = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-srcset')
            if not raw:
                continue
            
            for part in raw.split(','):
                u = part.strip().split(' ')[0]
                if u.startswith('//'):
                    u = 'https:' + u
                elif u.startswith('/'):
                    u = base_url + u
                elif not u.startswith('http'):
                    u = base_url + '/' + u.lstrip('/')
                
                img_format = get_image_format(u)
                extracted_data = extract_context(img)
                
                page_content = f"Alt: {extracted_data['alt_text']} | Title: {extracted_data['title_text']} | Class: {extracted_data['class_attr']} | Context: {extracted_data['context']}"
                page_content = page_content[:2000] if len(page_content) > 2000 else page_content
                
                doc = Document(
                    page_content=page_content,
                    metadata={
                        'img_url': u[:1000] if u else '',
                        'img_format': img_format,
                        'alt_text': extracted_data['alt_text'],
                        'title': extracted_data['title_text'],
                        'class': extracted_data['class_attr'],
                        'source_type': 'img',
                        'source_url': source_url[:1000] if source_url else '',
                        'source_page': urlparse(source_url).path[:200] if source_url else ''
                    }
                )
                docs.append(doc)
        
        return docs
    
    def _process_source_tags(self, source_tags, base_url: str, source_url: str) -> list[Document]:
        """Process source tags and create documents."""
        docs = []
        
        for source in source_tags:
            srcset = source.get('srcset', '')
            if not srcset:
                continue
            
            for part in srcset.split(','):
                url_part = part.strip().split(' ')[0]
                if url_part.startswith('/'):
                    url_part = base_url + url_part
                elif not url_part.startswith('http'):
                    url_part = base_url + '/' + url_part.lstrip('/')
                
                img_format = get_image_format(url_part)
                extracted_data = extract_context_from_source(source)
                
                page_content = f"Alt: {extracted_data['alt_text']} | Title: {extracted_data['title_text']} | Class: {extracted_data['class_attr']} | Context: {extracted_data['context']}"
                page_content = page_content[:2000] if len(page_content) > 2000 else page_content
                
                doc = Document(
                    page_content=page_content,
                    metadata={
                        'img_url': url_part[:1000] if url_part else '',
                        'img_format': img_format,
                        'alt_text': extracted_data['alt_text'],
                        'title': extracted_data['title_text'],
                        'class': extracted_data['class_attr'],
                        'source_type': 'source',
                        'media': extracted_data['media_attr'],
                        'source_url': source_url[:1000] if source_url else '',
                        'source_page': urlparse(source_url).path[:200] if source_url else ''
                    }
                )
                docs.append(doc)
        
        return docs 