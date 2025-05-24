"""
对话式图片搜索脚本
用户可以用自然语言查询，AI助手帮助找到相关图片
"""
import os
import glob
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI

# 载入环境变量
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("请设置环境变量 OPENAI_API_KEY")

# 初始化OpenAI客户端
client = OpenAI(api_key=openai_api_key)

def filename_to_url(filename):
    """将文件名转换回原始URL"""
    name_without_ext = filename.replace('.html', '')
    url_path = name_without_ext.replace('_', '/')
    
    if url_path.startswith('www.'):
        return f"https://{url_path}"
    else:
        return f"https://{url_path}"

def get_image_format(url):
    """获取图片格式"""
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
    """从source标签提取上下文信息"""
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
    """提取图片的上下文信息"""
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
    """处理单个HTML文件，返回文档列表"""
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
    
    # 处理img标签
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
    
    # 处理source标签
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
    """加载文件夹中的所有HTML文件"""
    print(f"加载HTML文件夹: {folder_path}")
    
    if not os.path.exists(folder_path):
        raise ValueError(f"文件夹不存在: {folder_path}")
    
    html_pattern = os.path.join(folder_path, "*.html")
    html_files = glob.glob(html_pattern)
    
    if not html_files:
        raise ValueError(f"在文件夹中没有找到HTML文件: {folder_path}")
    
    print(f"找到 {len(html_files)} 个HTML文件")
    
    all_docs = []
    
    for html_file in html_files:
        filename = os.path.basename(html_file)
        source_url = filename_to_url(filename)
        docs = process_html_file(html_file, source_url)
        all_docs.extend(docs)
    
    print(f"总共处理了 {len(all_docs)} 个图片文档")
    return all_docs

