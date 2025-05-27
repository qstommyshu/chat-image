"""
HTML Processing Utilities

This module contains utility functions for processing HTML content,
extracting image information, and handling URL transformations for
direct memory processing (no disk storage).
"""

from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup


def fix_image_paths(html_content: str, base_url: str) -> str:
    """
    Fix relative image paths in HTML content to absolute URLs.
    
    This is essential for direct memory processing since relative paths
    from crawled HTML need to be converted to absolute URLs.
    
    Args:
        html_content: Raw HTML content from crawling
        base_url: Base URL to resolve relative paths against
        
    Returns:
        HTML content with absolute image URLs
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
    """
    Get image format from URL.
    
    Args:
        url: Image URL to analyze
        
    Returns:
        Image format string (jpg, png, svg, webp, gif, unknown)
    """
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


def extract_context_from_source(source_tag) -> dict:
    """
    Extract context information from a source tag.
    
    Args:
        source_tag: BeautifulSoup source tag element
        
    Returns:
        Dict with individual fields and formatted context string
    """
    context_parts = []
    
    media_attr = source_tag.get('media', '')[:200] if source_tag.get('media') else ''
    if media_attr:
        context_parts.append(f"Media: {media_attr}")
    
    alt_text = ''
    title_text = ''
    class_attr = ''
    
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
    context = context[:1000] if len(context) > 1000 else context
    
    return {
        'alt_text': alt_text,
        'title_text': title_text,
        'class_attr': class_attr,
        'media_attr': media_attr,
        'context': context
    }


def extract_context(img_tag) -> dict:
    """
    Extract context information from an img tag.
    
    Args:
        img_tag: BeautifulSoup img tag element
        
    Returns:
        Dict with individual fields and formatted context string
    """
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
    context = context[:1000] if len(context) > 1000 else context
    
    return {
        'alt_text': alt_text,
        'title_text': title_text,
        'class_attr': class_attr,
        'context': context
    }

 