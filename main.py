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

# Больше источников крипто-новостей
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

MAX_POSTS_PER_CYCLE = 1
SEEN_FILE = "/tmp/seen_articles.json"

def load_seen():
    """Загружает сохраненные статьи (проверка на дубликаты)."""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_seen(seen):
    """Сохраняет статьи (помечает как опубликованные)."""
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen), f)
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def translate_to_russian(text):
    """Переводит текст на русский через MyMemory API (бесплатно)."""
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
        "trading": "Trading",
        "price": "Crypto Price",
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

def search_image_pexels(query):
    """Ищет картинку на Pexels (бесплатно, без ключа)."""
    try:
        print(f"      🔍 Ищу картинку на Pexels: '{query}'")
        
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
                image_url = data["photos"][0].get("src", {}).get("large")
                if image_url:
                    print(f"      ✅ Картинка найдена на Pexels!")
                    return image_url
    except Exception as e:
        print(f"      ⚠️  Ошибка Pexels: {e}")
    
    return None

def search_image_unsplash(query):
    """Ищет картинку на Unsplash (бесплатно)."""
    try:
        print(f"      🔍 Ищу картинку на Unsplash: '{query}'")
        
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
                    print(f"      ✅ Картинка найдена на Unsplash!")
                    return image_url
    except Exception as e:
        print(f"      ⚠️  Ошибка Unsplash: {e}")
    
    return None

