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
import json

# -----------------------------
# Konfiguration
# -----------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
FEED_URL = "https://q8reci.podcaster.de/scp-deutsch.rss"
SCHEDULE_CSV_URL = "https://docs.google.com/spreadsheets/d/125iGFTWMVKImY_abjac1Lfal78o-dFzQalq6rT_YDxM/export?format=csv"
BLACKLIST_CHANNELS = ["discord-vorschläge", "umfragen", "roleplay", "vertonungsplan", "news"]
DATA_FILE = "posted_episodes.json"
CHANNEL_ID = 1238108459543822337  # Hier die echte Channel-ID einsetzen

# -----------------------------
# Lade bereits gepostete Episoden
# -----------------------------
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        posted_episodes = set(json.load(f))
else:
    posted_episodes = set()

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


# -----------------------------
# Discord Setup
# -----------------------------

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

scp_links = {}
all_episodes = []
schedule = {}

def format_episode_message(entry):
    description = html.unescape(entry.get("description", ""))
    description = re.sub(r"http[s]?://discord\.gg/[^\s]+", "", description, flags=re.IGNORECASE)
    lines = description.split("/")
    title_match = re.match(r'(SCP-\d+):\s*"(.+)"', lines[0].strip())
    scp_code = title_match.group(1) if title_match else "Unbekannt"
    scp_title = title_match.group(2) if title_match else lines[0].strip()
    text_desc = lines[1].strip() if len(lines) > 1 else ""
    author = ""
    translator = ""
    if len(lines) > 2:
        author_match = re.search(r'Autor:\s*([^/]+)', lines[2])
        translator_match = re.search(r'Übersetzung:\s*([^/]+)', lines[2])
        if author_match: author = author_match.group(1).strip()
        if translator_match: translator = translator_match.group(1).strip()
    msg = f":newspaper2: :speaker: **Neue Vertonung von {author} | {scp_code}: „{scp_title}“**\n> {text_desc}\n"
    if translator: msg += f"> Übersetzer: {translator}\n"
    msg += entry.link
    return msg

async def check_rss_feed_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        feed = feedparser.parse(FEED_URL)
        for entry in feed.entries:
            if entry.link not in posted_episodes:
                posted_episodes.add(entry.link)
                msg = format_episode_message(entry)
                channel = client.get_channel(1238108459543822337)  # <--- Hier die Channel-ID einsetzen
                if channel:
                    await channel.send(msg)
        await asyncio.sleep(600)

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
        all_episodes.append({"title": title, "link": link})
        code = parse_scp_code(title)
        if code:
            scp_links[code.lower()] = {"title": title, "link": link}

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

async def refresh_data_loop():
    while True:
        update_feed()
        await fetch_schedule()
        await asyncio.sleep(3600)

async def post_random_episode_loop():
    await client.wait_until_ready()
    tz = pytz.timezone("Europe/Berlin")
    last_posted_date = None
    while True:
        now = datetime.datetime.now(tz)
        today = now.date()
        target_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
        latest_time = now.replace(hour=12, minute=10, second=0, microsecond=0)
        if last_posted_date != today and target_time <= now < latest_time:
            if all_episodes:
                import random
                episode = random.choice(all_episodes)
                channel = discord.utils.get(client.get_all_channels(), name="news")
                if channel:
                    await channel.send(f"🎧 Tägliche Zufalls-Episode:\n**{episode['title']}**\n🔗 **[Hier anhören]({episode['link']})**")
                    last_posted_date = today
        await asyncio.sleep(300)

@client.event
async def on_message(message):
    if message.author.bot or message.channel.name in BLACKLIST_CHANNELS:
        return
    content_raw = message.content
    content_lower = content_raw.lower()
    content_upper = content_raw.upper()

    for trigger, response in CUSTOM_TRIGGERS.items():
        if trigger in content_lower:
            await message.channel.send(response)
            return

    for special_code, info in SPECIAL_CODES.items():
        pattern = r'(?<![\w-])' + re.escape(special_code) + r'(?![\w-])'
        if re.search(pattern, content_upper, re.IGNORECASE):
            await message.channel.send(info["response"], suppress_embeds=True)
            return

    for code in scp_links.keys():
        pattern = r'(?<![\w-])' + re.escape(code.upper()) + r'(?![\w-])'
        if re.search(pattern, content_upper, re.IGNORECASE):
            data = scp_links[code]
            response = f"🔎 Gefunden: **{data['title']}**\n🎧 **[Hier anhören]({data['link']})**"
            if code in schedule:
                response += f"\n📅 Veröffentlichungsdatum laut Plan: {schedule[code]}"
            await message.channel.send(response)
            return

    for code in schedule.keys():
        if code not in scp_links:
            pattern = r'(?<![\w-])' + re.escape(code.upper()) + r'(?![\w-])'
            if re.search(pattern, content_upper, re.IGNORECASE):
                await message.channel.send(f"📅 **{code.upper()}** ist laut Plan für {schedule[code]} vorgesehen.")
                return

    if content_lower.startswith("!latest_episode"):
        if not all_episodes:
            await message.channel.send("⚠️ Keine Episoden gefunden.")
            return
        latest_entry = all_episodes[0]
        feed = feedparser.parse(FEED_URL)
        description = ""
        for entry in feed.entries:
            if entry.link == latest_entry["link"]:
                description = html.unescape(entry.get("description", ""))
                break
        msg = f"**Neueste Episode:** {latest_entry['title']}\n{description}\n🔗 {latest_entry['link']}"
        await message.channel.send(msg)
        return

@client.event
async def on_ready():
    global tasks_started
    print(f"[INFO] Bot ist bereit. Eingeloggt als {client.user}.")
    if not tasks_started:
        tasks_started = True
        update_feed()
        await fetch_schedule()
        client.loop.create_task(check_rss_feed_loop())
        client.loop.create_task(refresh_data_loop())
        client.loop.create_task(post_random_episode_loop())

client.run(TOKEN)
