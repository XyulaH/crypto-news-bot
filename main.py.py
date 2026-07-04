import feedparser
import requests
import time
import json
import os
import html
import re
import urllib.parse
from datetime import datetime

# Берем переменные из окружения Railway
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=cryptocurrency",
    "https://feeds.bloomberg.com/markets/cryptocurrency.rss",
    "https://bitcoinmagazine.com/feed",
    "https://www.coindesk.com/feed/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]

MAX_POSTS_PER_CYCLE = 8

# Используем /tmp для временного хранения (в Railway это работает)
SEEN_FILE = "/tmp/seen_articles.json"

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen), f)
    except Exception as e:
        print(f"Ошибка сохранения: {e}")

def extract_image(entry):
    """Достаёт картинку из RSS."""
    if hasattr(entry, "media_content") and entry.media_content:
        try:
            return entry.media_content[0].get("url")
        except:
            pass
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        try:
            return entry.media_thumbnail[0].get("url")
        except:
            pass
    if hasattr(entry, "links"):
        for link in entry.links:
            if link.get("type", "").startswith("image"):
                return link.get("href")
    summary_html = entry.get("summary", "")
    match = re.search(r'<img[^>]+src="([^"]+)"', summary_html)
    if match:
        return match.group(1)
    return None

def generate_ai_image_url(title):
    """Генерирует AI-картинку через Pollinations."""
    prompt = f"crypto cryptocurrency news, {title[:60]}, professional, no text"
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=576&nologo=true"

def format_post(entry, source_name):
    title = html.escape(entry.get("title", "Без заголовка")[:100])
    link = entry.get("link", "")
    summary = entry.get("summary", "")
    summary = re.sub("<[^<]+?>", "", summary)
    summary = html.escape(summary[:280]).strip()
    
    text = (
        f"📰 <b>{title}</b>\n\n"
        f"{summary}...\n\n"
        f"🔗 <a href=\"{link}\">Читать</a> | {source_name}"
    )
    return text

def send_to_telegram(text, image_url=None):
    """Отправляет сообщение в Telegram."""
    if image_url:
        caption = text if len(text) <= 1024 else text[:1000] + "..."
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHANNEL_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, data=payload, timeout=10)
            if resp.ok:
                return True
            else:
                print(f"Ошибка фото: {resp.status_code}")
        except Exception as e:
            print(f"Ошибка сети фото: {e}")
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        return resp.ok
    except Exception as e:
        print(f"Ошибка текста: {e}")
        return False

def check_feeds_and_post(seen):
    """Проверяет ленты и постит новости."""
    new_count = 0
    print(f"[{datetime.now()}] Начало проверки. В памяти: {len(seen)} статей")
    
    for feed_url in RSS_FEEDS:
        print(f"Проверяю: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            source_name = feed.feed.get("title", feed_url.split("/")[2])
            entries_count = len(feed.entries)
            print(f"  Найдено: {entries_count} записей")
            
            for entry in feed.entries[:10]:
                link = entry.get("link")
                if not link or link in seen:
                    continue
                if new_count >= MAX_POSTS_PER_CYCLE:
                    break
                
                title = entry.get("title", "Новость")
                print(f"  Публикую: {title[:60]}")
                
                post_text = format_post(entry, source_name)
                image_url = extract_image(entry)
                if not image_url:
                    image_url = generate_ai_image_url(title)
                
                if send_to_telegram(post_text, image_url):
                    print(f"    ✓ OK")
                    seen.add(link)
                    new_count += 1
                    time.sleep(1)
                else:
                    print(f"    ✗ Ошибка")
        except Exception as e:
            print(f"  Ошибка: {type(e).__name__}: {str(e)[:100]}")
    
    print(f"[{datetime.now()}] Готово. Опубликовано: {new_count}")
    return seen

def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Ошибка: не установлены BOT_TOKEN и CHANNEL_ID")
        return
    
    print("🚀 Запуск бота")
    seen = load_seen()
    seen = check_feeds_and_post(seen)
    save_seen(seen)
    print("✅ Всё готово")

if __name__ == "__main__":
    main()
