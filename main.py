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

tasks_started = False

# Konfiguration
TOKEN = os.getenv("DISCORD_TOKEN")
FEED_URL = "https://q8reci.podcaster.de/scp-deutsch.rss"
SCHEDULE_CSV_URL = "https://docs.google.com/spreadsheets/d/125iGFTWMVKImY_abjac1Lfal78o-dFzQalq6rT_YDxM/export?format=csv"
WORDPRESS_FEED_URL = "https://nurkram.de/wp-json/wp/v2/posts?categories=703&per_page=5"
BLACKLIST_CHANNELS = ["discord-vorschläge", "umfragen", "roleplay", "vertonungsplan", "news"]

SPECIAL_CODES = {
    "SCP-001": {
        "response": (
            "**SCP-001 ist besonders – es gibt mehrere Versionen!**\n"
            "🔗 Übersicht aller verfügbarer Vertonungen:\n"
            "- [SCP-001 – S. D. Lockes Vorschlag: „Wenn der Tag anbricht“](https://nurkram.de/scp-001-s-d-locke)\n"
            "- [SCP-001: CODE NAME: „Tufto – Der Scarlet King“](https://nurkram.de/scp-001-tufto)\n"
            "- [SCP-001: CODE NAME: „Tanhony II – Heult der Schwarze Mond?“](https://nurkram.de/scp-001-tanhony-ii)\n"
            "- [SCP-001: CODE NAME: „Dr. Clef – Der Torwächter“](https://nurkram.de/scp-001-dr-clef)\n"
            "- [SCP-001: CODE NAME: „Wrong – Der Konsens“](https://nurkram.de/scp-001-wrong)\n"
            "- [SCP-001: CODE NAME: „Djoric/Dmatix – Sechsunddreißig“](https://nurkram.de/scp-001-djoric-dmatix)\n"
            "- [SCP-001: CODE NAME: „Spike Brennan – Gottes blinder Fleck“](https://nurkram.de/scp-001-spike-brennan)\n"
            "- [SCP-001-IT / GRAF: „Der Drache der Offenbarung“](https://nurkram.de/scp-001-it-graf)\n"
            "- [SCP-001-DE: CODE NAME: „Dr. Ore – Der höchste Konflikt“](https://nurkram.de/scp-001-de-dr-ore)\n"
            "- [SCP-001-DE: CODE NAME: „Dr. Schwarz – V9 Erreger“](https://nurkram.de/scp-001-de-dr-schwarz)\n"
            "- [SCP-001-DE: CODE NAME: „Dr Leo – Trabant / Ende einer Ära“](https://nurkram.de/scp-001-de-dr-leo)\n"
            "- [SCP-001-DE: CODE NAME: „Thielemann – Wir stehen über Justitia“](https://nurkram.de/scp-001-de-thielemann)\n"
            "- [SCP-001-KO: CODE NAME: „L.H. Sein – Durch Menschen“](https://nurkram.de/scp-001-ko-lh-sein)\n"
            "- [SCP-LA-001: CODE NAME: „Fulmen – Die Sense“](https://nurkram.de/scp-la-001-sense)\n"
            "- [SCP-LA-001: CODE NAME: „Praetor Bold – Sprache“](https://nurkram.de/scp-la-001-sprache)\n"
            ":bulb: SCP-001-DE: CODE NAME: „Abyssus - Abgrund der Realität“ *ist bereits geplant, ich bitte um Geduld*\n"
        )
    },
    "SCP-6500": {
        "response": f"🔎 Gefunden: **SCP-6500: „Unvermeidbar“**\n🎧 **[Hier anhören](https://nurkram.de/scp-6500)**"
    },
    "SCP-1730": {
        "response": f"🔎 Gefunden: **SCP-1730: „Was ist mit Standort-13 passiert?“**\n🎧 **[Hier anhören](https://nurkram.de/scp-1730)**"
    }
}

CUSTOM_TRIGGERS = {
    "scarlet king": f"🔎 Gefunden: **SCP-001: CODE NAME: „Tufto – Der Scarlet King“**\n🎧 **[Hier anhören](https://nurkram.de/scp-001-tufto)**",
    "scharlach-rot": f"🔎 Gefunden: **SCP-001: CODE NAME: „Tufto – Der Scarlet King“**\n🎧 **[Hier anhören](https://nurkram.de/scp-001-tufto)**",
    "scharlach-roter": f"🔎 Gefunden: **SCP-001: CODE NAME: „Tufto – Der Scarlet King“**\n🎧 **[Hier anhören](https://nurkram.de/scp-001-tufto)**",
    "shy guy": f"🔎 Gefunden: **SCP-096: „Der Schüchterne Mann“**\n🎧 **[Hier anhören](https://nurkram.de/scp-096)**",
    "peanut": f"🔎 Gefunden: **SCP-173: „Die Statue“**\n🎧 **[Hier anhören](https://nurkram.de/scp-173)**"
}

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

