from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os

# Prendi token e credenziali da variabili d'ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Setup Spotify API client
client_credentials_manager = SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET)
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
