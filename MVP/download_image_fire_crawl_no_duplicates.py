from firecrawl import FirecrawlApp, ScrapeOptions
import requests
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import urljoin, urlparse

# 1. 抓取原始 HTML
app = FirecrawlApp(api_key="fc-953a025f973941da8233d16c09cde880")
crawl_result = app.crawl_url(
    'https://www.apple.com/ipad',
    limit=1,
    scrape_options=ScrapeOptions(
        formats=['rawHtml'],
        onlyMainContent=False,
        includeTags=['img', 'source'],
        renderJs=True
    ),
)
html_content = crawl_result.data[0].rawHtml

# 2. 保存 HTML
with open('apple_page.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("✔ 已保存：apple_page.html")

# 3. 从 HTML 中提取所有候选图片 URL
soup = BeautifulSoup(html_content, 'html.parser')
base_url = 'https://www.apple.com'
candidates = set()

# <source srcset="">
for src in soup.select('source[srcset]'):
    for part in src['srcset'].split(','):
        url = part.strip().split(' ')[0]
        candidates.add(urljoin(base_url, url))

# <img> 的各种属性
for img in soup.find_all('img'):
    for attr in ('src', 'data-src', 'data-lazy-src', 'data-srcset'):
        if not img.has_attr(attr): 
            continue
        for part in img[attr].split(','):
            url = part.strip().split(' ')[0]
            candidates.add(urljoin(base_url, url))

# 4. 分组去重：同一 “业务前缀” 只保留一条
pattern = re.compile(r'^(?P<base>.+)_[0-9a-f]+(?:_.*)?\.(?P<ext>png|jpe?g|svg)$')
groups = {}
for url in candidates:
    fname = os.path.basename(urlparse(url).path)
    m = pattern.match(fname)
    if m:
        base = m.group('base')
        # 尺寸后缀部分：从 hash 之后到扩展名前的文本，比如 "_medium_2x"、"_2x" 等
        size_suffix = fname[len(base)+1: fname.rfind('.')]  
    else:
        # 无 hash 格式，直接以整个文件名为前缀
        base = fname
        size_suffix = ''
    # 如果还没存，或者当前是“不带尺寸后缀”的版本，就覆盖
    if base not in groups or (size_suffix == '' and groups[base][1] != ''):
        groups[base] = (url, size_suffix)

# 最终只下载 groups 中保留下来的 URL
to_download = [info[0] for info in groups.values()]

# 5. 下载到 images/
os.makedirs('images', exist_ok=True)
for url in to_download:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        fname = os.path.basename(urlparse(url).path)
        path = os.path.join('images', fname)
        with open(path, 'wb') as f:
            f.write(resp.content)
        print(f"✔ 下载：{url} → {path}")
    except Exception as e:
        print(f"✗ 下载失败：{url} ({e})")
