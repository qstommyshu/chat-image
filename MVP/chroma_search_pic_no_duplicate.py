"""
多HTML文件图片搜索脚本 - 完全修复版本
支持加载指定文件夹中的所有HTML文件到Chroma向量数据库
包含完整的去重逻辑
"""
import os
import glob
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

def filename_to_url(filename):
    """将文件名转换回原始URL"""
    # 移除.html后缀
    name_without_ext = filename.replace('.html', '')
    
    # 将_替换为/
    url_path = name_without_ext.replace('_', '/')
    
    # 添加https://前缀
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
    
    # 1. source标签的属性
    media_attr = source_tag.get('media', '')
    if media_attr:
        context_parts.append(f"Media: {media_attr}")
    
    # 2. 查找关联的picture元素
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
    
    # 3. 查找父元素的文本内容
    parent = source_tag.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        if parent_text and len(parent_text) < 300:
            context_parts.append(f"Parent text: {parent_text}")
    
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
    
    return " | ".join(context_parts) if context_parts else str(img_tag)

def process_html_file(html_file_path, source_url):
    """处理单个HTML文件，返回文档列表"""
    print(f"\n处理文件: {os.path.basename(html_file_path)}")
    print(f"来源URL: {source_url}")
    
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(html_file_path, 'r', encoding='latin-1') as f:
                html = f.read()
        except:
            print(f"❌ 无法读取文件: {html_file_path}")
            return []
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 解析base_url用于相对路径转换
    parsed_url = urlparse(source_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    docs = []
    all_imgs = soup.find_all('img')
    all_sources = soup.find_all('source')
    
    print(f"  找到 {len(all_imgs)} 个img标签")
    print(f"  找到 {len(all_sources)} 个source标签")
    
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
            
            # 提取img标签的属性
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
                    'source_url': source_url,  # 记录来源页面
                    'source_file': os.path.basename(html_file_path)  # 记录文件名
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
                page_content=f"Alt: {alt_text} | Title: {title_text} | Class: {class_attr} | Context: {context}",
                metadata={
                    'img_url': url_part,
                    'img_format': img_format,
                    'alt_text': alt_text,
                    'title': title_text,
                    'class': class_attr,
                    'source_type': 'source',
                    'media': source.get('media', ''),
                    'source_url': source_url,  # 记录来源页面
                    'source_file': os.path.basename(html_file_path)  # 记录文件名
                }
            )
            docs.append(doc)
    
    print(f"  提取了 {len(docs)} 个图片文档")
    return docs

def load_html_folder(folder_path):
    """加载文件夹中的所有HTML文件"""
    print(f"\n=== 加载HTML文件夹: {folder_path} ===")
    
    if not os.path.exists(folder_path):
        raise ValueError(f"文件夹不存在: {folder_path}")
    
    # 查找所有HTML文件
    html_pattern = os.path.join(folder_path, "*.html")
    html_files = glob.glob(html_pattern)
    
    if not html_files:
        raise ValueError(f"在文件夹中没有找到HTML文件: {folder_path}")
    
    print(f"找到 {len(html_files)} 个HTML文件")
    
    all_docs = []
    source_stats = {}
    format_stats = {}
    
    for html_file in html_files:
        filename = os.path.basename(html_file)
        source_url = filename_to_url(filename)
        
        # 处理单个HTML文件
        docs = process_html_file(html_file, source_url)
        all_docs.extend(docs)
        
        # 统计来源
        source_stats[source_url] = len(docs)
        
        # 统计格式
        for doc in docs:
            fmt = doc.metadata['img_format']
            format_stats[fmt] = format_stats.get(fmt, 0) + 1
    
    print(f"\n=== 加载完成 ===")
    print(f"总共处理了 {len(all_docs)} 个图片文档")
    print(f"来自 {len(html_files)} 个不同的页面")
    
    print(f"\n=== 来源统计 ===")
    for source_url, count in sorted(source_stats.items()):
        print(f"  {source_url}: {count} 张图片")
    
    print(f"\n=== 格式统计 ===")
    for fmt, count in sorted(format_stats.items()):
        print(f"  {fmt}: {count} 张")
    
    return all_docs