def search_images_with_dedup(chroma_db, query, format_filter=None, max_results=5):
    """搜索图片并去重"""
    # 执行搜索
    results = chroma_db.similarity_search_with_score(query, k=50)
    
    processed_results = []
    
    for doc, score in results:
        img_format = doc.metadata['img_format']
        
        # 应用格式过滤
        if format_filter and img_format not in format_filter:
            continue
        
        # 计算Alt文本匹配度
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
    
    # 去重逻辑
    def normalize_alt_text(alt_text):
        if not alt_text:
            return ""
        import re
        normalized = alt_text.lower().strip()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def should_prefer_by_alt(img1, img2):
        # JPG > PNG > 其他
        if img1['format'] != img2['format']:
            format_priority = {'jpg': 3, 'png': 2, 'webp': 1, 'svg': 0}
            priority1 = format_priority.get(img1['format'], 0)
            priority2 = format_priority.get(img2['format'], 0)
            if priority1 != priority2:
                return priority1 > priority2
        
        # Alt匹配度优先
        if img1['alt_match_score'] != img2['alt_match_score']:
            return img1['alt_match_score'] > img2['alt_match_score']
        
        # 相似度分数
        return img1['score'] < img2['score']
    
    # Alt文本去重
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
    
    # 排序
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
    """使用AI解析用户查询，提取搜索词和格式要求"""
    
    system_prompt = """你是一个图片搜索助手。用户会用自然语言描述他们想要的图片，你需要提取关键的搜索信息。

请分析用户的查询，返回JSON格式的响应，包含：
1. search_query: 用于搜索的关键词（英文，适合图片Alt文本搜索）
2. format_filter: 图片格式要求（如果用户指定了JPG、PNG等格式，否则为null）
3. response_message: 给用户的友好回复，说明你理解了什么

示例：
用户："我想要iPad相关的JPG图片"
返回：{"search_query": "iPad", "format_filter": ["jpg"], "response_message": "我来帮你找iPad相关的JPG格式图片"}

用户："给我看看苹果铅笔的照片"
返回：{"search_query": "Apple Pencil", "format_filter": null, "response_message": "我来为你搜索Apple Pencil的图片"}

用户："有没有iPhone摄像头的PNG图片？"
返回：{"search_query": "iPhone camera", "format_filter": ["png"], "response_message": "我来查找iPhone摄像头的PNG格式图片"}

只返回JSON，不要其他内容。"""

    try:
        response = client.chat.completions.create(
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
        print(f"AI解析错误: {e}")
        # 默认处理
        return {
            "search_query": user_message,
            "format_filter": None,
            "response_message": f"我来为你搜索关于 '{user_message}' 的图片"
        }

def format_search_results_with_ai(search_results, user_query):
    """使用AI格式化搜索结果"""
    
    if not search_results:
        return "抱歉，没有找到相关的图片。"
    
    # 准备搜索结果数据
    results_data = []
    for i, img in enumerate(search_results, 1):
        results_data.append({
            "index": i,
            "alt_text": img['alt_text'],
            "format": img['format'].upper(),
            "url": img['url'],
            "source_url": img['source_url']
        })
    
    system_prompt = """你是一个图片搜索助手。用户搜索了图片，你需要用友好的语言介绍搜索结果。

要求：
1. 用简洁友好的语言介绍找到了什么
2. 对每张图片，只显示：图片URL 和 来源页面
3. 格式要清晰易读
4. 不要显示技术细节如alt_text等

示例格式：
我为你找到了3张相关图片：

🖼️ 图片1：
图片链接：https://...
来源页面：https://...

🖼️ 图片2：
图片链接：https://...
来源页面：https://...
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"用户搜索：{user_query}\n\n搜索结果：{json.dumps(results_data, ensure_ascii=False, indent=2)}"}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI格式化错误: {e}")
        # 默认格式化
        result = f"找到了{len(search_results)}张相关图片：\n\n"
        for i, img in enumerate(search_results, 1):
            result += f"🖼️ 图片{i}：\n"
            result += f"图片链接：{img['url']}\n"
            result += f"来源页面：{img['source_url']}\n\n"
        return result

def main():
    # 配置文件夹路径
    crawled_folder = "crawled_pages_apple"
    
    print("🚀 正在初始化对话式图片搜索系统...")
    
    # 加载HTML文件
    try:
        all_docs = load_html_folder(crawled_folder)
    except ValueError as e:
        print(f"❌ 错误: {e}")
        return
    
    if not all_docs:
        print("❌ 没有找到任何图片文档！")
        return
    
    # 创建向量存储
    print("📊 正在创建向量数据库...")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    chroma_all = Chroma.from_documents(
        all_docs,
        embedding=embeddings,
        collection_name='conversational_image_search'
    )
    
    print("✅ 系统初始化完成！")
    print("\n🤖 AI图片搜索助手已准备就绪！")
    print("💬 你可以用自然语言描述你想要的图片，例如：")
    print("   - '我想看iPad的图片'")
    print("   - '有没有Apple Pencil的JPG照片？'")
    print("   - '给我找一些iPhone摄像头的图片'")
    print("   - '苹果手表的PNG图片'")
    print("\n输入 'quit' 退出对话")
    
    # 对话循环
    while True:
        print("\n" + "="*50)
        user_input = input("👤 你：").strip()
        
        if user_input.lower() in ['quit', 'exit', '退出', '再见']:
            print("🤖 助手：再见！感谢使用图片搜索服务！")
            break
        
        if not user_input:
            print("🤖 助手：请告诉我你想要什么样的图片？")
            continue
        
        print("🤖 助手：让我来帮你搜索...")
        
        # 使用AI解析用户查询
        parsed_query = parse_user_query_with_ai(user_input)
        
        print(f"🔍 {parsed_query['response_message']}")
        
        # 执行搜索
        search_results = search_images_with_dedup(
            chroma_all, 
            parsed_query['search_query'],
            format_filter=parsed_query['format_filter'],
            max_results=5
        )
        
        # 使用AI格式化结果
        formatted_response = format_search_results_with_ai(search_results, user_input)
        print(f"\n🤖 助手：{formatted_response}")

if __name__ == "__main__":
    main()