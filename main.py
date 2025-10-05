# main.py
from pathlib import Path
import random
import string
import logging
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Original code (with minor adjustments) ---

# Constants
EXCLUDED_ARTISTS_FILE = Path("no_chords_artists.txt")
BASE_URL = "https://www.cifraclub.com"

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Functions
def load_excluded_artists(file_path: Path = EXCLUDED_ARTISTS_FILE) -> set[str]:
    if not file_path.exists():
        return set()
    with file_path.open("r", encoding="utf-8") as file:
        return {line.strip() for line in file}

def get_random_artist(initial_letter=random.choice(string.ascii_uppercase + "1")) -> str:
    url = f"{BASE_URL}/letra/{initial_letter}/lista.html"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch artist list: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    excluded_artists = load_excluded_artists()
    a_list = soup.select("ul.g-1.g-fix.list-links.art-alf li a")
    artists = [a["href"].strip("/") for a in a_list if a["href"].strip("/") not in excluded_artists]
    return random.choice(artists) if artists else None

def get_random_song_url_from_artist(artist: str) -> str:
    url = f"{BASE_URL}/{artist}/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch songs for {artist}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    a_list = soup.select("ol.list-links.art_musics.all.listSongArtist li a")
    songs = [a["href"] for a in a_list if a.find_parent("span") and "#instrument=guitar" in a["href"]]

    if not songs:
        logging.info(f"No chord songs found for {artist}, adding to excluded list.")
        with EXCLUDED_ARTISTS_FILE.open("a", encoding="utf-8") as file:
            file.write(artist + "\n")
        return None
    return f"{BASE_URL}{random.choice(songs).replace('#instrument=guitar', '')}"

def find_song_with_retries(max_attempts=20):
    for attempt in range(max_attempts):
        logging.info(f"Attempt {attempt + 1}: Finding a song...")
        artist = get_random_artist()
        if artist:
            song_url = get_random_song_url_from_artist(artist)
            if song_url:
                return song_url
    logging.error("Failed to find a song after multiple attempts.")
    return None

# --- FastAPI API Section ---

app = FastAPI(
    title="Random Song API",
    description="An API to get a random song with chords from CifraClub."
)

# This allows frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/random-song", summary="Get a random song URL")
def get_song_endpoint():
    """
    Searches for a random artist and song with chords.
    If not found, it retries several times.
    """
    song_url = find_song_with_retries()
    if song_url:
        return {"success": True, "url": song_url}
    return {"success": False, "url": None, "message": "Could not find a song after several attempts."}