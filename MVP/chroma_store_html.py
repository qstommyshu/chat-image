"""
调试版本：分析为什么找不到JPG图片
"""
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# 载入环境变量
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("请设置环境变量 OPENAI_API_KEY")

# 1. 读取 HTML
with open('apple_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f"HTML文件大小: {len(html)} 字符")

soup = BeautifulSoup(html, 'html.parser')
base_url = 'https://www.apple.com'

# 2. 详细分析所有图片和source标签
print("\n=== 详细分析所有图片和source标签 ===")
all_imgs = soup.find_all('img')
all_sources = soup.find_all('source')
print(f"找到 {len(all_imgs)} 个 img 标签")
print(f"找到 {len(all_sources)} 个 source 标签")

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
    
    # 1. source标签的属性
    media_attr = source_tag.get('media', '')
    if media_attr:
        context_parts.append(f"Media: {media_attr}")
    
    # 2. 查找关联的picture元素
    picture = source_tag.find_parent('picture')
    if picture:
        # 在picture中查找img标签
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
    
    # 3. 查找父元素的文本内容
    parent = source_tag.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        if parent_text and len(parent_text) < 300:
            context_parts.append(f"Parent text: {parent_text}")
    
    # 4. 查找周围的文本
    for sibling in source_tag.find_next_siblings(text=True)[:2]:
        sibling_text = sibling.strip()
        if sibling_text and len(sibling_text) < 100:
            context_parts.append(f"Next text: {sibling_text}")
            break
    
    return " | ".join(context_parts) if context_parts else str(source_tag)

def extract_context(img_tag):
    """提取图片的上下文信息"""
    context_parts = []
    
    # 1. img标签本身的属性
    alt_text = img_tag.get('alt', '')
    title_text = img_tag.get('title', '')
    class_attr = ' '.join(img_tag.get('class', []))
    
    if alt_text:
        context_parts.append(f"Alt: {alt_text}")
    if title_text:
        context_parts.append(f"Title: {title_text}")
    if class_attr:
        context_parts.append(f"Class: {class_attr}")
    
    # 2. 父元素的文本内容
    parent = img_tag.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        if parent_text and len(parent_text) < 200:
            context_parts.append(f"Parent text: {parent_text}")
    
    # 3. 查找相邻的文本元素
    for sibling in img_tag.find_next_siblings(text=True)[:2]:
        sibling_text = sibling.strip()
        if sibling_text and len(sibling_text) < 100:
            context_parts.append(f"Next text: {sibling_text}")
            break
    
    for sibling in img_tag.find_previous_siblings(text=True)[:2]:
        sibling_text = sibling.strip()
        if sibling_text and len(sibling_text) < 100:
            context_parts.append(f"Prev text: {sibling_text}")
            break
    
    return " | ".join(context_parts) if context_parts else str(img_tag)

# 3. 分析source标签中的图片（重点！）
print(f"\n=== 分析前10个source标签 ===")
source_docs = []
source_format_stats = {}

for i, source in enumerate(all_sources[:10]):
    print(f"\n--- Source {i+1} ---")
    
    srcset = source.get('srcset', '')
    if not srcset:
        print("没有找到srcset属性")
        continue
    
    print(f"Srcset: {srcset}")
    
    # 解析srcset，可能包含多个URL
    urls = []
    for part in srcset.split(','):
        url_part = part.strip().split(' ')[0]  # 去掉 "2x" 等描述符
        if url_part.startswith('/'):
            url_part = urljoin(base_url, url_part)
        urls.append(url_part)
    
    print(f"解析出的URLs: {urls}")
    
    for url in urls:
        img_format = get_image_format(url)
        print(f"格式: {img_format}, URL: {url}")
        
        source_format_stats[img_format] = source_format_stats.get(img_format, 0) + 1
        
        context = extract_context_from_source(source)
        print(f"上下文: {context[:200]}...")

print(f"\n=== Source标签格式统计（前10个）===")
for fmt, count in sorted(source_format_stats.items()):
    print(f"{fmt}: {count} 张")

# 3. 分析和收集所有图片
docs = []
format_stats = {}
sample_urls = {}

for i, img in enumerate(all_imgs[:10]):  # 先看前10个作为样本
    print(f"\n--- 图片 {i+1} ---")
    
    # 获取图片URL
    raw = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-srcset')
    
    if not raw:
        print("没有找到图片URL")
        continue
    
    print(f"原始URL属性: {raw}")
    
    # 处理可能的多个URL（srcset）
    urls = []
    for part in raw.split(','):
        u = part.strip().split(' ')[0]
        if u.startswith('//'):
            u = 'https:' + u
        elif u.startswith('/'):
            u = urljoin(base_url, u)
        urls.append(u)
    
    print(f"处理后的URL: {urls}")
    
    # 分析每个URL
    for url in urls:
        img_format = get_image_format(url)
        print(f"格式: {img_format}, URL: {url}")
        
        # 统计格式
        format_stats[img_format] = format_stats.get(img_format, 0) + 1
        
        # 保存样本URL
        if img_format not in sample_urls:
            sample_urls[img_format] = url
        
        # 提取上下文
        context = extract_context(img)
        print(f"上下文: {context[:200]}...")
        
        # 创建文档
        doc = Document(
            page_content=context,
            metadata={
                'img_url': url,
                'img_format': img_format,
                'alt_text': img.get('alt', ''),
                'title': img.get('title', ''),
                'class': ' '.join(img.get('class', [])),
                'original_tag': str(img)
            }
        )
        docs.append(doc)

print(f"\n=== 格式统计（前10张图片的样本）===")
for fmt, count in sorted(format_stats.items()):
    print(f"{fmt}: {count} 张")
    if fmt in sample_urls:
        print(f"  样本URL: {sample_urls[fmt]}")

# 4. 处理所有图片和source标签
print(f"\n=== 处理所有图片和source标签 ===")
all_docs = []
all_format_stats = {}
jpg_docs = []

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
        
        img_format = get_image_format(u)
        all_format_stats[img_format] = all_format_stats.get(img_format, 0) + 1
        
        context = extract_context(img)
        
        doc = Document(
            page_content=context,
            metadata={
                'img_url': u,
                'img_format': img_format,
                'alt_text': img.get('alt', ''),
                'title': img.get('title', ''),
                'class': ' '.join(img.get('class', [])),
                'source_type': 'img'
            }
        )
        
        all_docs.append(doc)
        
        if img_format == 'jpg':
            jpg_docs.append(doc)

# 处理source标签（重点！）
for source in all_sources:
    srcset = source.get('srcset', '')
    if not srcset:
        continue
    
    # 解析srcset
    for part in srcset.split(','):
        url_part = part.strip().split(' ')[0]  # 去掉 "2x" 等描述符
        if url_part.startswith('/'):
            url_part = urljoin(base_url, url_part)
        
        img_format = get_image_format(url_part)
        all_format_stats[img_format] = all_format_stats.get(img_format, 0) + 1
        
        context = extract_context_from_source(source)
        
        # 尝试从关联的picture/img获取更多信息
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
            page_content=context,
            metadata={
                'img_url': url_part,
                'img_format': img_format,
                'alt_text': alt_text,
                'title': title_text,
                'class': class_attr,
                'source_type': 'source',
                'media': source.get('media', '')
            }
        )
        
        all_docs.append(doc)
        
        if img_format == 'jpg':
            jpg_docs.append(doc)

