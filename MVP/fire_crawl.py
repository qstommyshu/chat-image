from firecrawl import FirecrawlApp, ScrapeOptions
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse

# 1. 初始化 Firecrawl
app = FirecrawlApp(api_key="fc-953a025f973941da8233d16c09cde880")

# 2. 抓取原始 HTML（带所有标签，不清洗）
crawl_result = app.crawl_url(
    'https://www.apple.com/ipad',
    limit=1,
    scrape_options=ScrapeOptions(
        formats=['rawHtml'],
        onlyMainContent=False,
        includeTags=['img', 'source'],  # 同时保留 <img> 和 <source>
        renderJs=True                    # 可选：执行 JS 以注入所有懒加载属性
    ),
)

# 3. 提取 HTML 内容
html_content = crawl_result.data[0].rawHtml

# 4. 保存原始 HTML
with open('apple_page.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("✔ 已保存：apple_page.html")

# 5. 解析出所有图片 URL
soup = BeautifulSoup(html_content, 'html.parser')
base_url = 'https://www.apple.com'

image_urls = set()

# 5a. 从 <source srcset=""> 中提取
for src in soup.select('source[srcset]'):
    for part in src['srcset'].split(','):
        url = part.strip().split(' ')[0]
        full = urljoin(base_url, url)
        image_urls.add(full)

# 5b. 从 <img> 的各种属性中提取
for img in soup.find_all('img'):
    for attr in ('src', 'data-src', 'data-lazy-src', 'data-srcset'):
        if img.has_attr(attr):
            for url in img[attr].split(','):
                url = url.strip().split(' ')[0]
                full = urljoin(base_url, url)
                image_urls.add(full)

# 6. 下载图片到 images/ 目录
os.makedirs('images', exist_ok=True)

for url in image_urls:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        # 从 URL 中取文件名
        path = urlparse(url).path
        filename = os.path.basename(path)
        if not filename:
            # 万一没有文件名，随机命名
            filename = f"img_{hash(url)}.jpg"
        filepath = os.path.join('images', filename)
        with open(filepath, 'wb') as f:
            f.write(resp.content)
        print(f"✔ 下载：{url} → {filepath}")
    except Exception as e:
        print(f"✗ 下载失败：{url} ({e})")