def search_image_pixabay(query):
    """Ищет картинку на Pixabay (бесплатно без ключа)."""
    try:
        print(f"      🔍 Ищу картинку на Pixabay: '{query}'")
        
        url = "https://pixabay.com/api/"
        params = {
            "key": "43648625-3eadc0819d3a5c3e89fbe1cf5",  # Public key для демо
            "q": query,
            "image_type": "photo",
            "per_page": 1,
            "order": "popular",
        }
        
        resp = requests.get(url, params=params, timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get("hits"):
                image_url = data["hits"][0].get("webformatURL")
                if image_url:
                    print(f"      ✅ Картинка найдена на Pixabay!")
                    return image_url
    except Exception as e:
        print(f"      ⚠️  Ошибка Pixabay: {e}")
    
    return None

def get_fallback_image():
    """Возвращает дефолтную картинку крипто-тематики."""
    fallback_images = [
        "https://images.unsplash.com/photo-1518546305927-30bbc8c9c8ff?w=1024&q=80",  # Bitcoin
        "https://images.unsplash.com/photo-1621761191007-11a2b0361e6f?w=1024&q=80",  # Ethereum
        "https://images.unsplash.com/photo-1639762681033-6461ffad8d80?w=1024&q=80",  # Crypto chart
        "https://images.unsplash.com/photo-1516321318423-f06f70d504f0?w=1024&q=80",  # Trading
    ]
    import random
    return random.choice(fallback_images)

def get_image_for_news(title):
    """Получает картинку по ключевым словам из заголовка."""
    keywords = extract_keywords(title)
    
    print(f"      🎯 Ключевые слова: {keywords}")
    
    for keyword in keywords:
        # Попытка 1: Pexels
        image = search_image_pexels(keyword)
        if image:
            return image
        time.sleep(0.5)
        
        # Попытка 2: Unsplash
        image = search_image_unsplash(keyword)
        if image:
            return image
        time.sleep(0.5)
        
        # Попытка 3: Pixabay
        image = search_image_pixabay(keyword)
        if image:
            return image
        time.sleep(0.5)
    
    # Если ничего не нашли - ищем по "cryptocurrency"
    print(f"      🔄 Ищу по 'cryptocurrency'...")
    image = search_image_pexels("cryptocurrency")
    if image:
        return image
    
    image = search_image_unsplash("cryptocurrency")
    if image:
        return image
    
    image = search_image_pixabay("cryptocurrency")
    if image:
        return image
    
    # Если совсем ничего не помогло - берем дефолт
    print(f"      🎲 Использую дефолтную картинку")
    return get_fallback_image()

def format_post(entry):
    """Форматирует пост с переводом на русский."""
    original_title = entry.get("title", "Новость")
    
    # Переводим заголовок
    title_ru = translate_to_russian(original_title)
    title_ru = html.escape(title_ru)
    
    link = entry.get("link", "")
    
    # Получаем текст
    summary = entry.get("summary", "")
    if not summary:
        summary = entry.get("description", "")
    if not summary:
        summary = entry.get("content", "")
    
    # Очищаем HTML-теги
    summary = re.sub("<[^<]+?>", "", summary)
    summary = re.sub("&[a-z]+;", "", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    
    # Сокращаем до первых 5 предложений
    sentences = re.split(r'[.!?]+', summary)
    short_summary = '.'.join(sentences[:5]).strip()
    if not short_summary.endswith('.'):
        short_summary += '.'
    
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
    
    # Если есть картинка
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
            print(f"      📤 Отправляю с картинкой: {image_url[:60]}...")
            resp = requests.post(url, data=payload, timeout=20)
            if resp.ok:
                success = True
                print(f"      ✅ Картинка отправлена!")
                # Если текст обрезан, отправляем остаток
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
            else:
                print(f"      ⚠️  Ошибка отправки фото: {resp.status_code}")
                print(f"      📝 Ответ: {resp.text[:200]}")
        except Exception as e:
            print(f"      ⚠️  Ошибка: {e}")
    
    # Отправляем текстом (если нет картинки или она не сработала)
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
            else:
                print(f"      ❌ Ошибка: {resp.status_code}")
                return False
        except Exception as e:
            print(f"      ❌ Ошибка сети: {e}")
            return False

def check_feeds_and_post(seen):
    """Проверяет RSS ленты и постит ТОЛЬКО новые новости."""
    new_count = 0
    print(f"\n🔄 Начало проверки новостей")
    print(f"   📊 Ранее опубликовано: {len(seen)} статей")
    print(f"   🚫 Старые посты НЕ будут опубликованы повторно")
    
    for feed_url in RSS_FEEDS:
        source = feed_url.split('/')[2]
        print(f"\n📡 Проверяю: {source}")
        
        try:
            feed = feedparser.parse(feed_url)
            entries_count = len(feed.entries)
            print(f"   Найдено статей: {entries_count}")
            
            for entry in feed.entries[:10]:
                link = entry.get("link")
                
                # ✅ ПРОВЕРКА НА ДУБЛИКАТЫ: пропускаем если уже публиковали
                if not link:
                    print(f"      ⏭️  Нет ссылки, пропускаю")
                    continue
                
                if link in seen:
                    print(f"      ⏭️  Уже опубликовано, пропускаю")
                    continue
                
                # Лимит постов за запуск
                if new_count >= MAX_POSTS_PER_CYCLE:
                    print(f"      ⏹️  Лимит постов достигнут")
                    break
                
                original_title = entry.get("title", "Новость")
                print(f"\n   ✨ НОВАЯ СТАТЬЯ: {original_title[:70]}")
                
                # Форматируем пост (переводим на русский)
                print(f"      🌐 Перевожу на русский...")
                post_text, orig_title = format_post(entry)
                
                # Ищем картинку
                print(f"      🎨 Ищу картинку...")
                image_url = get_image_for_news(orig_title)
                
                # Отправляем в Telegram
                if send_to_telegram(post_text, image_url):
                    print(f"      ✨ УСПЕШНО ОПУБЛИКОВАНО!")
                    seen.add(link)  # Помечаем как опубликованное
                    new_count += 1
                else:
                    print(f"      ❌ Не удалось отправить")
                    
        except Exception as e:
            print(f"   ❌ Ошибка при обработке: {type(e).__name__}: {e}")
    
    print(f"\n{'='*60}")
    print(f"✅ Проверка завершена!")
    print(f"   ✨ Опубликовано новых: {new_count}")
    print(f"   📊 Всего сохранено: {len(seen)}")
    print(f"{'='*60}\n")
    
    return seen

def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ ОШИБКА: не установлены BOT_TOKEN и CHANNEL_ID в Railway Variables")
        return
    
    print("\n" + "="*60)
    print("🚀 КРИПТО БОТ - ЗАПУСК")
    print("="*60)
    print("📍 Особенности:")
    print("   ✅ Автоперевод на русский")
    print("   ✅ Умный поиск картинок (Pexels, Unsplash, Pixabay)")
    print("   ✅ Проверка дубликатов (старые посты не повторяются)")
    print("   ✅ 10 источников крипто-новостей")
    print("   ✅ Красивое форматирование")
    print("="*60)
    
    # Загружаем сохраненные статьи (проверка дубликатов)
    seen = load_seen()
    
    # Проверяем ленты и постим ТОЛЬКО новые
    seen = check_feeds_and_post(seen)
    
    # Сохраняем (чтобы не повторять эти посты)
    save_seen(seen)
    
    print("✅ Бот готов к следующему запуску (через 6 часов)")

if __name__ == "__main__":
    main()
