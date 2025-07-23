import os
import discord
import feedparser
import re
import asyncio
import html

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "test")
FEED_URL = "https://q8reci.podcaster.de/scp-deutsch.rss"

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

scp_links = {}

def parse_scp_code(title):
    if not title.startswith("SCP-") or title.startswith("SCP-001"):
        return None
    match = re.match(r"^(SCP-[^:]+):", title)
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
    if message.author.bot or message.channel.name != CHANNEL_NAME:
        return

    msg = message.content.upper()

    for code, data in scp_links.items():
        # Regex: exakter Code-Treffer, keine Teiltreffer wie SCP-100 in SCP-1000
        pattern = r'(?<![\w-])' + re.escape(code) + r'(?![\w-])'
        if re.search(pattern, msg, re.IGNORECASE):
            await message.channel.send(
                f"🔎 Gefunden: **{data['title']}**\n🎧 **[Hier anhören]**({data['link']})"
            )
            break

import threading
import http.server
import socketserver

def keep_alive():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", 8080), handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=keep_alive).start()

client.run(TOKEN)
