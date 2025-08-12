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

# --- Konfiguration ---
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

# --- Discord-Intents ---
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

scp_links = {}      # Nur Folgen mit SCP-/SKP-Code
all_episodes = []   # Alle Folgen im Feed
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
            text = await resp.text()
    reader = csv.reader(text.splitlines())
    for row in reader:
        if len(row) >= 4:
            code = row[0].strip().lower()
            date = row[3].strip()
            if code and date:
                schedule[code] = date

# --- Wordpress-Feed abrufen und formatieren ---
async def fetch_wordpress_posts():
    async with aiohttp.ClientSession() as session:
        async with session.get(WORDPRESS_FEED_URL) as resp:
            if resp.status != 200:
                print(f"[ERROR] Wordpress-Feed konnte nicht geladen werden: Status {resp.status}")
                return None
            data = await resp.json()

    if not data:
        print("[TEST] Kein Wordpress-Post gefunden")
        return None

    newest = data[0]

    title = newest.get("title", {}).get("rendered", "Kein Titel")
    content = newest.get("content", {}).get("rendered", "")
    link = newest.get("link", "")

    return {
        "title": title,
        "content": content,
        "link": link
    }

def format_wordpress_post(post):
    # HTML-Tags entfernen, einfach und schnell
    text = re.sub(r'<[^>]+>', '', post['content'])
    text = text.strip().replace('\n', ' ')
    # Optional: Text auf 300 Zeichen kürzen
    if len(text) > 300:
        text = text[:297] + "..."

    msg = (
        f":newspaper2: :speaker: **Neue Vertonung von Pesti | {post['title']}**\n"
        f"> {text}\n"
        f"{post['link']}"
    )
    return msg

async def post_latest_wordpress_post_once():
    await client.wait_until_ready()

    post = await fetch_wordpress_posts()
    if not post:
        return

    message = format_wordpress_post(post)

    channel = discord.utils.get(client.get_all_channels(), name="test")
    if channel:
        await channel.send(f"[TEST] Neuester Wordpress-Beitrag:\n{message}")
        print(f"[TEST] Neuester Wordpress-Beitrag gepostet: {post['title']}")
    else:
        print("[TEST] Channel 'test' nicht gefunden.")

# Task-Wächter, nur einmal starten
tasks_started = False

async def refresh_data_loop():
    while True:
        await asyncio.sleep(3600)  # stündlich aktualisieren
        update_feed()
        await fetch_schedule()

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
async def on_connect():
    global tasks_started
    print(f"[INFO] Bot verbunden mit Discord.")

    if not tasks_started:
        print("[INFO] Starte Initialdaten-Aktualisierung und Hintergrund-Tasks ...")
        update_feed()
        await fetch_schedule()

        client.loop.create_task(refresh_data_loop())
        client.loop.create_task(post_random_episode_loop())
        client.loop.create_task(post_latest_wordpress_post_once())  # Testpost beim Start

        tasks_started = True

@client.event
async def on_message(message):
    if message.author.bot or message.channel.name in BLACKLIST_CHANNELS:
        return

    lower_msg = message.content.lower()

    for trigger, response in CUSTOM_TRIGGERS.items():
        if trigger in lower_msg:
            await message.channel.send(response)
            return

    msg = message.content.upper()

    # Spezielle Codes
    for special_code, info in SPECIAL_CODES.items():
        pattern = r'(?<![\w-])' + re.escape(special_code) + r'(?![\w-])'
        if re.search(pattern, msg, re.IGNORECASE):
            await message.channel.send(info["response"], suppress_embeds=True)
            return

    # Normale SCP-/SKP-Erkennung (aus Feed)
    for code, data in scp_links.items():
        code_upper = code.upper()
        pattern = r'(?<![\w-])' + re.escape(code_upper) + r'(?![\w-])'
        if re.search(pattern, msg, re.IGNORECASE):
            await message.channel.send(f"🎧 Neue Vertonung: **{data['title']}**\n🔗 **[Hier anhören]({data['link']})**", suppress_embeds=True)
            return

    # Nicht gefunden
    # (Optional: keine Antwort)
    # await message.channel.send("Kein Ergebnis gefunden.")

client.run(TOKEN)
