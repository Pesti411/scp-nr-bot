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
initial_run = True

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
posted_episodes = set()  # Damit keine Episode doppelt gepostet wird

def format_episode_message(entry):
    description = html.unescape(entry.get("description", ""))

    # Discord-Link entfernen
    description = re.sub(r"http[s]?://discord\.gg/[^\s]+", "", description, flags=re.IGNORECASE)

    # Aufteilen in Teile: Beschreibung / Autor / Übersetzer
    lines = description.split("/")

    # Beschreibungstext
    text_desc = lines[0].strip() if len(lines) > 0 else ""

    # Autor und Übersetzer
    author = ""
    translator = ""
    if len(lines) > 1:
        author_match = re.search(r'Autor:\s*([^/]+)', description)
        translator_match = re.search(r'Übersetzung:\s*([^/]+)', description)
        if author_match:
            author = author_match.group(1).strip()
        if translator_match:
            translator = translator_match.group(1).strip()

    # Titel direkt aus dem Feed
    title = entry.get("title", "Unbekannt")

    # Formatierten Message-String bauen
    msg = (
        f":newspaper2: :speaker: **Neue Vertonung von Pesti | {title}**\n"
        f"> {text_desc}\n"
    )
    msg += f"> Autor: {author}\n"
    if translator:
        msg += f"> Übersetzer: {translator}\n"

    msg += entry.get("link", "")  # Direktlink

    return msg


def format_alt_message(entry):
    description = html.unescape(entry.get("description", ""))
    description = re.sub(r"http[s]?://discord\.gg/[^\s]+", "", description, flags=re.IGNORECASE)

    # Aufteilen in Teile: Beschreibung / Autor / Übersetzer
    lines = description.split("/")
    text_desc = lines[0].strip() if len(lines) > 0 else ""

    # Autor und Übersetzer
    author = ""
    if "Autor:" in description:
        author_match = re.search(r'Autor:\s*([^/]+)', description)
        if author_match:
            author = author_match.group(1).strip()

    # Titel direkt aus dem Feed
    title = entry.get("title", "Unbekannt")

    # Prüfen, ob Titel mit "SCP-" beginnt
    if title.startswith("SCP-"):
        # SCP-Nummer extrahieren
        scp_match = re.match(r'(SCP-\d+):?\s*"?([^"]+)"?', title)
        if scp_match:
            scp_code = scp_match.group(1)
            scp_title = scp_match.group(2).strip()
            title_line = f"> +++ [{entry.link} {scp_code}]: {scp_title}"
        else:
            title_line = f"> +++ [{entry.link} {title}]"
    else:
        # kein SCP-Code → kompletter Titel in eckige Klammer, ohne Doppelpunkt danach
        title_line = f"> +++ [{entry.link} {title}]"

    # Nachricht zusammensetzen
    msg = (
        f"{title_line}\n"
        f"> {text_desc}\n"
        f"> ++++* vertont von [[*User Pesti]]"
    )
    return msg


async def check_rss_feed_loop():
    await client.wait_until_ready()
    initial_run = True  # verhindert Spam beim ersten Start

    while not client.is_closed():
        feed = feedparser.parse(FEED_URL)
        for entry in feed.entries:
            if entry.link not in posted_episodes:
                posted_episodes.add(entry.link)

                # nur neue Episoden posten, nicht beim allerersten Start
                if not initial_run:
                    channel1 = client.get_channel(1238108459543822337)  # Erster Channel (Discord-Format) ID Kanal test: 1238108459543822337 / ID Kanal news: 1230551357635825787
                    channel2 = client.get_channel(1238108459543822337)  # Zweiter Channel (Wiki-Format)

                    if channel1:
                        await channel1.send(format_episode_message(entry))
                    if channel2:
                        await channel2.send(format_alt_message(entry))

        initial_run = False  # nach dem ersten Durchlauf deaktivieren
        await asyncio.sleep(600)  # 10 Minuten warten

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


@client.event
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
        latest_time = now.replace(hour=12, minute=10, second=0, microsecond=0)

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

    # Test-Command: !latest_episode
    if content_lower.startswith("!latest_episode"):
        if not all_episodes:
            await message.channel.send("⚠️ Keine Episoden gefunden.")
            return

        latest_entry = all_episodes[0]
        # Feedparser nochmal parsen, um die Beschreibung zu holen
        feed = feedparser.parse(FEED_URL)
        description = ""
        for entry in feed.entries:
            if entry.link == latest_entry["link"]:
                description = html.unescape(entry.get("description", ""))
                break

        msg = f"**Neueste Episode:** {latest_entry['title']}\n{description}\n🔗 {latest_entry['link']}"
        await message.channel.send(msg)
        return

async def post_latest_wordpress_post_once():
    print("[INFO] Starte einmaliges Posten des neuesten Wordpress-Beitrags ...")
    
@client.event
async def on_ready():
    global tasks_started
    print(f"[INFO] Bot ist bereit. Eingeloggt als {client.user}.")

    if not tasks_started:
        print("[INFO] Starte Hintergrund-Tasks ...")

        # Initialdaten laden
        update_feed()  # Falls async -> await update_feed()
        await fetch_schedule()

        # Tasks nur einmal starten
        client.loop.create_task(refresh_data_loop())
        client.loop.create_task(post_random_episode_loop())
        client.loop.create_task(check_rss_feed_loop())

        tasks_started = True
    else:
        print("[INFO] Hintergrund-Tasks laufen bereits, kein erneuter Start.")

client.run(TOKEN)
