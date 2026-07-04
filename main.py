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
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")  # Опционально для лучших картинок

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
    """Переводит текст на русский через MyMemory API (бесплатно)."""
    if not text or len(text) < 3:
        return text
    
    try:
        # Ограничиваем длину для быстрого перевода
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
                # Убираем лишние символы
                translated = re.sub(r'&#\d+;', '', translated)
                return translated
    except Exception as e:
        print(f"      ⚠️  Ошибка перевода: {e}")
    
    return text

def extract_keywords(title):
    """Извлекает ключевые слова из заголовка."""
    keywords = []
    
    # Ищем важные крипто-терины
    crypto_terms = {
        "bitcoin": "Bitcoin",
        "ethereum": "Ethereum",
        "crypto": "Cryptocurrency",
        "blockchain": "Blockchain",
        "nft": "NFT",
        "defi": "DeFi",
        "dogecoin": "Dogecoin",
        "ripple": "Ripple",
        "solana": "Solana",
        "cardano": "Cardano",
        "polkadot": "Polkadot",
        "trump": "Trump",
        "elon": "Elon Musk",
    }
    
    title_lower = title.lower()
    for term, proper_name in crypto_terms.items():
        if term in title_lower:
            keywords.append(proper_name)
    
    # Если не найдено - берем первое слово заголовка
    if not keywords:
        words = title.split()
        if words:
            keywords.append(words[0])
    
    return keywords[:2]  # Берем максимум 2 ключевых слова

def search_image_duckduckgo(query):
    """Ищет картинку через DuckDuckGo (бесплатно, без ключей)."""
    try:
        print(f"      🔍 Ищу картинку по '{query}'...")
        
        # DuckDuckGo через простой поиск
        search_query = f"{query} cryptocurrency digital art high quality"
        url = "https://duckduckgo.com/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Это простой вариант - ищет через bing images которые доступны
        bing_url = f"https://api.bing.microsoft.com/v7.0/images/search?q={search_query}"
        
        # Альтернатива - поиск через unsplash
        unsplash_url = "https://api.unsplash.com/search/photos"
        unsplash_params = {
            "query": query,
            "per_page": 1,
            "client_id": "2ZlNMUd5Fa8P_0qMSYUg2fsjPJ4g8mHX-f5gHLSn9l0",  # Public client ID
        }
        
        resp = requests.get(unsplash_url, params=unsplash_params, timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get("results"):
                image_url = data["results"][0].get("urls", {}).get("regular")
                if image_url:
                    print(f"      ✅ Картинка найдена на Unsplash!")
                    return image_url
    except Exception as e:
        print(f"      ⚠️  Ошибка поиска картинки: {e}")
    
    return None

def search_image_pixabay(query):
    """Ищет картинку на Pixabay (если есть ключ)."""
    if not PIXABAY_API_KEY:
        return None
    
    try:
        print(f"      🔍 Ищу картинку на Pixabay...")
        
        url = "https://pixabay.com/api/"
        params = {
            "key": PIXABAY_API_KEY,
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

def get_image_for_news(title, original_title):
    """Получает картинку по ключевым словам из заголовка."""
    keywords = extract_keywords(original_title)
    
    for keyword in keywords:
        # Сначала пытаемся Pixabay (если есть ключ)
        image = search_image_pixabay(keyword)
        if image:
            return image
        
        # Потом Unsplash (всегда работает)
        image = search_image_duckduckgo(keyword)
        if image:
            return image
    
    # Если ничего не нашли - ищем просто по "cryptocurrency"
    print(f"      Ищу картинку по 'cryptocurrency'...")
    return search_image_duckduckgo("cryptocurrency")

def format_post(entry):
    """Форматирует пост с переводом на русский."""
    # Оригинальный заголовок для поиска картинки
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
    
    # Сокращаем до первых 5 предложений на английском
    sentences = re.split(r'[.!?]+', summary)
    short_summary = '.'.join(sentences[:5]).strip()
    if not short_summary.endswith('.'):
        short_summary += '.'
    
    # Переводим описание
    short_summary_ru = translate_to_russian(short_summary)
    short_summary_ru = html.escape(short_summary_ru)
    
    # Сохраняем оригинальный заголовок для поиска картинки
    store_data = {
        "original_title": original_title,
        "original_summary": short_summary,
    }
    
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
            print(f"      📤 Отправляю с картинкой...")
            resp = requests.post(url, data=payload, timeout=20)
            if resp.ok:
                success = True
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
                return True
            else:
                print(f"      ❌ Ошибка: {resp.status_code}")
                return False
        except Exception as e:
            print(f"      ❌ Ошибка сети: {e}")
            return False

def check_feeds_and_post(seen):
    """Проверяет RSS ленты и постит новости."""
    new_count = 0
    print(f"\n🔄 Начало проверки новостей")
    print(f"   Ранее опубликовано: {len(seen)}")
    
    for feed_url in RSS_FEEDS:
        source = feed_url.split('/')[2]
        print(f"\n📡 Проверяю: {source}")
        
        try:
            feed = feedparser.parse(feed_url)
            entries_count = len(feed.entries)
            print(f"   Найдено статей: {entries_count}")
            
            for entry in feed.entries[:10]:
                link = entry.get("link")
                
                # Пропускаем если уже публиковали
                if not link or link in seen:
                    continue
                
                # Лимит постов за запуск
                if new_count >= MAX_POSTS_PER_CYCLE:
                    break
                
                original_title = entry.get("title", "Новость")
                print(f"\n   📌 {original_title[:75]}")
                
                # Форматируем пост (переводим на русский)
                print(f"      🌐 Переводу на русский...")
                post_text, orig_title = format_post(entry)
                
                # Ищем картинку по ключевым словам
                print(f"      🎨 Ищу картинку...")
                image_url = get_image_for_news(post_text, orig_title)
                
                if image_url:
                    print(f"      ✅ Картинка найдена!")
                else:
                    print(f"      ⚠️  Картинка не найдена, постю без картинки")
                
                # Отправляем в Telegram
                if send_to_telegram(post_text, image_url):
                    print(f"      ✨ Успешно опубликовано!")
                    seen.add(link)
                    new_count += 1
                else:
                    print(f"      ❌ Не удалось отправить")
                    
        except Exception as e:
            print(f"   ❌ Ошибка при обработке: {type(e).__name__}")
    
    print(f"\n{'='*60}")
    print(f"✅ Проверка завершена!")
    print(f"   Опубликовано новых постов: {new_count}")
    print(f"   Всего в памяти: {len(seen)}")
    print(f"{'='*60}\n")
    
    return seen

def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ ОШИБКА: не установлены BOT_TOKEN и CHANNEL_ID в Railway Variables")
        return
    
    print("\n" + "="*60)
    print("🚀 КРИПТО БОТ (С ПЕРЕВОДОМ И КАРТИНКАМИ) - ЗАПУСК")
    print("="*60)
    print("📍 Особенности:")
    print("   ✅ Автоперевод на русский")
    print("   ✅ Поиск картинок по ключевым словам")
    print("   ✅ 10 источников крипто-новостей")
    print("   ✅ Красивое форматирование")
    print("="*60)
    
    # Загружаем сохраненные статьи
    seen = load_seen()
    
    # Проверяем ленты и постим
    seen = check_feeds_and_post(seen)
    
    # Сохраняем
    save_seen(seen)
    
    print("✅ Бот готов к следующему запуску (через 6 часов)")

if __name__ == "__main__":
    main()