# 主程序
def main():
    # 配置文件夹路径
    crawled_folder = "crawled_pages_apple"  # 修改为你的文件夹路径
    
    # 加载所有HTML文件
    all_docs = load_html_folder(crawled_folder)
    
    if not all_docs:
        print("没有找到任何图片文档！")
        return
    
    # 创建向量存储
    print(f"\n=== 创建向量存储 ===")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    
    chroma_all = Chroma.from_documents(
        all_docs,
        embedding=embeddings,
        collection_name='multi_page_images'
    )
    
    print(f"向量存储创建完成！")
    
    # 统计各种格式
    jpg_docs = [doc for doc in all_docs if doc.metadata['img_format'] == 'jpg']
    png_docs = [doc for doc in all_docs if doc.metadata['img_format'] == 'png']
    print(f"其中JPG格式: {len(jpg_docs)} 个")
    print(f"其中PNG格式: {len(png_docs)} 个")
    
    # 交互式查询系统
    print(f"\n=== 多页面图片搜索系统 ===")
    print("输入查询来搜索相关图片（输入 'quit' 退出）")
    print("\n🔍 搜索格式:")
    print("  your_query          - 基于Alt文本搜索所有格式（优先JPG/PNG）")
    print("  jpg:your_query      - 基于Alt文本仅搜索JPG格式")
    print("  png:your_query      - 基于Alt文本仅搜索PNG格式")
    print("  jpg+png:your_query  - 基于Alt文本仅搜索JPG和PNG格式")
    print("\n💡 示例查询:")
    print("  apple pencil        - 在所有页面中查找Apple Pencil相关图片")
    print("  jpg:iPad Pro        - 查找JPG格式的iPad Pro图片")
    print("  png:iPhone camera   - 查找PNG格式的iPhone相机图片")
    print("\n📝 搜索说明:")
    print("  - 搜索结果会显示图片来源页面URL")
    print("  - 自动去重相同Alt文本和相同文件的不同尺寸")
    print("  - 支持跨多个页面搜索")
    
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
            print(f"\n🔍 正在跨页面搜索 {format_str} 格式的图片: '{query}'...")
        else:
            print(f"\n🔍 正在跨页面搜索所有格式的图片: '{query}' (优先JPG/PNG)...")
        
        # 执行相似性搜索
        results = chroma_all.similarity_search_with_score(query, k=50)
        
        print(f"🔎 从向量数据库找到 {len(results)} 个初始匹配结果")
        
        # 处理和过滤结果
        processed_results = []
        
        for doc, score in results:
            img_format = doc.metadata['img_format']
            
            # 应用格式过滤
            if format_filter and img_format not in format_filter:
                continue
            
            # 提取Alt文本进行额外匹配检查
            alt_text = doc.metadata.get('alt_text', '').lower()
            title_text = doc.metadata.get('title', '').lower()
            query_lower = query.lower()
            
            # 计算Alt文本匹配度
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
                'source_url': doc.metadata['source_url'],  # 来源页面URL
                'source_file': doc.metadata['source_file'],  # 来源文件名
                'context': doc.page_content
            }
            processed_results.append(img_info)
        
        print(f"🎯 应用格式过滤后: {len(processed_results)} 个结果")
        
        # 去重逻辑：1) 基于文件名 2) 基于Alt文本
        def get_image_base_name(url):
            """提取图片的基础名称，用于检测重复"""
            import re
            from urllib.parse import urlparse
            
            path = urlparse(url).path
            filename = path.split('/')[-1]
            name_without_ext = filename.rsplit('.', 1)[0]
            
            # 移除常见的大小/分辨率后缀
            patterns_to_remove = [
                r'_2x$',           # _2x
                r'_3x$',           # _3x
                r'_large$',        # _large
                r'_medium$',       # _medium
                r'_small$',        # _small
                r'_thumb$',        # _thumb
                r'_\d+x\d+$',      # _1920x1080
                r'_@2x$',          # _@2x
                r'_@3x$',          # _@3x
            ]
            
            base_name = name_without_ext
            for pattern in patterns_to_remove:
                base_name = re.sub(pattern, '', base_name)
            
            path_parts = path.split('/')[:-1]
            if len(path_parts) > 2:
                context_path = '/'.join(path_parts[-2:])
                return f"{context_path}/{base_name}"
            else:
                return base_name
        
        def should_prefer_image(img1, img2):
            """决定应该保留哪张图片"""
            url1, url2 = img1['url'], img2['url']
            
            # 1. 优先保留非retina版本
            has_retina_1 = any(suffix in url1.lower() for suffix in ['_2x', '_3x', '@2x', '@3x'])
            has_retina_2 = any(suffix in url2.lower() for suffix in ['_2x', '_3x', '@2x', '@3x'])
            
            if has_retina_1 != has_retina_2:
                return not has_retina_1
            
            # 2. 优先保留更大尺寸
            size_priority = {'large': 3, 'medium': 2, 'small': 1, '': 2}
            
            def get_size_priority(url):
                url_lower = url.lower()
                for size in size_priority:
                    if size and size in url_lower:
                        return size_priority[size]
                return size_priority['']
            
            priority1 = get_size_priority(url1)
            priority2 = get_size_priority(url2)
            
            if priority1 != priority2:
                return priority1 > priority2
            
            # 3. 保留Alt匹配度更高的
            if img1['alt_match_score'] != img2['alt_match_score']:
                return img1['alt_match_score'] > img2['alt_match_score']
            
            # 4. 保留相似度分数更高的
            return img1['score'] < img2['score']
        
        # 第一层去重：基于文件名
        unique_results = []
        seen_base_names = {}
        
        for img in processed_results:
            base_name = get_image_base_name(img['url'])
            
            if base_name in seen_base_names:
                existing_img = seen_base_names[base_name]
                if should_prefer_image(img, existing_img):
                    seen_base_names[base_name] = img
                    unique_results = [r for r in unique_results if get_image_base_name(r['url']) != base_name]
                    unique_results.append(img)
            else:
                seen_base_names[base_name] = img
                unique_results.append(img)
        
        print(f"📋 文件名去重: {len(processed_results)} -> {len(unique_results)} 个结果")
        
        # 第二层去重：基于Alt文本
        def normalize_alt_text(alt_text):
            """标准化Alt文本，用于比较"""
            if not alt_text:
                return ""
            import re
            normalized = alt_text.lower().strip()
            normalized = re.sub(r'[^\w\s]', ' ', normalized)
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            return normalized
        
        def should_prefer_by_alt(img1, img2):
            """基于Alt文本相同时，决定保留哪张图片"""
            # 1. 优先保留JPG格式
            if img1['format'] != img2['format']:
                format_priority = {'jpg': 3, 'png': 2, 'webp': 1, 'svg': 0}
                priority1 = format_priority.get(img1['format'], 0)
                priority2 = format_priority.get(img2['format'], 0)
                if priority1 != priority2:
                    return priority1 > priority2
            
            # 2. 优先保留Alt匹配度更高的
            if img1['alt_match_score'] != img2['alt_match_score']:
                return img1['alt_match_score'] > img2['alt_match_score']
            
            # 3. 优先保留更大尺寸
            def get_image_size_score(url):
                url_lower = url.lower()
                if 'large' in url_lower:
                    return 3
                elif 'medium' in url_lower:
                    return 2
                elif 'small' in url_lower:
                    return 1
                else:
                    return 2
            
            size1 = get_image_size_score(img1['url'])
            size2 = get_image_size_score(img2['url'])
            if size1 != size2:
                return size1 > size2
            
            # 4. 优先保留相似度分数更高的
            return img1['score'] < img2['score']
        
        # 执行基于Alt文本的去重
        alt_filtered_results = []
        seen_alt_texts = {}
        
        for img in unique_results:
            alt_text = normalize_alt_text(img['alt_text'])
            
            # 如果Alt文本为空，直接添加
            if not alt_text:
                alt_filtered_results.append(img)
                continue
            
            if alt_text in seen_alt_texts:
                existing_img = seen_alt_texts[alt_text]
                if should_prefer_by_alt(img, existing_img):
                    seen_alt_texts[alt_text] = img
                    alt_filtered_results = [r for r in alt_filtered_results 
                                          if normalize_alt_text(r['alt_text']) != alt_text]
                    alt_filtered_results.append(img)
            else:
                seen_alt_texts[alt_text] = img
                alt_filtered_results.append(img)
        
        # 最终结果
        final_results = alt_filtered_results
        
        print(f"🔄 Alt文本去重: {len(unique_results)} -> {len(final_results)} 个结果")
        print(f"✅ 总去重效果: {len(processed_results)} -> {len(final_results)} 个结果")
        
        # 显示去重统计
        if len(seen_alt_texts) > 0:
            duplicate_alt_count = len(unique_results) - len(final_results)
            if duplicate_alt_count > 0:
                print(f"🗑️ 基于Alt文本去重了 {duplicate_alt_count} 个重复图片")
                
                # 显示被去重的Alt文本样本
                sample_alts = [alt for alt in seen_alt_texts.keys() if alt][:3]
                if sample_alts:
                    print("去重的Alt文本样本:")
                    for alt in sample_alts:
                        print(f"  📝 '{alt}'")
        
        # 排序结果
        if not format_filter:
            final_results.sort(key=lambda x: (
                -x['alt_match_score'],
                x['format'] not in ['jpg', 'png'],
                x['format'] != 'jpg',
                x['score']
            ))
        else:
            final_results.sort(key=lambda x: (
                -x['alt_match_score'],
                x['score']
            ))
        
        # 返回前5个结果
        top_5 = final_results[:5]
        
        if not top_5:
            if format_filter:
                format_str = " + ".join(format_filter).upper()
                print(f"❌ 没有找到 {format_str} 格式的相关图片")
            else:
                print("❌ 没有找到相关图片")
            continue
        
        print(f"\n找到 {len(final_results)} 个相关结果，显示前5个:")
        print("=" * 80)
        
        for i, img in enumerate(top_5, 1):
            print(f"\n【图片 {i}】")
            print(f"图片URL: {img['url']}")
            print(f"📄 来源页面: {img['source_url']}")
            print(f"📁 来源文件: {img['source_file']}")
            
            # 根据格式添加标识
            format_display = img['format'].upper()
            if img['format'] == 'jpg':
                format_display += " ✅"
            elif img['format'] == 'png':
                format_display += " 🟢"
            
            print(f"格式: {format_display}")
            print(f"向量相似度: {img['score']:.4f}")
            print(f"Alt匹配度: {img['alt_match_score']:.1f}")
            
            if img['alt_text']:
                # 高亮显示匹配的查询词
                alt_display = img['alt_text']
                query_words = query.lower().split()
                for word in query_words:
                    if len(word) > 2 and word in alt_display.lower():
                        alt_display = alt_display.replace(word, f"**{word}**")
                        alt_display = alt_display.replace(word.capitalize(), f"**{word.capitalize()}**")
                print(f"Alt文本: {alt_display}")
            
            if img['title']:
                print(f"标题: {img['title']}")
            
            if img['media']:
                print(f"媒体查询: {img['media']}")
            
            print(f"来源标签: {img['source_type']}")
            
            print("-" * 60)
        
        # 统计信息
        format_count = {}
        source_count = {}
        for img in top_5:
            fmt = img['format']
            format_count[fmt] = format_count.get(fmt, 0) + 1
            
            source = img['source_url']
            source_count[source] = source_count.get(source, 0) + 1
        
        print(f"\n📊 结果格式分布: {dict(format_count)}")
        print(f"📄 结果来源分布: {dict(source_count)}")

if __name__ == "__main__":
    main()