print(f"总共处理了 {len(all_docs)} 个图片文档")
print(f"其中JPG格式: {len(jpg_docs)} 个")

print("\n=== 完整格式统计 ===")
for fmt, count in sorted(all_format_stats.items()):
    print(f"{fmt}: {count} 张")

# 5. 如果有JPG，显示JPG样本
if jpg_docs:
    print(f"\n=== JPG图片样本 ===")
    for i, doc in enumerate(jpg_docs[:5]):  # 显示前5个JPG
        print(f"\nJPG {i+1}:")
        print(f"来源: {doc.metadata['source_type']}")
        print(f"URL: {doc.metadata['img_url']}")
        print(f"Alt: {doc.metadata.get('alt_text', 'N/A')}")
        if doc.metadata.get('media'):
            print(f"Media: {doc.metadata['media']}")
        print(f"Context: {doc.page_content[:300]}...")
        
        # 检查是否包含pencil相关内容
        content_lower = doc.page_content.lower()
        if 'pencil' in content_lower or 'ipad' in content_lower:
            print(f"*** 可能相关内容！包含关键词 ***")
else:
    print(f"\n=== 没有找到JPG图片！===")
    print("可能的原因:")
    print("1. source标签中的URL路径解析有问题")
    print("2. 需要检查更多的属性")
    
    # 检查一些原始source标签
    print(f"\n=== 原始source标签样本 ===")
    for i, source in enumerate(all_sources[:5]):
        print(f"\nSource {i+1}:")
        print(f"完整标签: {source}")
        srcset = source.get('srcset', '')
        if srcset:
            print(f"Srcset: {srcset}")
            for part in srcset.split(','):
                url_part = part.strip().split(' ')[0]
                print(f"  解析URL: {url_part}")
                if url_part.startswith('/'):
                    full_url = urljoin(base_url, url_part)
                    print(f"  完整URL: {full_url}")
                    print(f"  格式: {get_image_format(full_url)}")

