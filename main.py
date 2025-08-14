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
SCHEDULE_CSV_URL = "https://docs.google.com/spreadsheets/d/.../export?format=csv"
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
    feed = feedparser.parse(FEED_URL)
    scp_links = {}
    all_episodes = []
    for entry in feed.entries:
        if hasattr(entry, "title") and hasattr(entry, "link"):
            code = parse_scp_code(entry.title)
            if code:
                scp_links[code] = entry.link
            all_episodes.append({"title": entry.title, "link": entry.link})
    print(f"[INFO] {len(all_episodes)} Episoden geladen, {len(scp_links)} SCP-Codes gefunden.")

async def fetch_schedule():
    global schedule
    print("[INFO] Lade Vertonungsplan ...")
    schedule = {}
    async with aiohttp.ClientSession() as session:
        async with session.get(SCHEDULE_CSV_URL) as resp:
            if resp.status == 200:
                text = await resp.text()
                reader = csv.reader(text.splitlines())
                for row in reader:
                    if len(row) >= 4:
                        schedule[row[0].upper()] = row[3]
                print(f"[INFO] {len(schedule)} Einträge im Vertonungsplan geladen.")
            else:
                print("[WARN] Konnte CSV nicht laden.")

# ================= Textaufbereitung =================

def clean_and_format_text(text):
    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)
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
    return f"**{title}**\n{clean_text}\n🎧 [Hier lesen]({link})"

# ================= Background Tasks =================

async def refresh_data_loop():
    while True:
        await update_feed()
        await fetch_schedule()
        await asyncio.sleep(3600)  # jede Stunde

async def post_random_episode_loop():
    await client.wait_until_ready()
    news_channel = next((c for c in client.get_all_channels() if c.name.lower() == "news"), None)
    while not client.is_closed():
        now = datetime.datetime.now(pytz.timezone("Europe/Berlin"))
        if 12 <= now.hour < 13:
            if all_episodes and news_channel:
                episode = random.choice(all_episodes)
                await news_channel.send(f"Heute zufällige Episode: **{episode['title']}**\n🎧 [Hier anhören]({episode['link']})")
            await asyncio.sleep(3600)
        else:
            await asyncio.sleep(300)

# ================= Message Handling =================

@client.event
async def on_message(message):
    if message.author.bot or message.channel.name.lower() in BLACKLIST_CHANNELS:
        return

    msg_lower = message.content.lower()
    msg_upper = message.content.upper()

    # Custom Triggers
    for trigger, reply in CUSTOM_TRIGGERS.items():
        if trigger in msg_lower:
            await message.channel.send(reply)
            return

    # Special Codes
    for code, data in SPECIAL_CODES.items():
        if re.search(rf"\b{re.escape(code)}\b", msg_upper):
            await message.channel.send(data["response"])
            return

    # SCP Feed
    for code, link in scp_links.items():
        if re.search(rf"(?<![\w-]){re.escape(code)}(?![\w-])", msg_upper):
            await message.channel.send(f"🔎 Gefunden: **{code}**\n🎧 [Hier anhören]({link})")
            return

    # Schedule
    for code, date in schedule.items():
        if re.search(rf"(?<![\w-]){re.escape(code)}(?![\w-])", msg_upper):
            await message.channel.send(f"{code} erscheint am {date}")
            return

    # WordPress command
    if msg_lower.startswith("!wp"):
        async with aiohttp.ClientSession() as session:
            async with session.get(WORDPRESS_FEED_URL) as resp:
                if resp.status == 200:
                    posts = await resp.json()
                    if posts:
                        await message.channel.send(format_wordpress_post(posts[0]))
                else:
                    await message.channel.send("Konnte WordPress-Feed nicht laden.")

# ================= On Connect =================

@client.event
async def on_connect():
    global tasks_started
    print("[INFO] Bot verbunden")
    if not tasks_started:
        client.loop.create_task(refresh_data_loop())
        client.loop.create_task(post_random_episode_loop())
        tasks_started = True
        print("[INFO] Hintergrund-Tasks gestartet")

# ================= Start =================

client.run(TOKEN)
