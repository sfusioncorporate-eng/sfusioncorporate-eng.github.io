#!/usr/bin/env python3
"""Validate full RSS articles and optionally deployed public resources."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from lxml import html
from PIL import Image

ROOT = Path(__file__).resolve().parent
BASE = 'https://sfusioncorporate-eng.github.io'
NS = {'content':'http://purl.org/rss/1.0/modules/content/'}
ALLOWED = {'p','a','b','i','u','s','h1','h2','h3','h4','blockquote','ul','ol','li','figure','figcaption','img','video','source'}

def check():
    scheduled = json.loads((ROOT/'content/scheduled-articles.json').read_text())
    slots = [a['slot_id'] for a in scheduled]
    assert len(slots) == len(set(slots)), 'Duplicate publication slot'
    assert all(len(a['blocks']) == 4 for a in scheduled)
    feed = ET.parse(ROOT/'rss.xml')
    items = feed.findall('./channel/item')
    assert 10 <= len(items) <= 500, f'Unexpected item count: {len(items)}'
    guids = [i.findtext('guid') for i in items]
    assert len(set(guids)) == len(items)
    urls = {BASE+'/rss.xml',BASE+'/',BASE+'/assets/style.css',BASE+'/robots.txt',BASE+'/sitemap.xml'}
    image_hashes = set()
    total_images = 0
    now = datetime.now(timezone.utc)
    recent = 0
    summaries = []
    for item in items:
        link = item.findtext('link')
        assert link == item.findtext('guid') and link.startswith(BASE+'/articles/')
        assert '?' not in link
        published = parsedate_to_datetime(item.findtext('pubDate'))
        assert published <= now
        recent += int(published >= now-timedelta(days=30))
        assert item.findtext('category') == 'format-article'
        body = item.findtext('content:encoded',namespaces=NS)
        fragment = html.fragment_fromstring(body,create_parent='div')
        assert all(e.tag in ALLOWED for e in fragment.iterdescendants())
        local_path = ROOT/(urlparse(link).path.lstrip('/')+'index.html')
        page = html.fromstring(local_path.read_text())
        assert page.xpath('//h1/text()') == [item.findtext('title')]
        article = page.xpath('//article')[0]
        norm = lambda x:' '.join(x.split())
        assert norm(fragment.text_content()) == norm(article.text_content()), f'Full text mismatch: {link}'
        imgs = fragment.xpath('.//img')
        expected = 5 if 'raion-u-okeana-arenda' in link else 4
        assert len(imgs) == expected
        assert [e.get('src') for e in article.xpath('.//img')] == [e.get('src') for e in imgs]
        if expected == 4:
            for h in fragment.xpath('./h2'):
                assert h.getnext().tag == 'figure',f'Image missing after heading: {link}'
        for img in imgs:
            src = img.get('src')
            assert src.startswith(BASE+'/assets/') and img.get('alt')
            path = ROOT/urlparse(src).path.lstrip('/')
            with Image.open(path) as im:
                assert im.format == 'JPEG' and min(im.size)>=700
                assert im.size == (int(img.get('width')),int(img.get('height')))
                im.verify()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest not in image_hashes,'Duplicate image'
            image_hashes.add(digest)
            urls.add(src)
        enclosure = item.find('enclosure')
        assert enclosure.get('url') == imgs[0].get('src')
        assert enclosure.get('type') == 'image/jpeg'
        assert int(enclosure.get('length')) == (ROOT/urlparse(enclosure.get('url')).path.lstrip('/')).stat().st_size
        urls.add(link)
        total_images += len(imgs)
        summaries.append({'url':link,'characters':len(fragment.text_content()),'images':len(imgs)})
    assert recent >= 3
    homepage = html.fromstring((ROOT/'index.html').read_text())
    assert len(homepage.xpath('//a[@class="story"]')) == len(items)
    token = homepage.xpath('//meta[@name="zen-verification"]/@content')[0]
    assert len(token) == 64
    verification_path = ROOT/f'zen_{token}.html'
    assert verification_path.exists() and token in verification_path.read_text()
    urls.add(BASE+'/'+verification_path.name)
    assert 'Disallow: /' not in (ROOT/'robots.txt').read_text()
    ET.parse(ROOT/'sitemap.xml')
    live_results = []
    if '--live' in sys.argv:
        def fetch(url):
            req = Request(url,headers={'User-Agent':'Mozilla/5.0 JournalValidation/1.0'})
            with urlopen(req,timeout=45) as response:
                data = response.read()
                assert response.status == 200
                assert response.geturl() == url, f'Unexpected redirect: {url}'
                path = urlparse(url).path.lstrip('/')
                if not path or path.endswith('/'):
                    path += 'index.html'
                assert data == (ROOT/path).read_bytes(), f'Deployed content differs: {url}'
                return {'url':url,'status':response.status,'bytes':len(data)}
        with ThreadPoolExecutor(max_workers=4) as pool:
            live_results = list(pool.map(fetch,sorted(urls)))
    result = {'checked_at':now.isoformat(),'items':len(items),'images':total_images,'recent_items':recent,'unique_guids':len(set(guids)),'live_resources_checked':len(live_results),'articles':summaries,'resources':live_results}
    (ROOT/'content/validation-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['articles','resources']},ensure_ascii=False))

if __name__ == '__main__':
    check()