# 6. 检查是否有包含"pencil"或"ipad"的内容
print(f"\n=== 搜索包含关键词的内容 ===")
pencil_docs = []
ipad_docs = []

for doc in all_docs:
    content_lower = doc.page_content.lower()
    url_lower = doc.metadata['img_url'].lower()
    alt_lower = doc.metadata.get('alt_text', '').lower()
    
    if 'pencil' in content_lower or 'pencil' in url_lower or 'pencil' in alt_lower:
        pencil_docs.append(doc)
    
    if 'ipad' in content_lower or 'ipad' in url_lower or 'ipad' in alt_lower:
        ipad_docs.append(doc)

print(f"包含'pencil'的文档: {len(pencil_docs)}")
print(f"包含'ipad'的文档: {len(ipad_docs)}")

if pencil_docs:
    print(f"\n=== Pencil相关内容样本 ===")
    for i, doc in enumerate(pencil_docs[:5]):
        print(f"\nPencil相关 {i+1}:")
        print(f"格式: {doc.metadata['img_format']}")
        print(f"来源: {doc.metadata['source_type']}")
        print(f"URL: {doc.metadata['img_url']}")
        print(f"Alt: {doc.metadata.get('alt_text', 'N/A')}")
        print(f"Context: {doc.page_content[:200]}...")

if ipad_docs:
    print(f"\n=== iPad相关内容样本 ===")
    for i, doc in enumerate(ipad_docs[:5]):
        print(f"\niPad相关 {i+1}:")
        print(f"格式: {doc.metadata['img_format']}")
        print(f"来源: {doc.metadata['source_type']}")
        print(f"URL: {doc.metadata['img_url']}")
        print(f"Alt: {doc.metadata.get('alt_text', 'N/A')}")
        print(f"Context: {doc.page_content[:200]}...")

# 7. 只有在有足够文档时才创建向量存储
if len(all_docs) > 0:
    print(f"\n=== 创建向量存储 ===")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    
    chroma_all = Chroma.from_documents(
        all_docs,
        embedding=embeddings,
        collection_name='apple_images_debug'
    )
    
    # 测试多个查询
    queries = ["apple pencil", "iPad pencil", "stylus", "drawing", "ipad"]
    
    for query in queries:
        print(f"\n=== 测试搜索: '{query}' ===")
        results = chroma_all.similarity_search(query, k=10)
        
        print(f"找到 {len(results)} 个结果:")
        
        # 分析搜索结果的格式分布
        result_formats = {}
        jpg_results = []
        relevant_results = []
        
        for doc in results:
            fmt = doc.metadata['img_format']
            result_formats[fmt] = result_formats.get(fmt, 0) + 1
            
            if fmt == 'jpg':
                jpg_results.append(doc)
            
            # 检查是否真的相关
            content_lower = doc.page_content.lower()
            url_lower = doc.metadata['img_url'].lower()
            alt_lower = doc.metadata.get('alt_text', '').lower()
            
            if any(keyword in content_lower or keyword in url_lower or keyword in alt_lower 
                   for keyword in ['pencil', 'stylus', 'drawing', 'ipad']):
                relevant_results.append(doc)
        
        print(f"搜索结果格式分布:")
        for fmt, count in sorted(result_formats.items()):
            print(f"  {fmt}: {count}")
        
        print(f"其中JPG结果: {len(jpg_results)}")
        print(f"明显相关的结果: {len(relevant_results)}")
        
        # 显示前几个结果
        for i, doc in enumerate(results[:5]):
            print(f"\n结果 {i+1}:")
            print(f"格式: {doc.metadata['img_format']}")
            print(f"来源: {doc.metadata['source_type']}")
            print(f"URL: {doc.metadata['img_url']}")
            print(f"Alt: {doc.metadata.get('alt_text', 'N/A')}")
            print(f"内容: {doc.page_content[:150]}...")
        
else:
    print("没有找到任何图片文档！")