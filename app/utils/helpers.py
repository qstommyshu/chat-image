"""
Helper utilities for the web crawler and image search application.

This module contains utility functions for formatting search results, 
generating summaries, and other helper operations.
"""
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def generate_crawl_summary(session):
    """
    Generate a human-readable summary of crawl results.
    
    This creates a summary message that will be sent to the client
    when crawling completes, describing what was found.
    
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


def get_domain_from_url(url):
    """
    Extract the normalized domain from a URL.
    
    Args:
        url (str): The URL to parse
        
    Returns:
        str: The normalized domain (without www prefix)
    """
    try:
        parsed_url = urlparse(url)
        return parsed_url.netloc.replace('www.', '')
    except:
        return None


def create_unique_folder_name(domain, session_id):
    """
    Create a unique folder name for crawled pages based on domain and session ID.
    
    Args:
        domain (str): The domain being crawled
        session_id (str): The session ID
        
    Returns:
        str: A unique folder name
    """
    base_folder = f"crawled_pages_{domain.replace('.', '_')}"
    return f"{base_folder}_{session_id[:8]}"


def count_media_tags(html):
    """
    Count the number of media tags in HTML content.
    
    Args:
        html (str): HTML content to analyze
        
    Returns:
        tuple: A tuple of (img_count, source_count)
    """
    soup = BeautifulSoup(html, 'html.parser')
    img_count = len(soup.find_all('img'))
    source_count = len(soup.find_all('source'))
    return img_count, source_count 