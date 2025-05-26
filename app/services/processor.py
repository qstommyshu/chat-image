"""
HTML Processing Service

This module handles processing HTML content and extracting image documents
for vector database indexing.
"""

from datetime import datetime
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from langchain.schema import Document


def fix_image_paths(html_content: str, base_url: str) -> str:
    """
    Fix relative image paths in HTML content to absolute URLs.
    
    This is essential for direct memory processing since relative paths
    from crawled HTML need to be converted to absolute URLs.
    """
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


def get_image_format(url: str) -> str:
    """Get image format from URL."""
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


def extract_context(img_tag) -> str:
    """Extract context information from an img tag."""
    context_parts = []
    
    alt_text = img_tag.get('alt', '')[:500] if img_tag.get('alt') else ''
    title_text = img_tag.get('title', '')[:200] if img_tag.get('title') else ''
    class_attr = ' '.join(img_tag.get('class', []))[:300] if img_tag.get('class') else ''
    
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
            truncated_parent = parent_text[:150] + "..." if len(parent_text) > 150 else parent_text
            context_parts.append(f"Parent text: {truncated_parent}")
    
    context = " | ".join(context_parts) if context_parts else str(img_tag)[:100]
    return context[:1000] if len(context) > 1000 else context


def extract_context_from_source(source_tag) -> str:
    """Extract context information from a source tag."""
    context_parts = []
    
    media_attr = source_tag.get('media', '')[:200] if source_tag.get('media') else ''
    if media_attr:
        context_parts.append(f"Media: {media_attr}")
    
    picture = source_tag.find_parent('picture')
    if picture:
        img_in_picture = picture.find('img')
        if img_in_picture:
            alt_text = img_in_picture.get('alt', '')[:500] if img_in_picture.get('alt') else ''
            title_text = img_in_picture.get('title', '')[:200] if img_in_picture.get('title') else ''
            class_attr = ' '.join(img_in_picture.get('class', []))[:300] if img_in_picture.get('class') else ''
            
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
            truncated_parent = parent_text[:150] + "..." if len(parent_text) > 150 else parent_text
            context_parts.append(f"Parent text: {truncated_parent}")
    
    context = " | ".join(context_parts) if context_parts else str(source_tag)[:100]
    return context[:1000] if len(context) > 1000 else context


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
        docs.extend(self._process_image_element(all_imgs, 'img', base_url, source_url))
        
        # Process source tags
        docs.extend(self._process_image_element(all_sources, 'source', base_url, source_url))
        
        return docs
    
    def process_crawl_results_directly(self, crawl_result) -> list[Document]:
        """Process Firecrawl results directly without saving to disk."""
        print(f"\n🔄 Processing {len(crawl_result.data)} pages directly from crawl results")
        
        all_docs = []
        
        for i, page_data in enumerate(crawl_result.data, 1):
            url = page_data.metadata.get('url', f'page_{i}')
            print(f"Processing page {i}: {url}")
            
            # Fix relative image paths to absolute URLs
            fixed_html = fix_image_paths(page_data.rawHtml, url)
            
            # Process HTML content directly
            docs = self.process_html_content(fixed_html, url)
            all_docs.extend(docs)
            
            # Count and report image elements found
            soup = BeautifulSoup(fixed_html, 'html.parser')
            img_count = len(soup.find_all('img'))
            source_count = len(soup.find_all('source'))
            print(f"  ✔ Found {img_count} img tags, {source_count} source tags")
        
        print(f"Processed {len(all_docs)} image documents")
        return all_docs
    
    def _process_image_element(self, elements, element_type: str, base_url: str, source_url: str) -> list[Document]:
        """Generic image element processor."""
        docs = []
        
        for element in elements:
            # Get URLs based on element type
            urls = self._extract_urls_from_element(element, element_type)
            
            # Get attributes based on element type  
            attributes = self._extract_attributes_from_element(element, element_type)
            
            for url in urls:
                # Common processing logic
                absolute_url = self._make_absolute_url(url, base_url)
                img_format = get_image_format(absolute_url)
                context = extract_context(element) if element_type == 'img' else extract_context_from_source(element)
                
                # Common document creation
                doc = self._create_document(absolute_url, img_format, attributes, context, source_url, element_type)
                docs.append(doc)
        
        return docs
    
    def _extract_urls_from_element(self, element, element_type: str) -> list[str]:
        """Extract URLs based on element type."""
        if element_type == 'img':
            raw = element.get('src') or element.get('data-src') or element.get('data-lazy-src')
            return raw.split(',') if raw else []
        elif element_type == 'source':
            srcset = element.get('srcset', '')
            return srcset.split(',') if srcset else []
    
    def _extract_attributes_from_element(self, element, element_type: str) -> dict:
        """Extract attributes based on element type."""
        if element_type == 'img':
            return {
                'alt_text': element.get('alt', ''),
                'title': element.get('title', ''),
                'class': ' '.join(element.get('class', [])),
            }
        elif element_type == 'source':
            # Complex logic for source → picture → img
            picture = element.find_parent('picture')
            if picture and picture.find('img'):
                img = picture.find('img')
                return {
                    'alt_text': img.get('alt', ''),
                    'title': img.get('title', ''),
                    'class': ' '.join(img.get('class', [])),
                    'media': element.get('media', '')
                }
            return {'media': element.get('media', '')}
    
    def _make_absolute_url(self, url, base_url: str) -> str:
        """Convert relative URL to absolute URL."""
        if not url:
            return ''
        
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = base_url + url
        elif not url.startswith('http'):
            url = base_url + '/' + url.lstrip('/')
        
        return url
    

    
    def _create_document(self, absolute_url, img_format, attributes, context, source_url, element_type: str) -> Document:
        """Create a langchain document from processed element attributes."""
        # Ensure all text fields are properly limited
        alt_text_limited = attributes['alt_text'][:500] if attributes['alt_text'] else ''
        title_text_limited = attributes['title'][:200] if attributes['title'] else ''
        class_attr_limited = attributes['class'][:300] if attributes['class'] else ''
        
        page_content = f"Alt: {alt_text_limited} | Title: {title_text_limited} | Class: {class_attr_limited} | Context: {context}"
        page_content = page_content[:2000] if len(page_content) > 2000 else page_content
        
        doc = Document(
            page_content=page_content,
            metadata={
                'img_url': absolute_url[:1000] if absolute_url else '',
                'img_format': img_format,
                'alt_text': alt_text_limited,
                'title': title_text_limited,
                'class': class_attr_limited,
                'source_type': element_type,
                'source_url': source_url[:1000] if source_url else '',
                'source_page': urlparse(source_url).path[:200] if source_url else '',
                'media': attributes['media'][:200] if attributes['media'] else ''
            }
        )
        return doc 