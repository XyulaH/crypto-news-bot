import feedparser
import requests
import time
import json
import os
import html
import re
from datetime import datetime

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY", "")

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=cryptocurrency",
    "https://feeds.bloomberg.com/markets/cryptocurrency.rss",
    "https://bitcoinmagazine.com/feed",
    "https://www.coindesk.com/feed/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]

MAX_POSTS_PER_CYCLE = 1  # По одной новости за запуск (остальные в следующий раз)
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

def analyze_text_with_claude(title, text):
    """Анализирует статью через Claude API и делает краткий вывод."""
    if not CLAUDE_API_KEY:
        print(f"      ⚠️  Claude API не настроен")
        return shorten_text_simple(text)
    
    try:
        prompt = f"""Ты - аналитик криптовалютных новостей. Проанализируй эту новость и напиши краткий вывод на русском (5-7 предложений).

Заголовок: {title}

Текст: {text[:1500]}

Требования:
- Вывод информативный и ясный
- Только ключевые моменты
- На русском языке
- Без излишних деталей"""

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-opus-4-1",
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.ok:
            data = resp.json()
            if data.get("content"):
                summary = data["content"][0].get("text", "")
                return summary.strip()
        else:
            print(f"      ⚠️  Claude ошибка {resp.status_code}")
    except Exception as e:
        print(f"      ⚠️  Ошибка Claude: {e}")
    
    return shorten_text_simple(text)

def shorten_text_simple(text):
    """Сокращение текста если API недоступен."""
    sentences = re.split(r'[.!?]+', text)
    summary = '.'.join(sentences[:6]).strip()
    if not summary.endswith('.'):
        summary += '.'
    return summary

def generate_image_with_replicate(title):
    """Генерирует картинку через Replicate API."""
    if not REPLICATE_API_KEY:
        print(f"      ⚠️  Replicate API не настроен")
        return None
    
    try:
        prompt = f"Professional cryptocurrency news illustration about {title[:50]}, digital art, high quality, modern design, no text, 1024x576"
        
        url = "https://api.replicate.com/v1/predictions"
        headers = {
            "Authorization": f"Token {REPLICATE_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "version": "db21e45d3f7023abc9db3d3d",
            "input": {
                "prompt": prompt,
                "num_outputs": 1,
                "height": 576,
                "width": 1024,
                "num_inference_steps": 25,
            },
        }
        
        print(f"      ⏳ Генерирую картинку...")
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if resp.ok:
            data = resp.json()
            prediction_id = data.get("id")
            
            # Ждем завершения генерации
            for attempt in range(40):
                time.sleep(1.5)
                check_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
                check_resp = requests.get(check_url, headers=headers, timeout=10)
                
                if check_resp.ok:
                    check_data = check_resp.json()
                    if check_data.get("status") == "succeeded":
                        output = check_data.get("output")
                        if output:
                            image_url = output[0] if isinstance(output, list) else output
                            if image_url and image_url.startswith("http"):
                                print(f"      ✅ Картинка готова!")
                                return image_url
                    elif check_data.get("status") == "failed":
                        print(f"      ❌ Генерация не удалась")
                        return None
        else:
            print(f"      ❌ Replicate ошибка {resp.status_code}")
    except Exception as e:
        print(f"      ❌ Ошибка генерации: {e}")
    
    return None

def extract_image(entry):
    """Достает картинку из RSS."""
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
    
    # Способ 3: картинка в summary
    summary_html = entry.get("summary", "") or entry.get("description", "") or ""
    match = re.search(r'<img[^>]+src="([^"]+)"', summary_html)
    if match:
        url = match.group(1)
        if url.startswith("http"):
            return url
    
    # Способ 4: картинка по расширению
    match = re.search(r'(https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp))', summary_html, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None

def format_post(entry, source_name):
    """Форматирует пост с заголовком, анализом и ссылкой."""
    title = html.escape(entry.get("title", "Без заголовка"))
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
    
    # Анализируем текст
    print(f"      📝 Анализирую новость...")
    analysis = analyze_text_with_claude(title, summary)
    
    text = (
        f"📰 <b>{title}</b>\n\n"
        f"<b>📊 Анализ:</b>\n"
        f"{analysis}\n\n"
        f"🔗 <a href=\"{link}\">Читать полностью</a>\n\n"
        f"📌 By Trading | По Торговле"
    )
    return text

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
                print(f"      ⚠️  Ошибка отправки: {resp.status_code}")
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
                
                title = entry.get("title", "Новость")
                print(f"\n   📌 {title[:75]}")
                
                # Форматируем пост
                post_text = format_post(entry, source)
                
                # Получаем или генерируем картинку
                print(f"      🎨 Ищу картинку...")
                image_url = extract_image(entry)
                
                if not image_url:
                    print(f"      Картинки в RSS нет")
                    image_url = generate_image_with_replicate(title)
                else:
                    print(f"      ✅ Картинка найдена в RSS")
                
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
    print("🚀 КРИПТО БОТ - ЗАПУСК")
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
