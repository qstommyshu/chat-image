from firecrawl import FirecrawlApp, ScrapeOptions
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
import re

load_dotenv()

# 1. 初始化 Firecrawl
app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

# 2. 创建存储文件夹
folder_name = "crawled_pages_apple"
if not os.path.exists(folder_name):
    os.makedirs(folder_name)
    print(f"✔ 创建文件夹：{folder_name}")

print("开始爬取 Apple 网站ipad 相关的 10 个页面...")

# 3. 抓取多个页面（带所有标签，不清洗）
crawl_result = app.crawl_url(
    'https://www.apple.com/iphone',
    limit=10,
    scrape_options=ScrapeOptions(
        formats=['rawHtml'],
        onlyMainContent=False,
        includeTags=['img', 'source', 'picture', 'video'],  # 包含所有媒体标签
        renderJs=True,                   # 执行 JS 以注入所有懒加载属性
        waitFor=3000,                   # 等待3秒让懒加载完成
        skipTlsVerification=False,
        removeBase64Images=False        # 保留 base64 图片
    ),
)

print(f"\n成功爬取了 {len(crawl_result.data)} 个页面")

# 4. 函数：将 URL 转换为安全的文件名
def url_to_filename(url):
    # 移除协议部分
    filename = url.replace('https://', '').replace('http://', '')
    # 替换不安全的字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 替换斜杠为下划线
    filename = filename.replace('/', '_')
    # 如果文件名以点结尾，移除它
    filename = filename.rstrip('.')
    # 添加 .html 扩展名
    if not filename.endswith('.html'):
        filename += '.html'
    return filename

# 5. 处理 HTML 内容并保存每个页面到单独的文件
def fix_image_paths(html_content, base_url):
    """修复 HTML 中的图片路径"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 处理 img 标签
    for img in soup.find_all('img'):
        # 处理懒加载属性
        if img.get('data-src'):
            img['src'] = urljoin(base_url, img['data-src'])
        elif img.get('data-srcset'):
            img['srcset'] = img['data-srcset']
        elif img.get('src') and not img['src'].startswith(('http', 'data:')):
            img['src'] = urljoin(base_url, img['src'])
        
        # 处理 srcset
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
    
    # 处理 source 标签
    for source in soup.find_all('source'):
        if source.get('srcset') and not source['srcset'].startswith(('http', 'data:')):
            source['srcset'] = urljoin(base_url, source['srcset'])
    
    return str(soup)

saved_files = []

for i, page_data in enumerate(crawl_result.data, 1):
    url = page_data.metadata.get('url', f'page_{i}')
    print(f"正在保存第 {i} 个页面: {url}")
    
    # 生成安全的文件名
    filename = url_to_filename(url)
    filepath = os.path.join(folder_name, filename)
    
    # 修复图片路径
    fixed_html = fix_image_paths(page_data.rawHtml, url)
    
    # 保存 HTML 内容
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(fixed_html)
    
    saved_files.append((url, filename))
    print(f"  ✔ 已保存为：{filepath}")
    
    # 统计图片数量
    soup = BeautifulSoup(fixed_html, 'html.parser')
    img_count = len(soup.find_all('img'))
    source_count = len(soup.find_all('source'))
    print(f"    包含 {img_count} 个 img 标签，{source_count} 个 source 标签")

print(f"\n✔ 所有页面已保存到 {folder_name} 文件夹")

# 6. 显示保存结果汇总
print(f"\n保存的文件列表：")
for i, (url, filename) in enumerate(saved_files, 1):
    print(f"{i}. {filename}")
    print(f"   来源: {url}")
    print()