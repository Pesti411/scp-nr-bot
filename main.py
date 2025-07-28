import os
import discord
import feedparser
import re
import asyncio
import html
import aiohttp
import csv
import datetime

# Konfiguration
TOKEN = os.getenv("DISCORD_TOKEN")
FEED_URL = "https://q8reci.podcaster.de/scp-deutsch.rss"
SCHEDULE_CSV_URL = "https://docs.google.com/spreadsheets/d/125iGFTWMVKImY_abjac1Lfal78o-dFzQalq6rT_YDxM/export?format=csv"
BLACKLIST_CHANNELS = ["discord-vorschläge", "umfragen", "roleplay", "vertonungsplan", "news"]

# Discord-Intents setzen
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

scp_links = {}
schedule = {}

def parse_scp_code(title):
    if not (title.startswith("SCP-") or title.startswith("SKP-")):
        return None
    if title.startswith("SCP-001") or title.startswith("SKP-001"):
        return None
    match = re.match(r"^((?:SCP|SKP)-[^:]+):", title)
    return match.group(1) if match else None

def update_feed():
    global scp_links
    scp_links.clear()
    feed = feedparser.parse(FEED_URL)
    for entry in feed.entries:
        # Eindeutiger Schlüssel, z. B. Link
        key = entry.link.strip()
        scp_links[key] = {
            "title": html.unescape(entry.title.strip()),
            "link": entry.link.strip()
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

@client.event
async def on_ready():
    print(f"Eingeloggt als {client.user}")
    update_feed()
    await fetch_schedule()

    async def refresh_data_loop():
        while True:
            await asyncio.sleep(3600)  # stündlich
            update_feed()
            await fetch_schedule()

    client.loop.create_task(refresh_data_loop())
    client.loop.create_task(post_random_episode_loop())

import datetime

async def post_random_episode_loop():
    await client.wait_until_ready()
    while True:
        now = datetime.datetime.now()
        target_time = now.replace(hour=12, minute=0, second=0, microsecond=0)

        # Wenn Zielzeit heute schon vorbei ist, nimm morgen
        if now >= target_time:
            target_time += datetime.timedelta(days=1)

        wait_seconds = (target_time - now).total_seconds()
        print(f"[INFO] Warte bis {target_time} ({int(wait_seconds)} Sekunden)")

        await asyncio.sleep(wait_seconds)

        # Wähle zufällige Episode
        if scp_links:
            import random
            episode = random.choice(list(scp_links.values()))
            channel = discord.utils.get(client.get_all_channels(), name="test")  # ggf. Channelname anpassen
            if channel:
                await channel.send(
                    f"🎧 Tägliche Zufalls-Episode:\n**{episode['title']}**\n🔗 **[Hier anhören]({episode['link']})**"
                )

        # Danach exakt 24 Stunden warten (bis zur nächsten Sendung)
        await asyncio.sleep(86400)
            
@client.event
async def on_message(message):
    if message.author.bot or message.channel.name in BLACKLIST_CHANNELS:
        return

    msg = message.content.upper()

    # Spezialfall: SCP-001
    if re.search(r'\bSCP-001\b', msg, re.IGNORECASE):
        await message.channel.send(
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
            ":bulb: SCP-001-DE: CODE NAME: „Abyssus - Abgrund der Realität“ *ist bereits geplant, ich bitte um Geduld*\n",
            suppress_embeds=True
        )
        return

    # Check gegen Plan-Tabelle
    for code, date in schedule.items():
        pattern = r'(?<![\w-])' + re.escape(code.upper()) + r'(?![\w-])'
        if re.search(pattern, msg, re.IGNORECASE):
            await message.channel.send(
                f"📅 **{code.upper()}** ist laut Plan für {date} vorgesehen."
            )
            return

    # Normale SCP-/SKP-Erkennung (aus Feed)
    for code, data in scp_links.items():
        code_upper = code.upper()
        pattern = r'(?<![\w-])' + re.escape(code_upper) + r'(?![\w-])'
        if re.search(pattern, msg, re.IGNORECASE):
            await message.channel.send(
                f"🔎 Gefunden: **{data['title']}**\n🎧 **[Hier anhören]({data['link']})**"
            )
            break

client.run(TOKEN)
