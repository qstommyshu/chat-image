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
    for i, source in enumerate(all_sources[:3]):
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
    for i, doc in enumerate(pencil_docs[:3]):
        print(f"\nPencil相关 {i+1}:")
        print(f"格式: {doc.metadata['img_format']}")
        print(f"来源: {doc.metadata['source_type']}")
        print(f"URL: {doc.metadata['img_url']}")
        print(f"Alt: {doc.metadata.get('alt_text', 'N/A')}")
        print(f"Context: {doc.page_content[:200]}...")

if ipad_docs:
    print(f"\n=== iPad相关内容样本 ===")
    for i, doc in enumerate(ipad_docs[:3]):
        print(f"\niPad相关 {i+1}:")
        print(f"格式: {doc.metadata['img_format']}")
        print(f"来源: {doc.metadata['source_type']}")
        print(f"URL: {doc.metadata['img_url']}")
        print(f"Alt: {doc.metadata.get('alt_text', 'N/A')}")
        print(f"Context: {doc.page_content[:200]}...")

# 7. 创建向量存储并提供交互式查询
if len(all_docs) > 0:
    print(f"\n=== 创建向量存储 ===")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    
    chroma_all = Chroma.from_documents(
        all_docs,
        embedding=embeddings,
        collection_name='apple_images_debug'
    )
    
    print(f"向量存储创建完成！包含 {len(all_docs)} 个图片文档")
    print(f"其中JPG格式: {len(jpg_docs)} 个")
    
    # 统计PNG文档
    png_docs = [doc for doc in all_docs if doc.metadata['img_format'] == 'png']
    print(f"其中PNG格式: {len(png_docs)} 个")
    
    # 交互式查询系统
    print(f"\n=== 交互式图片搜索 ===")
    print("输入查询来搜索相关图片（输入 'quit' 退出）")
    print("\n🔍 搜索格式:")
    print("  your_query          - 搜索所有格式（优先JPG/PNG）")
    print("  jpg:your_query      - 仅搜索JPG格式")
    print("  png:your_query      - 仅搜索PNG格式")
    print("  jpg+png:your_query  - 仅搜索JPG和PNG格式")
    print("\n💡 示例查询:")
    print("  apple pencil")
    print("  jpg:iPad Pro")
    print("  png:iPhone camera")
    print("  jpg+png:MacBook Air")
    
    while True:
        user_input = input("\n请输入搜索查询: ").strip()
        
        if user_input.lower() == 'quit':
            print("退出搜索。再见！")
            break
            
        if not user_input:
            print("请输入有效的搜索查询。")
            continue
        
        # 解析搜索格式和查询
        format_filter = None
        query = user_input
        
        if user_input.startswith('jpg:'):
            format_filter = ['jpg']
            query = user_input[4:].strip()
        elif user_input.startswith('png:'):
            format_filter = ['png']
            query = user_input[4:].strip()
        elif user_input.startswith('jpg+png:'):
            format_filter = ['jpg', 'png']
            query = user_input[8:].strip()
        
        if not query:
            print("请输入有效的搜索查询词。")
            continue
        
        # 显示搜索信息
        if format_filter:
            format_str = " + ".join(format_filter).upper()
            print(f"\n正在搜索 {format_str} 格式的图片: '{query}'...")
        else:
            print(f"\n正在搜索所有格式的图片: '{query}' (优先JPG/PNG)...")
        
        # 执行相似性搜索
        results = chroma_all.similarity_search_with_score(query, k=30)  # 获取更多结果用于过滤
        
        # 处理和过滤结果
        processed_results = []
        
        for doc, score in results:
            img_format = doc.metadata['img_format']
            
            # 应用格式过滤
            if format_filter and img_format not in format_filter:
                continue
            
            img_info = {
                'url': doc.metadata['img_url'],
                'format': img_format,
                'alt_text': doc.metadata.get('alt_text', ''),
                'title': doc.metadata.get('title', ''),
                'source_type': doc.metadata['source_type'],
                'media': doc.metadata.get('media', ''),
                'score': score,
                'context': doc.page_content
            }
            processed_results.append(img_info)
        
        # 排序结果：如果没有指定格式过滤，优先JPG和PNG
        if not format_filter:
            # 优先JPG，然后PNG，然后其他格式，最后按分数排序
            processed_results.sort(key=lambda x: (
                x['format'] not in ['jpg', 'png'],  # 优先JPG/PNG
                x['format'] != 'jpg',               # JPG优先于PNG
                x['score']                          # 按分数排序
            ))
        else:
            # 如果指定了格式，只按分数排序
            processed_results.sort(key=lambda x: x['score'])
        
        # 返回前5个结果
        top_5 = processed_results[:5]
        
        if not top_5:
            if format_filter:
                format_str = " + ".join(format_filter).upper()
                print(f"❌ 没有找到 {format_str} 格式的相关图片")
                print("💡 建议:")
                print("  - 尝试不同的查询词")
                print("  - 移除格式限制搜索所有格式")
            else:
                print("❌ 没有找到相关图片")
            continue
        
        print(f"\n找到 {len(processed_results)} 个相关结果，显示前5个:")
        print("=" * 80)
        
        for i, img in enumerate(top_5, 1):
            print(f"\n【图片 {i}】")
            print(f"URL: {img['url']}")
            
            # 根据格式添加标识
            format_display = img['format'].upper()
            if img['format'] == 'jpg':
                format_display += " ✅"
            elif img['format'] == 'png':
                format_display += " 🟢"
            
            print(f"格式: {format_display}")
            print(f"相似度分数: {img['score']:.4f}")
            
            if img['alt_text']:
                print(f"Alt文本: {img['alt_text']}")
            
            if img['title']:
                print(f"标题: {img['title']}")
            
            if img['media']:
                print(f"媒体查询: {img['media']}")
            
            print(f"来源: {img['source_type']} 标签")
            
            # 显示相关上下文（截取重要部分）
            context = img['context']
            if len(context) > 200:
                context = context[:200] + "..."
            print(f"上下文: {context}")
            
            print("-" * 60)
        
        # 统计信息
        format_count = {}
        for img in top_5:
            fmt = img['format']
            format_count[fmt] = format_count.get(fmt, 0) + 1
        
        print(f"\n📊 结果格式分布: {dict(format_count)}")
        
        # 提供建议
        jpg_count = format_count.get('jpg', 0)
        png_count = format_count.get('png', 0)
        
        if format_filter:
            format_str = " + ".join(format_filter).upper()
            print(f"✅ 成功找到 {len(top_5)} 个 {format_str} 格式的图片")
        else:
            total_hq = jpg_count + png_count
            if total_hq == 0:
                print("\n💡 提示: 没有找到JPG/PNG格式的图片。你可以尝试:")
                print("  - 更具体的查询词")
                print("  - 使用 'jpg:查询词' 或 'png:查询词' 来专门搜索")
            else:
                print(f"\n✅ 找到 {total_hq} 个高质量图片 (JPG: {jpg_count}, PNG: {png_count})")

else:
    print("没有找到任何图片文档！")