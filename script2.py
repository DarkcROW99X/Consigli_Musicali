import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import requests
import base64
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
TOKEN_GITHUB = os.getenv("TOKEN_GITHUB")
REPO_GITHUB = os.getenv("REPO_GITHUB")  # es: username/repo
FILE_PATH_GITHUB = os.getenv("FILE_PATH_GITHUB", "user_artists.json")
BRANCH_GITHUB = os.getenv("BRANCH_GITHUB", "main")

client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# --- GitHub interaction functions ---
def github_get_file_sha():
    url = f"https://api.github.com/repos/{REPO_GITHUB}/contents/{FILE_PATH_GITHUB}"
    headers = {"Authorization": f"token {TOKEN_GITHUB}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def github_commit_file(content_json):
    content_bytes = json.dumps(content_json, indent=2).encode("utf-8")
    content_b64 = base64.b64encode(content_bytes).decode("utf-8")
    sha = github_get_file_sha()

    url = f"https://api.github.com/repos/{REPO_GITHUB}/contents/{FILE_PATH_GITHUB}"
    headers = {
        "Authorization": f"token {TOKEN_GITHUB}",
        "Accept": "application/vnd.github+json"
    }

    payload = {
        "message": "Aggiornamento artisti preferiti",
        "content": content_b64,
        "branch": BRANCH_GITHUB
    }

    if sha:
        payload["sha"] = sha

    response = requests.put(url, headers=headers, json=payload)
    return response.status_code in [200, 201]

# --- Gestione file utenti ---
def load_user_artists():
    try:
        with open("user_artists.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_artists(data):
    with open("user_artists.json", "w") as f:
        json.dump(data, f, indent=2)
    github_commit_file(data)








# --- Comandi bot ---
def start(update: Update, context: CallbackContext):
    msg = (
        "🎵 Benvenuto! Ecco cosa puoi fare:\n\n"
        "/search <brano> – Cerca una canzone su Spotify\n"
        "/setartist <nome artista 1> <nome artista 2> – Aggiungi artisti ai tuoi preferiti\n"
        "/listartists – Mostra i tuoi artisti preferiti\n"
        "/recommend – Ottieni consigli basati sui tuoi gusti\n\n"
        "Esempio: /setartist Dua Lipa Eminem\n"
        "Esempio: /search Blinding Lights"
    )
    update.message.reply_text(msg)

def search_song(update: Update, context: CallbackContext):
    query = " ".join(context.args)
    if not query:
        update.message.reply_text("❗ Usa /search seguito dal nome della canzone.")
        return
    results = sp.search(q=query, limit=1, type='track')
    if results['tracks']['items']:
        track = results['tracks']['items'][0]
        update.message.reply_text(
            f"🎶 {track['name']} - {track['artists'][0]['name']}\n{track['external_urls']['spotify']}"
        )
    else:
        update.message.reply_text("❌ Nessuna canzone trovata.")

def setartist(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    args = context.args
    if not args:
        update.message.reply_text("❗ Usa /setartist <artista 1> <artista 2> ...")
        return

    artist_names = " ".join(args).split(",") if "," in " ".join(args) else args
    user_artists = load_user_artists()

    if user_id not in user_artists:
        user_artists[user_id] = []

    added = []
    skipped = []

    for name in artist_names:
        artist_name = name.strip()
        if artist_name and artist_name not in user_artists[user_id]:
            user_artists[user_id].append(artist_name)
            added.append(artist_name)
        elif artist_name:
            skipped.append(artist_name)

    save_user_artists(user_artists)

    msg = ""
    if added:
        msg += f"✅ Aggiunti: {', '.join(added)}\n"
    if skipped:
        msg += f"ℹ️ Già presenti: {', '.join(skipped)}"
    update.message.reply_text(msg.strip())

def listartists(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_artists = load_user_artists()

    if user_id not in user_artists or not user_artists[user_id]:
        update.message.reply_text("📭 Non hai ancora artisti preferiti.")
        return

    artists = "\n".join(f"- {a}" for a in user_artists[user_id])
    update.message.reply_text(f"🎨 I tuoi artisti:\n{artists}")

def recommend(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_artists = load_user_artists()

    if user_id not in user_artists or not user_artists[user_id]:
        update.message.reply_text("⚠️ Nessun artista salvato. Usa /setartist per aggiungerne.")
        return

    seed_artist_ids = []
    for artist_name in user_artists[user_id]:
        results = sp.search(q=f"artist:{artist_name}", type="artist", limit=1)
        items = results.get("artists", {}).get("items", [])
        if items:
            seed_artist_ids.append(items[0]["id"])
        if len(seed_artist_ids) >= 5:
            break

    if not seed_artist_ids:
        update.message.reply_text("❌ Nessun artista trovato su Spotify.")
        return

    try:
        recs = sp.recommendations(seed_artists=seed_artist_ids, limit=5)
        tracks = recs.get("tracks", [])
        if not tracks:
            update.message.reply_text("😕 Nessuna raccomandazione trovata.")
            return

        msg = "🎧 Brani consigliati:\n"
        for t in tracks:
            msg += f"- {t['name']} di {t['artists'][0]['name']}\n{t['external_urls']['spotify']}\n"
        update.message.reply_text(msg)
    except Exception as e:
        update.message.reply_text(f"Errore: {e}")

# --- Avvio bot ---
def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("search", search_song))
    dp.add_handler(CommandHandler("setartist", setartist))
    dp.add_handler(CommandHandler("listartists", listartists))
    dp.add_handler(CommandHandler("recommend", recommend))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
