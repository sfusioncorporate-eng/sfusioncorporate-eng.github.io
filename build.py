#!/usr/bin/env python3
"""Build full articles and Dzen RSS from versioned sources."""
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
import json
import re
from PIL import Image

ROOT = Path(__file__).resolve().parent
BASE = 'https://sfusioncorporate-eng.github.io'
DZEN = 'https://dzen.ru/id/68a7478389764b0a8542426d'
CONTENT = ROOT / 'content'

def esc(value):
    return escape(str(value), quote=True)

def build():
    sources = ['new-articles.json', 'more-articles.json', 'final-articles.json', 'scheduled-articles.json']
    articles = [a for source in sources for a in json.loads((CONTENT/source).read_text())]
    state_path = CONTENT/'publication-dates.json'
    dates = json.loads(state_path.read_text()) if state_path.exists() else {}
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for a in articles:
        dates.setdefault(a['slug'], now.isoformat())
    state_path.write_text(json.dumps(dates, ensure_ascii=False, indent=2)+'\n')
    rss_path = ROOT/'rss.xml'
    legacy_path = CONTENT/'original-item.xml'
    if not legacy_path.exists():
        legacy_path.write_text(re.search(r'<item>.*?</item>', rss_path.read_text(), re.S).group())
    legacy_item = legacy_path.read_text()
    home = (ROOT/'index.html').read_text()
    before = home.split('<section class="latest"')[0]
    header = home.split('<body>')[1].split('<main')[0]
    footer = home[home.index('<footer>'):]
    cards, items, stats = [], [], []
    articles.sort(key=lambda a: dates[a['slug']], reverse=True)
    for a in articles:
        slug = a['slug']
        url = f'{BASE}/articles/{slug}/'
        dt = datetime.fromisoformat(dates[slug])
        human_date = f'{dt.day} октября {dt.year}' if dt.month == 10 else dt.strftime('%d.%m.%Y')
        body_parts = []
        for i, block in enumerate(a['blocks']):
            image_path = f"assets/articles/{block['image']}.jpg"
            with Image.open(ROOT/image_path) as im:
                width, height = im.size
            body_parts += [f'<h2>{esc(block["heading"])}</h2>',
                f'<figure><img src="{BASE}/{image_path}" alt="{esc(block["alt"])}" width="{width}" height="{height}"/></figure>']
            body_parts += [f'<p>{esc(p)}</p>' for p in block['paragraphs']]
            if slug == 'dozhdlivyi-den-doma' and i == 0:
                body_parts.append('<p>Проверить актуальные предупреждения можно на <a href="https://www.defesacivil.sc.gov.br/alerta/">официальной странице Defesa Civil Santa Catarina</a>.</p>')
        source_labels = a.get('source_labels', [])
        if a.get('sources') and source_labels:
            links = [f'<a href="{esc(url)}">{esc(label)}</a>' for url, label in zip(a['sources'], source_labels)]
            body_parts.append('<p>Источники: ' + '; '.join(links) + '.</p>')
        cta = a.get('cta')
        if cta:
            body_parts.append(f'<p>{esc(cta["text"])} <a href="{esc(cta["url"])}">{esc(cta["label"])}</a>.</p>')
        body = '\n'.join(body_parts)
        cover = f"{BASE}/assets/articles/{a['blocks'][0]['image']}.jpg"
        cover_path = ROOT/'assets/articles'/f"{a['blocks'][0]['image']}.jpg"
        word_count = sum(len(p.split()) for b in a['blocks'] for p in b['paragraphs'])
        read_minutes = max(1, round(word_count/180))
        head = f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(a['title'])} — Гео Неважно</title><meta name="description" content="{esc(a['description'])}">
