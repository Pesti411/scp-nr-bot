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
import random

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
        "response": "🔎 Gefunden: **SCP-6500: „Unvermeidbar“**\n🎧 **[Hier anhören](https://nurkram.de/scp-6500)**"
    },
    "SCP-1730": {
        "response": "🔎 Gefunden: **SCP-1730: „Was ist mit Standort-13 passiert?“**\n🎧 **[Hier anhören](https://nurkram.de/scp-1730)**"
    }
}

CUSTOM_TRIGGERS = {
    "scarlet king": "🔎 Gefunden: **SCP-001: CODE NAME: „Tufto – Der Scarlet King“**\n🎧 **[Hier anhören](https://nurkram.de/scp-001-tufto)**",
    "scharlach-rot": "🔎 Gefunden: **SCP-001: CODE NAME: „Tufto – Der Scarlet King“**\n🎧 **[Hier anhören](https://nurkram.de/scp-001-tufto)**",
    "scharlach-roter": "🔎 Gefunden: **SCP-001: CODE NAME: „Tufto – Der Scarlet King“**\n🎧 **[Hier anhören](https://nurkram.de/scp-001-tufto)**",
    "shy guy": "🔎 Gefunden: **SCP-096: „Der Schüchterne Mann“**\n🎧 **[Hier anhören](https://nurkram.de/scp-096)**",
    "peanut": "🔎 Gefunden: **SCP-173: „Die Statue“**\n🎧 **[Hier anhören](https://nurkram.de/scp-173)**"
}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

scp_links = {}
all_episodes = []
schedule = {}
tasks_started = False

# ================= Feed & Schedule =================

def parse_scp_code(title):
    match = re.match(r'^((?:SCP|SKP)-[^:]+):', title)
    if match:
        code = match.group(1)
        if code != "SCP-001":
            return code
    return None

async def update_feed():
    global scp_links, all_episodes
    print("[INFO] Aktualisiere RSS-Feed ...")
    scp_links = {}
    all_episodes = []
    try:
        feed = feedparser.parse(FEED_URL)
        for entry in feed.entries:
            if hasattr(entry, "title") and hasattr(entry, "link"):
                code = parse_scp_code(entry.title)
                if code:
                    scp_links[code] = entry.link
                # Format Titel richtig
                title_clean = entry.title.replace('"', "„").replace('"', "“")
                all_episodes.append({"title": title_clean, "link": entry.link})
        print(f"[INFO] {len(all_episodes)} Episoden geladen, {len(scp_links)} SCP-Codes gefunden.")
    except Exception as e:
        print(f"[ERROR] Fehler beim Aktualisieren des RSS-Feeds: {e}")

async def fetch_schedule():
    global schedule
    print("[INFO] Lade Vertonungsplan ...")
    schedule = {}
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(SCHEDULE_CSV_URL) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    reader = csv.reader(text.splitlines())
                    for row in reader:
                        if len(row) >= 4:
                            schedule[row[0].upper()] = row[3]
                    print(f"[INFO] {len(schedule)} Einträge im Vertonungsplan geladen.")
                else:
                    print(f"[WARN] Konnte CSV nicht laden: HTTP {resp.status}")
    except Exception as e:
        print(f"[ERROR] Fehler beim Abrufen des Vertonungsplans: {e}")

# ================= Textaufbereitung =================

def clean_and_format_text(text):
    text = html.unescape(text)
    text = re.sub(r"\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\*.*?\*", "", text)
    text = text.strip()
    if len(text) > 300:
        text = text[:300] + "..."
    return "> " + text

def format_wordpress_post(post):
    title = post.get("title", {}).get("rendered", "")
    content = post.get("content", {}).get("rendered", "")
    link = post.get("link", "#")
    clean_text = clean_and_format_text(content)
    title = title.replace('"', "„").replace('"', "“")
    return f"**{title}**\n{clean_text}\n<{link}>"

# ================= Background Tasks =================

async def refresh_data_loop():
    while True:
        await update_feed()
        await fetch_schedule()
        await asyncio.sleep(3600)

async def post_random_episode_loop():
    await client.wait_until_ready()
    news_channel = discord.utils.get(client.get_all_channels(), lambda c: c.name.lower() == "news")
    while not client.is_closed():
        now = datetime.datetime.now(pytz.timezone("Europe/Berlin"))
        if 12 <= now.hour < 13:
            if all_episodes and news_channel:
                episode = random.choice(all_episodes)
                await news_channel.send(f"Heute zufällige Episode:\n**{episode['title']}**\n🎧 <{episode['link']}>")
        await asyncio.sleep(3600)

# ================= Discord Events =================

@client.event
async def on_ready():
    global tasks_started
    print(f"[INFO] Bot eingeloggt als {client.user}")
    if not tasks_started:
        client.loop.create_task(refresh_data_loop())
        client.loop.create_task(post_random_episode_loop())
        tasks_started = True

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.name in BLACKLIST_CHANNELS:
        return

    content_lower = message.content.lower()
    
    # Spezialfälle
    for trigger, response in CUSTOM_TRIGGERS.items():
        if trigger in content_lower:
            await message.channel.send(response)
            return

    # SCP-001 Fix
    if "scp-001" in content_lower:
        await message.channel.send(SPECIAL_CODES["SCP-001"]["response"])
        return

    # RSS-Feed Lookup
    match = re.match(r"^(scp-\d+)", content_lower)
    if match:
        code = match.group(1).upper()
        if code in SPECIAL_CODES:
            await message.channel.send(SPECIAL_CODES[code]["response"])
        elif code in scp_links:
            await message.channel.send(f"🔎 Gefunden: **{code}**\n🎧 **[Hier anhören]({scp_links[code]})**")
        elif code in schedule:
            await message.channel.send(f"📅  **{code}** ist geplant für: {schedule[code]}")

    # WordPress Post
    if message.content.startswith("!wp"):
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            "User-Agent": "DiscordBot/1.0 (+https://example.com)",
            "Accept": "application/json"
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            try:
                async with session.get(WORDPRESS_FEED_URL, allow_redirects=True) as resp:
                    if resp.status == 200:
                        posts = await resp.json()
                        if posts:
                            post_text = format_wordpress_post(posts[0])
                            await message.channel.send(post_text)
                        else:
                            await message.channel.send("Keine Beiträge gefunden.")
                    else:
                        await message.channel.send(f"Fehler beim Laden der WordPress-Posts: {resp.status}")
            except Exception as e:
                await message.channel.send(f"Fehler beim Abrufen der WordPress-Posts: {e}")

client.run(TOKEN)
