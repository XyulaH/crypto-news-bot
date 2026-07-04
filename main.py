import feedparser
import requests
import time
import json
import os
import html
import re
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
    """Достаёт картинку из RSS - пытается разные способы."""
    # Способ 1: media_content 
    if hasattr(entry, "media_content") and entry.media_content:
        try:
            url = entry.media_content[0].get("url")
            if url and url.startswith("http"):
                return url
        except:
            pass
    
    # Способ 2: media_thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        try:
            url = entry.media_thumbnail[0].get("url")
            if url and url.startswith("http"):
                return url
        except:
            pass
    
    # Способ 3: image в summary
    summary_html = entry.get("summary", "") or entry.get("description", "") or ""
    match = re.search(r'<img[^>]+src="([^"]+)"', summary_html)
    if match:
        url = match.group(1)
        if url.startswith("http"):
            return url
    
    # Способ 4: og:image или другие meta-теги в summary
    match = re.search(r'(https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp))', summary_html, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None

def format_post(entry, source_name):
    title = html.escape(entry.get("title", "Без заголовка"))
    link = entry.get("link", "")
    
    # Пытаемся получить полный контент
    summary = entry.get("summary", "")
    if not summary:
        summary = entry.get("description", "")
    if not summary:
        summary = entry.get("content", "")
    
    # Убираем HTML-теги и HTML-сущности
    summary = re.sub("<[^<]+?>", "", summary)
    summary = re.sub("&nbsp;", " ", summary)
    summary = re.sub("&[a-z]+;", "", summary)
    summary = re.sub("\s+", " ", summary)  # Убираем множественные пробелы
    summary = html.escape(summary[:2000]).strip()  # Максимум 2000 символов
    
    text = (
        f"📰 <b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"🔗 <a href=\"{link}\">Читать полностью на источнике</a>\n\n"
        f"📌 By Trading | По Торговле"
    )
    return text

def send_to_telegram(text, image_url=None):
    """Отправляет сообщение в Telegram с картинкой и текстом."""
    success = False
    
    # Если есть картинка — отправляем её первой
    if image_url and image_url.startswith("http"):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        # Для подписи берем только первую часть если текст длинный
        caption = text[:1024] if len(text) > 1024 else text
        payload = {
            "chat_id": CHANNEL_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, data=payload, timeout=15)
            if resp.ok:
                success = True
                # Если текст был обрезан, отправляем остаток отдельно
                if len(text) > 1024:
                    time.sleep(1)
                    url2 = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    payload2 = {
                        "chat_id": CHANNEL_ID,
                        "text": text[1024:],
                        "parse_mode": "HTML",
                    }
                    requests.post(url2, data=payload2, timeout=15)
                return success
        except Exception as e:
            print(f"    Ошибка при отправке фото: {e}")
    
    # Если нет картинки или она не сработала — отправляем текст
    if not success:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, data=payload, timeout=15)
            return resp.ok
        except Exception as e:
            print(f"    Ошибка: {e}")
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
                image_url = extract_image(entry)  # Только из RSS, генерацию не делаем
                
                if send_to_telegram(post_text, image_url):
                    print(f"    ✓ OK")
                    if image_url:
                        print(f"    📷 С картинкой")
                    seen.add(link)
                    new_count += 1
                    time.sleep(21600)  # 8 секунд между постами, чтобы они приходили по одному
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