<link rel="canonical" href="{url}"><link rel="alternate" type="application/rss+xml" title="Гео Неважно — полные статьи" href="{BASE}/rss.xml">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/style.css">
<meta property="og:type" content="article"><meta property="og:title" content="{esc(a['title'])}"><meta property="og:description" content="{esc(a['description'])}"><meta property="og:url" content="{url}"><meta property="og:image" content="{cover}">
<meta property="article:published_time" content="{dt.isoformat()}"></head><body>'''
        page = head + header + f'''<main id="main"><div class="article-top"><a class="back" href="/">← Все статьи</a><div class="eyebrow">{esc(a['section'])} · Жизнь в Бразилии</div><h1>{esc(a['title'])}</h1><p class="deck">{esc(a['description'])}</p><div class="meta"><span>Гео Неважно</span><time datetime="{dt.isoformat()}">{human_date}</time><span>{read_minutes} мин. чтения</span></div></div>
<article class="prose" aria-label="Текст статьи">{body}</article>
<div class="endnote"><span class="eyebrow">Продолжаем знакомство</span><h2>Жизнь у океана — в деталях.</h2><p>Больше наблюдений и историй — в нашем канале.</p><a class="button" href="{DZEN}">Читать в Дзене ↗</a></div></main>''' + footer
        path = ROOT/'articles'/slug/'index.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page)
        with Image.open(cover_path) as im:
            cw, ch = im.size
        cards.append(f'''<a class="story" href="/articles/{slug}/"><div class="story-image"><img src="{cover}" alt="{esc(a['blocks'][0]['alt'])}" width="{cw}" height="{ch}" loading="lazy"></div><div class="story-text"><div class="eyebrow">{esc(a['section'])}</div><h3>{esc(a['title'])}</h3><p>{esc(a['description'])}</p><div class="story-bottom"><time datetime="{dt.isoformat()}">{human_date}</time><span>Читать статью <b aria-hidden="true">↗</b></span></div></div></a>''')
        items.append(f'''<item><title>{esc(a['title'])}</title><link>{url}</link><guid isPermaLink="true">{url}</guid><pubDate>{format_datetime(dt, usegmt=True)}</pubDate><dc:creator>Гео Неважно</dc:creator><category>format-article</category><description>{esc(a['description'])}</description><content:encoded><![CDATA[{body}]]></content:encoded><enclosure url="{cover}" type="image/jpeg" length="{cover_path.stat().st_size}"/><media:thumbnail url="{cover}"/></item>''')
        stats.append({'slug':slug,'title':a['title'],'characters_with_spaces':len(a['title']+'\n'+'\n'.join(b['heading']+'\n'+'\n'.join(b['paragraphs']) for b in a['blocks'])),'images':len(a['blocks']),'published_at':dt.isoformat()})
    old_card_path = CONTENT/'original-card.html'
    if not old_card_path.exists():
        old_card_path.write_text(re.search(r'<a class="story".*?</a>', home, re.S).group())
    cards.append(old_card_path.read_text())
    (ROOT/'index.html').write_text(before + f'<section class="latest" aria-labelledby="latest-title"><div class="section-line"><h2 id="latest-title">Истории журнала</h2><span>{len(cards)} материалов</span></div>' + '\n'.join(cards)+'</section></main>'+footer)
    old_page = ROOT/'articles/raion-u-okeana-arenda/index.html'
    old_page.write_text(re.sub(r'<meta name="zen-verification"[^>]+>\s*', '', old_page.read_text()))
    rss_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Гео Неважно — журнал</title><link>{BASE}/</link><description>Истории о повседневной жизни во Флорианополисе, Бразилия.</description><language>ru</language><lastBuildDate>{format_datetime(max(datetime.fromisoformat(d) for d in dates.values()),usegmt=True)}</lastBuildDate><atom:link href="{BASE}/rss.xml" rel="self" type="application/rss+xml"/>
'''
    rss_path.write_text(rss_header + '\n'.join(items+[legacy_item]) + '\n</channel></rss>')
    locations = [(BASE+'/',max(dates.values()))] + [(BASE+'/articles/'+a['slug']+'/',dates[a['slug']]) for a in articles] + [(BASE+'/articles/raion-u-okeana-arenda/','2026-10-04T15:55:34+00:00')]
    (ROOT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{url}</loc><lastmod>{date}</lastmod></url>' for url,date in locations)+'</urlset>')
    (CONTENT/'article-stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    print(f'Built {len(articles)} new articles; RSS has {len(items)+1} items.')

if __name__ == '__main__':
    build()

