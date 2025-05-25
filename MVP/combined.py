"""
Combined Crawler and Conversational Image Search
Crawls a website and provides a chat interface to search for images
"""
import os
import glob
import json
import re
import sys
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from firecrawl import FirecrawlApp, ScrapeOptions
import requests

# Load environment variables
load_dotenv()

# Check required API keys
openai_api_key = os.getenv("OPENAI_API_KEY")
firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")

if not openai_api_key:
    raise ValueError("Please set OPENAI_API_KEY in your .env file")
if not firecrawl_api_key:
    raise ValueError("Please set FIRECRAWL_API_KEY in your .env file")

# Initialize clients
openai_client = OpenAI(api_key=openai_api_key)
firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)

# ========== Crawling Functions ==========

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

def crawl_website(start_url, limit=10):
    """Crawl website and save HTML files"""
    # Create folder based on domain
    parsed_url = urlparse(start_url)
    domain = parsed_url.netloc.replace('www.', '')
    folder_name = f"crawled_pages_{domain.replace('.', '_')}"
    
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
    
    saved_files = []
    
    for i, page_data in enumerate(crawl_result.data, 1):
        url = page_data.metadata.get('url', f'page_{i}')
        print(f"Saving page {i}: {url}")
        
        filename = url_to_filename(url)
        filepath = os.path.join(folder_name, filename)
        
        fixed_html = fix_image_paths(page_data.rawHtml, url)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_html)
        
        saved_files.append((url, filename))
        print(f"  ✔ Saved as: {filepath}")
        
        soup = BeautifulSoup(fixed_html, 'html.parser')
        img_count = len(soup.find_all('img'))
        source_count = len(soup.find_all('source'))
        print(f"    Contains {img_count} img tags, {source_count} source tags")
    
    print(f"\n✔ All pages saved to {folder_name} folder")
    return folder_name

# ========== Image Extraction and Search Functions ==========

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
    
    media_attr = source_tag.get('media', '')
    if media_attr:
        context_parts.append(f"Media: {media_attr}")
    
    picture = source_tag.find_parent('picture')
    if picture:
        img_in_picture = picture.find('img')
        if img_in_picture:
            alt_text = img_in_picture.get('alt', '')
            title_text = img_in_picture.get('title', '')
            class_attr = ' '.join(img_in_picture.get('class', []))
            
            if alt_text:
                context_parts.append(f"Alt: {alt_text}")
            if title_text:
                context_parts.append(f"Title: {title_text}")
            if class_attr:
                context_parts.append(f"Class: {class_attr}")
    
    parent = source_tag.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        if parent_text and len(parent_text) < 300:
            context_parts.append(f"Parent text: {parent_text}")
    
    return " | ".join(context_parts) if context_parts else str(source_tag)