async def fetch_schedule():
    global schedule
    schedule.clear()
    async with aiohttp.ClientSession() as session:
        async with session.get(SCHEDULE_CSV_URL) as resp:
            if resp.status == 200:
                text = await resp.text()
                reader = csv.reader(text.splitlines())
                for row in reader:
                    if len(row) >= 4:
                        code = row[0].strip().lower()
                        date = row[3].strip()
                        if code and date:
                            schedule[code] = date
            else:
                print(f"[WARNUNG] CSV konnte nicht geladen werden, Status: {resp.status}")


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
        await fetch_schedule()
        await asyncio.sleep(3600)  # jede Stunde

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
    if message.author.bot or message.channel.name in BLACKLIST_CHANNELS:
        return

    content_raw = message.content
    content_lower = content_raw.lower()
    content_upper = content_raw.upper()

    print(f"[DEBUG] Neue Nachricht: {content_raw}")

    # Eigene Trigger
    for trigger, response in CUSTOM_TRIGGERS.items():
        if trigger in content_lower:
            print(f"[DEBUG] Eigener Trigger '{trigger}' gefunden")
            await message.channel.send(response)
            return

    # Spezialcodes
    for special_code, info in SPECIAL_CODES.items():
        pattern = r'(?<![\w-])' + re.escape(special_code) + r'(?![\w-])'
        if re.search(pattern, content_upper, re.IGNORECASE):
            print(f"[DEBUG] Spezialcode '{special_code}' gefunden")
            await message.channel.send(info["response"], suppress_embeds=True)
            return

    # 1. SCP-Links zuerst prüfen
    for code in scp_links.keys():
        pattern = r'(?<![\w-])' + re.escape(code.upper()) + r'(?![\w-])'
        if re.search(pattern, content_upper, re.IGNORECASE):
            print(f"[DEBUG] Code '{code}' im Feed gefunden")
            data = scp_links[code]
            response = f"🔎 Gefunden: **{data['title']}**\n🎧 **[Hier anhören]({data['link']})**"
            if code in schedule:
                response += f"\n📅 Veröffentlichungsdatum laut Plan: {schedule[code]}"
            await message.channel.send(response)
            return

    # 2. Codes nur im Plan prüfen
    for code in schedule.keys():
        if code not in scp_links:
            pattern = r'(?<![\w-])' + re.escape(code.upper()) + r'(?![\w-])'
            if re.search(pattern, content_upper, re.IGNORECASE):
                print(f"[DEBUG] Code '{code}' nur im Plan gefunden")
                await message.channel.send(
                    f"📅 **{code.upper()}** ist laut Plan für {schedule[code]} vorgesehen."
                )
                return

    # Spezieller Test-Command (WP-Test)
    if content_lower == "!wp-test":
        dummy_post = {
            "title": "SCP-2291: „Spaßkästchen“",
            "content": (
                "SCP-2291 ist eine Box aus Wellpappe mit einer Kantenlänge von 15cm. "
                "Das Wort „Spaß“ ist auf jeder Seite in riesen Großbuchstaben aufgedruckt. "
                "Autor: arnbobo\nÜbersetzung: Dreamler1433"
            ),
            "link": "https://nurkram.de/scp-2291"
        }
        msg = format_wordpress_post(dummy_post)
        await message.channel.send(msg)
        return

    # SCP-Code Erkennung & Reaktion (zusätzliche Prüfung)
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

    print("[DEBUG] Keine Codes gefunden.")
    await client.process_commands(message)

async def post_latest_wordpress_post_once():
    print("[INFO] Starte einmaliges Posten des neuesten Wordpress-Beitrags ...")
    
@client.event
async def on_connect():
    global tasks_started
    print(f"[INFO] Bot verbunden mit Discord.")

    if not tasks_started:
        print("[INFO] Starte Initialdaten-Aktualisierung und Hintergrund-Tasks ...")
        update_feed()             
        await fetch_schedule()

        client.loop.create_task(refresh_data_loop())
        client.loop.create_task(post_random_episode_loop())
        client.loop.create_task(post_latest_wordpress_post_once())

        tasks_started = True

client.run(TOKEN)
