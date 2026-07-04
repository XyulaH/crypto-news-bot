import feedparser
import requests
import time
import json
import os
import html
import re

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

# RSS ленты
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=cryptocurrency",
    "https://news.google.com/rss/search?q=bitcoin",
    "https://news.google.com/rss/search?q=ethereum",
    "https://feeds.bloomberg.com/markets/cryptocurrency.rss",
    "https://bitcoinmagazine.com/feed",
    "https://www.coindesk.com/feed/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblockcrypto.com/rss.xml",
    "https://tokenizedhq.com/feed/",
]

MAX_POSTS_PER_CYCLE = 1  # ТОЛЬКО 1 пост за запуск!
SEEN_FILE = "/tmp/seen_articles.json"

def load_seen():
    """Загружает сохраненные статьи."""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_seen(seen):
    """Сохраняет статьи."""
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen), f)
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def translate_to_russian(text):
    """Переводит текст на русский."""
    if not text or len(text) < 3:
        return text
    
    try:
        text_to_translate = text[:500]
        url = f"https://api.mymemory.translated.net/get"
        params = {
            "q": text_to_translate,
            "langpair": "en|ru",
        }
        
        resp = requests.get(url, params=params, timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get("responseStatus") == 200:
                translated = data["responseData"]["translatedText"]
                translated = re.sub(r'&#\d+;', '', translated)
                return translated
    except Exception as e:
        print(f"      ⚠️  Ошибка перевода: {e}")
    
    return text

def extract_keywords(title):
    """Извлекает ключевые слова для поиска картинки."""
    keywords = []
    
    crypto_terms = {
        "bitcoin": "Bitcoin",
        "ethereum": "Ethereum",
        "crypto": "Cryptocurrency",
        "blockchain": "Blockchain",
        "nft": "NFT",
        "defi": "DeFi",
        "dogecoin": "Dogecoin",
        "ripple": "Ripple XRP",
        "solana": "Solana",
        "cardano": "Cardano",
        "polkadot": "Polkadot",
        "trump": "Donald Trump",
        "elon": "Elon Musk",
        "sec": "SEC",
    }
    
    title_lower = title.lower()
    for term, proper_name in crypto_terms.items():
        if term in title_lower:
            keywords.append(proper_name)
    
    if not keywords:
        words = title.split()
        if words:
            keywords.append(words[0])
    
    return keywords[:2]

def search_image_unsplash(query):
    """Ищет картинку на Unsplash."""
    try:
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": 1,
            "client_id": "2ZlNMUd5Fa8P_0qMSYUg2fsjPJ4g8mHX-f5gHLSn9l0",
        }
        
        resp = requests.get(url, params=params, timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get("results"):
                image_url = data["results"][0].get("urls", {}).get("regular")
                if image_url:
                    return image_url
    except:
        pass
    
    return None

def search_image_pexels(query):
    """Ищет картинку на Pexels."""
    try:
        url = "https://api.pexels.com/v1/search"
        headers = {
            "Authorization": "563492ad6f91700001000001a9c2c5f2ed844c3f9e33a1c09a22a77e"
        }
        params = {
            "query": query,
            "per_page": 1,
        }
        
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get("photos"):
                return data["photos"][0].get("src", {}).get("large")
    except:
        pass
    
    return None

def get_fallback_image():
    """Дефолтная картинка."""
    fallback_images = [
        "https://images.unsplash.com/photo-1518546305927-30bbc8c9c8ff?w=1024&q=80",
        "https://images.unsplash.com/photo-1621761191007-11a2b0361e6f?w=1024&q=80",
        "https://images.unsplash.com/photo-1639762681033-6461ffad8d80?w=1024&q=80",
        "https://images.unsplash.com/photo-1516321318423-f06f70d504f0?w=1024&q=80",
        "https://images.unsplash.com/photo-1611532736579-6b16e2b50449?w=1024&q=80",
    ]
    import random
    return random.choice(fallback_images)

def extract_image(entry):
    """Достает картинку из RSS - много способов."""
    
    # media_content
    if hasattr(entry, "media_content") and entry.media_content:
        try:
            url = entry.media_content[0].get("url")
            if url and url.startswith("http") and len(url) > 15:
                return url
        except:
            pass
    
    # media_thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        try:
            url = entry.media_thumbnail[0].get("url")
            if url and url.startswith("http") and len(url) > 15:
                return url
        except:
            pass
    
    # links
    if hasattr(entry, "links"):
        for link in entry.links:
            try:
                if link.get("type", "").startswith("image"):
                    url = link.get("href")
                    if url and url.startswith("http"):
                        return url
            except:
                pass
    
    # img tag в summary
    summary = entry.get("summary", "") or entry.get("description", "") or ""
    if summary:
        match = re.search(r'<img[^>]+src="([^"]+)"', summary)
        if match:
            url = match.group(1)
            if url.startswith("http"):
                return url
    
    # картинка по расширению
    if summary:
        match = re.search(r'(https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp|svg))', summary, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def get_image_for_news(title):
    """Получает картинку для конкретной новости."""
    keywords = extract_keywords(title)
    
    print(f"      🎯 Ключевые слова: {keywords}")
    
    # Пытаемся найти уникальную картинку
    for keyword in keywords:
        # Unsplash
        image = search_image_unsplash(keyword)
        if image:
            print(f"      ✅ Картинка найдена на Unsplash")
            return image
        time.sleep(0.3)
        
        # Pexels
        image = search_image_pexels(keyword)
        if image:
            print(f"      ✅ Картинка найдена на Pexels")
            return image
        time.sleep(0.3)
    
    # По "cryptocurrency" если ничего не нашли
    image = search_image_unsplash("cryptocurrency")
    if image:
        print(f"      ✅ Картинка найдена (криптовалюта)")
        return image
    
    image = search_image_pexels("cryptocurrency")
    if image:
        print(f"      ✅ Картинка найдена (криптовалюта Pexels)")
        return image
    
    # Дефолт
    print(f"      🎲 Использую случайную дефолт-картинку")
    return get_fallback_image()

def format_post(entry):
    """Форматирует пост с достаточным количеством текста."""
    original_title = entry.get("title", "Новость")
    
    # Переводим заголовок
    title_ru = translate_to_russian(original_title)
    title_ru = html.escape(title_ru)
    
    link = entry.get("link", "")
    
    # Получаем МАКСИМУМ текста
    summary = entry.get("summary", "")
    if not summary:
        summary = entry.get("description", "")
    if not summary:
        summary = entry.get("content", "")
    
    # Очищаем HTML-теги
    summary = re.sub("<[^<]+?>", "", summary)
    summary = re.sub("&[a-z]+;", "", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    
    # Берем больше текста (первые 8 предложений вместо 5)
    sentences = re.split(r'[.!?]+', summary)
    short_summary = '.'.join(sentences[:8]).strip()
    if short_summary and not short_summary.endswith('.'):
        short_summary += '.'
    
    # Если текст очень короткий - берем всё
    if len(short_summary) < 100:
        short_summary = summary[:300]
    
    # Переводим описание
    short_summary_ru = translate_to_russian(short_summary)
    short_summary_ru = html.escape(short_summary_ru)
    
    text = (
        f"📰 <b>{title_ru}</b>\n\n"
        f"{short_summary_ru}\n\n"
        f"🔗 <a href=\"{link}\">Читать оригинал</a>\n\n"
        f"📌 By Trading | По Торговле"
    )
    return text, original_title

def send_to_telegram(text, image_url=None):
    """Отправляет пост в Telegram."""
    success = False
    
    # С картинкой
    if image_url and image_url.startswith("http"):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        caption = text[:1024] if len(text) > 1024 else text
        payload = {
            "chat_id": CHANNEL_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
        }
        try:
            print(f"      📤 Отправляю с картинкой...")
            resp = requests.post(url, data=payload, timeout=20)
            if resp.ok:
                success = True
                print(f"      ✅ Картинка отправлена!")
                if len(text) > 1024:
                    time.sleep(1)
                    url2 = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    payload2 = {
                        "chat_id": CHANNEL_ID,
                        "text": text[1024:],
                        "parse_mode": "HTML",
                    }
                    requests.post(url2, data=payload2, timeout=20)
                return success
        except Exception as e:
            print(f"      ⚠️  Ошибка: {e}")
    
    # Текстом
    if not success:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            print(f"      📤 Отправляю текст...")
            resp = requests.post(url, data=payload, timeout=20)
            if resp.ok:
                print(f"      ✅ Текст отправлен!")
                return True
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
    
    return False

def check_feeds_and_post(seen):
    """Проверяет RSS и постит только НОВЫЕ новости."""
    new_count = 0
    print(f"\n🔄 Начало проверки новостей")
    print(f"   📊 Ранее опубликовано: {len(seen)} статей")
    
    for feed_url in RSS_FEEDS:
        source = feed_url.split('/')[2]
        print(f"\n📡 Проверяю: {source}")
        
        try:
            feed = feedparser.parse(feed_url)
            entries_count = len(feed.entries)
            print(f"   Найдено статей: {entries_count}")
            
            for entry in feed.entries[:15]:
                link = entry.get("link")
                
                if not link or link in seen:
                    if link in seen:
                        print(f"      ⏭️  Уже опубликовано")
                    continue
                
                if new_count >= MAX_POSTS_PER_CYCLE:
                    print(f"      ⏹️  Лимит (1 пост) достигнут")
                    break
                
                original_title = entry.get("title", "Новость")
                print(f"\n   ✨ НОВАЯ: {original_title[:70]}")
                
                # Форматируем
                print(f"      🌐 Перевожу...")
                post_text, orig_title = format_post(entry)
                
                # Ищем картинку ДЛЯ ЭТОЙ конкретной новости
                print(f"      🎨 Ищу уникальную картинку для этой новости...")
                image_url = extract_image(entry)  # Сначала из RSS
                if not image_url:
                    image_url = get_image_for_news(orig_title)  # Потом ищем по ключевым словам
                
                # Отправляем
                if send_to_telegram(post_text, image_url):
                    print(f"      ✨ ОПУБЛИКОВАНО!")
                    seen.add(link)
                    new_count += 1
                    
        except Exception as e:
            print(f"   ❌ Ошибка: {type(e).__name__}")
    
    print(f"\n{'='*60}")
    print(f"✅ Готово! Опубликовано: {new_count}, Всего сохранено: {len(seen)}")
    print(f"{'='*60}\n")
    
    return seen

def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Нет BOT_TOKEN или CHANNEL_ID")
        return
    
    print("\n" + "="*60)
    print("🚀 КРИПТО БОТ")
    print("="*60)
    
    seen = load_seen()
    seen = check_feeds_and_post(seen)
    save_seen(seen)
    
    print("✅ Готов к следующему запуску (6 часов)")

if __name__ == "__main__":
    main()
