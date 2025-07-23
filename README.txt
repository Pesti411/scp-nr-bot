SCP-Discord-Bot (für Railway)
=============================

1. Erstelle einen Bot über https://discord.com/developers/applications
   - Aktiviere MESSAGE CONTENT INTENT
   - Kopiere deinen Token

2. Lade dieses Projekt auf https://railway.app hoch
   - Neues Projekt → Deploy from GitHub (oder Upload Folder)

3. Füge in Railway unter Variables folgendes hinzu:
   - DISCORD_TOKEN = <dein Token>
   - CHANNEL_NAME = test

4. Starte den Bot – er antwortet auf SCP-Codes im Channel #test
   - Nur exakte Codes (SCP-123, SCP-087-DE), keine SCP-001

5. Der Bot aktualisiert alle 24h automatisch den Podcast-Feed