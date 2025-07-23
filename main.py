import os
import discord
import feedparser
import re
import asyncio
import html
import threading
import http.server
import socketserver

TOKEN = os.getenv("DISCORD_TOKEN")
FEED_URL = "https://q8reci.podcaster.de/scp-deutsch.rss"
BLACKLIST_CHANNELS = ["discord-vorschläge", "umfragen", "roleplay", "vertonungsplan", "news"]

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

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
            
        )
        return
     
scp_links = {}

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
        code = parse_scp_code(entry.title)
        if code:
            scp_links[code.lower()] = {
                "title": html.unescape(entry.title.strip()),
                "link": entry.link.strip()
            }

@client.event
async def on_ready():
    print(f"Eingeloggt als {client.user}")
    update_feed()
    async def refresh_feed_loop():
        while True:
            await asyncio.sleep(86400)  # alle 24h
            update_feed()
    client.loop.create_task(refresh_feed_loop())

@client.event
async def on_message(message):
    if message.author.bot or message.channel.name in BLACKLIST_CHANNELS:
        return

    msg = message.content.upper()

    for code, data in scp_links.items():
        code_upper = code.upper()
        pattern = r'(?<![\w-])' + re.escape(code_upper) + r'(?![\w-])'
        if re.search(pattern, msg, re.IGNORECASE):
            await message.channel.send(
                f"🔎 Gefunden: **{data['title']}**\n🎧 **[Hier anhören]({data['link']})**"
            )
            break

def keep_alive():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", 8080), handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=keep_alive).start()

client.run(TOKEN)
