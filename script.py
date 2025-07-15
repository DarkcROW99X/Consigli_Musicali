import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# === Dummy web server per Render ===
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Spotify-Telegram attivo!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))  # Render fornisce la porta come env var
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

# Avvia il server in un thread separato
threading.Thread(target=run_dummy_server, daemon=True).start()

# === Configurazione Bot Telegram + Spotify ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Ciao! Sono il tuo bot Spotify-Telegram.")

def search_song(update: Update, context: CallbackContext):
    query = " ".join(context.args)
    if not query:
        update.message.reply_text("Devi darmi il nome di una canzone dopo /search")
        return
    results = sp.search(q=query, limit=1, type='track')
    if results['tracks']['items']:
        track = results['tracks']['items'][0]
        response = f"Trovata: {track['name']} di {track['artists'][0]['name']} - {track['external_urls']['spotify']}"
    else:
        response = "Nessun risultato trovato."
    update.message.reply_text(response)

def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("search", search_song))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
