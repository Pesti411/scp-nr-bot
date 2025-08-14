import os
import discord
import feedparser
import re
import asyncio
import html
import aiohttp
import csv
import datetime
import pytz
import requests
import functools

# Konfiguration
TOKEN = os.getenv("DISCORD_TOKEN")
FEED_URL = "https://q8reci.podcaster.de/scp-deutsch.rss"
SCHEDULE_CSV_URL = "https://docs.google.com/spreadsheets/d/125iGFTWMVKImY_abjac1Lfal78o-dFzQalq6rT_YDxM/export?format=csv"
WORDPRESS_FEED_URL = "https://nurkram.de/wp-json/wp/v2/posts?categories=703&per_page=5"
BLACKLIST_CHANNELS = ["discord-vorschläge", "umfragen", "roleplay", "vertonungsplan", "news"]

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

scp_links = {}
all_episodes = []
schedule = {}

def parse_scp_code(title):
    if not (title.startswith("SCP-") or title.startswith("SKP-")):
        return None
    if title.startswith("SCP-001") or title.startswith("SKP-001"):
        return None
    match = re.match(r"^((?:SCP|SKP)-[^:]+):", title)
    return match.group(1) if match else None

def update_feed():
    global scp_links, all_episodes
    scp_links.clear()
    all_episodes.clear()

    feed = feedparser.parse(FEED_URL)
    for entry in feed.entries:
        title = html.unescape(entry.title.strip())
        link = entry.link.strip()

        all_episodes.append({
            "title": title,
            "link": link
        })

        code = parse_scp_code(title)
        if code:
            scp_links[code.lower()] = {
                "title": title,
                "link": link
            }

def fetch_schedule():
    """Lädt das Google Sheet als CSV und füllt die globale schedule-Variable."""
    global schedule
    schedule.clear()
    try:
        r = requests.get(SCHEDULE_CSV_URL, timeout=10)
        r.raise_for_status()
        reader = csv.reader(r.text.splitlines())
        for row in reader:
            if len(row) >= 4:
                code = row[0].strip().lower()
                date = row[3].strip()
                if code and date:
                    schedule[code] = date
        print(f"[INFO] Schedule erfolgreich geladen: {len(schedule)} Einträge")
    except Exception as e:
        print(f"[ERROR] Fehler beim Laden des Schedules: {e}")

def clean_and_format_text(raw_html_content):
    # HTML-Tags entfernen
    text = re.sub(r'<[^>]+>', '', raw_html_content)
    text = html.unescape(text)
    
    # SCP-Wikidot-Link und Folgetext entfernen
    text = re.split(r'https?://scp-wiki-de\.wikidot\.com.*', text)[0].strip()
    
    # Autor und Übersetzer extrahieren
    autor_match = re.search(r'Autor:\s*([^\n\r]+)', text, re.IGNORECASE)
    übersetzer_match = re.search(r'Übersetzung:\s*([^\n\r]+)', text, re.IGNORECASE)
    
    autor = autor_match.group(1).strip() if autor_match else None
    übersetzer = übersetzer_match.group(1).strip() if übersetzer_match else None
    
    # Autor-/Übersetzer-Zeilen entfernen
    text = re.sub(r'Autor:\s*[^\n\r]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Übersetzung:\s*[^\n\r]+', '', text, flags=re.IGNORECASE)
    
    # Text kürzen und Zeilenumbrüche ersetzen
    text = " ".join(text.split())
    max_len = 300
    if len(text) > max_len:
        text = text[:max_len-3] + "..."
    
    # Discord-Zitat-Formatierung
    result = f"> {text}\n"
    if autor:
        result += f"> Autor: {autor}\n"
    if übersetzer:
        result += f"> Übersetzung: {übersetzer}\n"
    return result