def extract_context(img_tag):
    """Extract context from img tag"""
    context_parts = []
    
    alt_text = img_tag.get('alt', '')
    title_text = img_tag.get('title', '')
    class_attr = ' '.join(img_tag.get('class', []))
    
    if alt_text:
        context_parts.append(f"Alt: {alt_text}")
    if title_text:
        context_parts.append(f"Title: {title_text}")
    if class_attr:
        context_parts.append(f"Class: {class_attr}")
    
    parent = img_tag.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        if parent_text and len(parent_text) < 200:
            context_parts.append(f"Parent text: {parent_text}")
    
    return " | ".join(context_parts) if context_parts else str(img_tag)

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
            
            doc = Document(
                page_content=f"Alt: {alt_text} | Title: {title_text} | Class: {class_attr} | Context: {context}",
                metadata={
                    'img_url': u,
                    'img_format': img_format,
                    'alt_text': alt_text,
                    'title': title_text,
                    'class': class_attr,
                    'source_type': 'img',
                    'source_url': source_url,
                    'source_file': os.path.basename(html_file_path)
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
            
            doc = Document(
                page_content=f"Alt: {alt_text} | Title: {title_text} | Class: {class_attr} | Context: {context}",
                metadata={
                    'img_url': url_part,
                    'img_format': img_format,
                    'alt_text': alt_text,
                    'title': title_text,
                    'class': class_attr,
                    'source_type': 'source',
                    'media': source.get('media', ''),
                    'source_url': source_url,
                    'source_file': os.path.basename(html_file_path)
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

def search_images_with_dedup(chroma_db, query, format_filter=None, max_results=5):
    """Search images with deduplication"""
    results = chroma_db.similarity_search_with_score(query, k=50)
    
    processed_results = []
    
    for doc, score in results:
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
        import re
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

def format_search_results_with_ai(search_results, user_query):
    """Format search results with AI"""
    
    if not search_results:
        return "Sorry, I couldn't find any relevant images."
    
    results_data = []
    for i, img in enumerate(search_results, 1):
        results_data.append({
            "index": i,
            "alt_text": img['alt_text'],
            "format": img['format'].upper(),
            "url": img['url'],
            "source_url": img['source_url']
        })
    
    system_prompt = """You are an image search assistant. The user searched for images, and you need to present the results in a friendly way.

Requirements:
1. Use concise, friendly language to describe what was found
2. For each image, only show: Image URL and Source page
3. Format should be clear and easy to read
4. Don't show technical details like alt_text

Example format:
I found 3 relevant images for you:

🖼️ Image 1:
Image link: https://...
Source page: https://...

🖼️ Image 2:
Image link: https://...
Source page: https://..."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User search: {user_query}\n\nSearch results: {json.dumps(results_data, ensure_ascii=False, indent=2)}"}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI formatting error: {e}")
        result = f"Found {len(search_results)} relevant images:\n\n"
        for i, img in enumerate(search_results, 1):
            result += f"🖼️ Image {i}:\n"
            result += f"Image link: {img['url']}\n"
            result += f"Source page: {img['source_url']}\n\n"
        return result

def conversational_search(chroma_db):
    """Run conversational search interface"""
    print("\n🤖 AI Image Search Assistant is ready!")
    print("💬 You can describe what images you want in natural language, for example:")
    print("   - 'I want to see iPad images'")
    print("   - 'Do you have JPG photos of Apple Pencil?'")
    print("   - 'Find me some iPhone camera pictures'")
    print("   - 'Apple Watch PNG images'")
    print("\nType 'quit' to exit")
    
    while True:
        print("\n" + "="*50)
        user_input = input("👤 You: ").strip()
        
        if user_input.lower() in ['quit', 'exit']:
            print("🤖 Assistant: Goodbye! Thanks for using the image search service!")
            break
        
        if not user_input:
            print("🤖 Assistant: Please tell me what kind of images you're looking for?")
            continue
        
        print("🤖 Assistant: Let me search for you...")
        
        parsed_query = parse_user_query_with_ai(user_input)
        
        print(f"🔍 {parsed_query['response_message']}")
        
        search_results = search_images_with_dedup(
            chroma_db, 
            parsed_query['search_query'],
            format_filter=parsed_query['format_filter'],
            max_results=5
        )
        
        formatted_response = format_search_results_with_ai(search_results, user_input)
        print(f"\n🤖 Assistant: {formatted_response}")

def main():
    """Main function"""
    print("🎯 Combined Website Crawler and Image Search System")
    print("="*50)
    
    # Get URL from command line or user input
    if len(sys.argv) > 1:
        start_url = sys.argv[1]
    else:
        start_url = input("Enter the URL to crawl (e.g., https://www.apple.com/iphone): ").strip()
    
    if not start_url:
        print("❌ Error: Please provide a valid URL")
        return
    
    # Get crawl limit
    try:
        if len(sys.argv) > 2:
            limit = int(sys.argv[2])
        else:
            limit_input = input("How many pages to crawl? (default: 10): ").strip()
            limit = int(limit_input) if limit_input else 10
    except ValueError:
        limit = 10
    
    # Step 1: Crawl website
    try:
        folder_name = crawl_website(start_url, limit)
    except Exception as e:
        print(f"❌ Crawling error: {e}")
        return
    
    # Step 2: Load and process HTML files
    print("\n📊 Creating vector database...")
    try:
        all_docs = load_html_folder(folder_name)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return
    
    if not all_docs:
        print("❌ No image documents found!")
        return
    
    # Step 3: Create vector store
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    chroma_db = Chroma.from_documents(
        all_docs,
        embedding=embeddings,
        collection_name='combined_image_search'
    )
    
    print("✅ System initialization complete!")
    
    # Step 4: Start conversational search
    conversational_search(chroma_db)

if __name__ == "__main__":
    main() 