def format_wordpress_post(post):
    title = html.unescape(post['title'])
    content = post['content']
    link = post['link']

    formatted_text = clean_and_format_text(content)

    msg = (
        f":newspaper2: :speaker: **Neue Vertonung von Pesti | {title}**\n"
        f"{formatted_text}"
        f"{link}"
    )
    return msg

@client.event
async def on_ready():
    print(f"[INFO] Eingeloggt als {client.user}")
    update_feed()
    await fetch_schedule()
    client.loop.create_task(refresh_data_loop())
    client.loop.create_task(post_random_episode_loop())

async def refresh_data_loop():
    while True:
        update_feed()
        fetch_schedule()  # keine await mehr
        await asyncio.sleep(3600)

async def post_random_episode_loop():
    await client.wait_until_ready()
    tz = pytz.timezone("Europe/Berlin")
    last_posted_date = None

    while True:
        now = datetime.datetime.now(tz)
        today = now.date()

        target_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
        latest_time = now.replace(hour=13, minute=0, second=0, microsecond=0)

        if last_posted_date != today and target_time <= now < latest_time:
            if not all_episodes:
                print("[WARNUNG] Keine Episoden für Zufallsauswahl vorhanden!")
            else:
                import random
                episode = random.choice(all_episodes)
                channel = discord.utils.get(client.get_all_channels(), name="news")

                if channel:
                    await channel.send(
                        f"🎧 Tägliche Zufalls-Episode:\n**{episode['title']}**\n🔗 **[Hier anhören]({episode['link']})**"
                    )
                    print(f"[INFO] Zufalls-Episode gepostet: {episode['title']}")
                    last_posted_date = today
                else:
                    print("[WARNUNG] Ziel-Channel 'news' nicht gefunden.")

        await asyncio.sleep(300)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if isinstance(message.channel, discord.DMChannel):
        return
    if message.channel.name != "test":
        return

    content_lower = message.content.lower()

    # !wp Befehl (WordPress-Beiträge)
    if content_lower == "!wp":
        loop = asyncio.get_running_loop()
        try:
            r = await loop.run_in_executor(None, functools.partial(requests.get, WORDPRESS_FEED_URL, timeout=10))
            if r.status_code == 200:
                posts = r.json()
                if posts:
                    post = {
                        "title": posts[0]['title']['rendered'],
                        "content": posts[0]['content']['rendered'],
                        "link": posts[0]['link']
                    }
                    msg = format_wordpress_post(post)
                    await message.channel.send(msg)
                else:
                    await message.channel.send("Keine WordPress-Beiträge gefunden.")
            else:
                await message.channel.send("Fehler beim Abrufen der WordPress-Beiträge.")
        except Exception as e:
            await message.channel.send(f"Fehler: {e}")
        return

    # Testpost mit Beispieltext
    if content_lower == "!wp-test":
        dummy_post = {
            "title": "SCP-2291: „Spaßkästchen“",
            "content": (
                "SCP-2291 ist eine Box aus Wellpappe mit einer Kantenlänge von 15cm. "
                "Das Wort „Spaß“ ist auf jeder Seite in riesen Großbuchstaben aufgedruckt. "
                "Autor: arnbobo\nÜbersetzung: Dreamler1433\n"
                "http://scp-wiki-de.wikidot.com/scp-2291 document.createElement('audio'); https://q8reci...."
            ),
            "link": "https://nurkram.de/scp-2291"
        }
        msg = format_wordpress_post(dummy_post)
        await message.channel.send(msg)
        return

    # SCP-Code Erkennung & Reaktion
    found_code = None
    for code in scp_links.keys():
        if code in content_lower:
            found_code = code
            break

    if found_code:
        date = schedule.get(found_code, None)
        post = scp_links.get(found_code)
        if post:
            title = post['title']
            link = post['link']
            response = f"🔎 Gefunden: **{title}**\n🎧 **[Hier anhören]({link})**"
            if date:
                response += f"\n📅 Veröffentlichungsdatum: {date}"
            await message.channel.send(response)
            return

client.run(TOKEN)
