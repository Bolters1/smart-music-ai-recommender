"""
Music Preference Prediction Pipeline

Workflow:
  python pipeline.py fetch-liked          # scrape liked songs from Last.fm
  python pipeline.py fetch-disliked       # scrape negative samples by genre
  python pipeline.py combine              # merge liked + disliked
  python pipeline.py process-all          # clean tags + TF-IDF + taste centroid
  python pipeline.py train                # train Random Forest model
  python pipeline.py predict "Artist" "Song"
  python pipeline.py predict-batch songs.txt
  python pipeline.py add-negatives
  python pipeline.py smart-negatives
  python pipeline.py reclassify
  python pipeline.py recommend
  python pipeline.py sync-recent
  python pipeline.py generate-weekly
  python pipeline.py generate-prompt "muzica trista atmosferica"
  python pipeline.py analyze-tags
"""

import os
import re
import sys

# Fix Windows console encoding (cp1252 can't handle Romanian ă, ț, ș, â, î)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import csv
import time
import json
import random
import string
import argparse
import threading
import urllib.parse
import concurrent.futures
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta

from dotenv import load_dotenv
import requests
import pandas as pd
import numpy as np
import joblib
import lightgbm as lgb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, roc_auc_score, f1_score
from google import genai as google_genai


# --- Config ---

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "")
LASTFM_USERNAME = os.getenv("LASTFM_USERNAME", "Spinachio")
LASTFM_BASE_URL = "http://ws.audioscrobbler.com/2.0/"
LASTFM_DELAY = 0.5

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    _GEMINI_CLIENT = google_genai.Client(api_key=GEMINI_API_KEY)
else:
    _GEMINI_CLIENT = None
    print("[WARNING] GEMINI_API_KEY nu e setat in .env - generate-prompt nu va functiona.")

FILE_LIKED_RAW = BASE_DIR / "music_database.csv"
FILE_DISLIKED_RAW = BASE_DIR / "top_songs.csv"
FILE_MASTER = BASE_DIR / "master_dataset_pre_spotify.csv"
FILE_PROCESSED_ALL = BASE_DIR / "processed_all_songs.csv"
FILE_MODEL = BASE_DIR / "model_tags_only.pkl"
FILE_VECTORIZER = BASE_DIR / "tfidf_vectorizer_tags_only.pkl"
FILE_FEATURE_COLS = BASE_DIR / "feature_columns_tags_only.json"
FILE_TASTE_CENTROID = BASE_DIR / "taste_centroid.pkl"
FILE_TAG_CACHE = BASE_DIR / "tags_cache.json"
FILE_LAST_SYNC = BASE_DIR / ".last_sync.json"

META_COLS = ['Artist Name', 'Song Name', 'Plays', 'Rank', 'Tags',
             'Track Tags', 'Artist Tags', 'Target', 'MBID', 'Unnamed: 0']

DEFAULT_NEGATIVE_GENRES = ['pop', 'contemporary country', 'kpop', 'reggaeton', 'trap']

# Fallback prompt -> tag mapping (used when Gemini is unavailable)
PROMPT_TAG_MAP = {
    'trist': 'sad melancholic', 'trista': 'sad melancholic',
    'vesel': 'happy upbeat', 'energic': 'energetic upbeat',
    'calm': 'calm ambient chill', 'relaxare': 'chill ambient relaxing',
    'agresiv': 'aggressive heavy', 'romantic': 'romantic love',
    'melancolic': 'melancholic sad atmospheric', 'nostalgic': 'nostalgic melancholic',
    'dark': 'dark gothic post-punk', 'ploaie': 'atmospheric melancholic dreamy',
    'ploioasa': 'atmospheric melancholic dreamy',
    'rock': 'rock', 'hip-hop': 'hip-hop rap', 'rap': 'rap hip-hop',
    'electronic': 'electronic', 'jazz': 'jazz',
    'shoegaze': 'shoegaze dream pop', 'post-punk': 'post-punk gothic',
    'metal': 'metal heavy', 'indie': 'indie alternative',
    'ambient': 'ambient atmospheric', 'sport': 'energetic workout upbeat',
    'somn': 'ambient calm sleep', 'studiu': 'ambient instrumental focus',
    'condus': 'driving rock energetic', 'petrecere': 'party dance upbeat',
}


# --- Tag Cache (thread-safe) ---

_TAG_CACHE = {"artist": {}, "track": {}}
_TAG_CACHE_LOADED = False
CACHE_LOCK = threading.Lock()


def _load_tag_cache():
    global _TAG_CACHE, _TAG_CACHE_LOADED
    if _TAG_CACHE_LOADED:
        return

    if FILE_TAG_CACHE.exists():
        try:
            with open(FILE_TAG_CACHE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _TAG_CACHE['artist'] = data.get('artist', {})
                _TAG_CACHE['track'] = data.get('track', {})
        except Exception as e:
            print(f"  [!] Exception loading tag cache: {e}")

    # Pre-populate from master dataset
    if FILE_MASTER.exists():
        try:
            df = pd.read_csv(FILE_MASTER)
            for _, row in df.iterrows():
                a = str(row.get('Artist Name', '')).strip().lower()
                s = str(row.get('Song Name', '')).strip().lower()
                t_tags = str(row.get('Track Tags', '')).strip()
                a_tags = str(row.get('Artist Tags', '')).strip()

                if a and a_tags and a not in _TAG_CACHE['artist']:
                    _TAG_CACHE['artist'][a] = [x.strip() for x in a_tags.split(',') if x.strip()]
                if a and s and t_tags:
                    key = f"{a}:::{s}"
                    if key not in _TAG_CACHE['track']:
                        _TAG_CACHE['track'][key] = [x.strip() for x in t_tags.split(',') if x.strip()]
        except Exception:
            pass

    _TAG_CACHE_LOADED = True


def _save_tag_cache():
    try:
        with CACHE_LOCK:
            with open(FILE_TAG_CACHE, 'w', encoding='utf-8') as f:
                json.dump(_TAG_CACHE, f, ensure_ascii=False)
    except Exception:
        pass


# --- Last.fm API ---

def lastfm_request(method, **params):
    """Last.fm API request with retry logic."""
    params['api_key'] = LASTFM_API_KEY
    params['format'] = 'json'
    params['method'] = method

    for attempt in range(3):
        try:
            response = requests.get(LASTFM_BASE_URL, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 503:
                print(f"  Rate limit! Astept {5 * (attempt + 1)}s...")
                time.sleep(5 * (attempt + 1))
            else:
                return None
        except (requests.RequestException, ValueError) as e:
            print(f"  Eroare request (incercare {attempt + 1}/3): {e}")
            time.sleep(2)
    return None


def get_track_tags(artist, track):
    """Get track tags from Last.fm (cached)."""
    _load_tag_cache()
    key = f"{artist.strip().lower()}:::{track.strip().lower()}"
    with CACHE_LOCK:
        if key in _TAG_CACHE['track']:
            return _TAG_CACHE['track'][key]

    data = lastfm_request('track.getTopTags',
                           artist=urllib.parse.quote(artist),
                           track=urllib.parse.quote(track))
    if not data:
        return []

    tags = [tag['name'] for tag in data.get('toptags', {}).get('tag', []) if isinstance(tag, dict)]

    with CACHE_LOCK:
        _TAG_CACHE['track'][key] = tags
    _save_tag_cache()
    return tags


def get_artist_tags(artist):
    """Get artist tags from Last.fm (cached)."""
    _load_tag_cache()
    key = artist.strip().lower()
    with CACHE_LOCK:
        if key in _TAG_CACHE['artist']:
            return _TAG_CACHE['artist'][key]

    data = lastfm_request('artist.getTopTags', artist=urllib.parse.quote(artist))
    if not data:
        return []

    tags = [tag['name'] for tag in data.get('toptags', {}).get('tag', []) if isinstance(tag, dict)]

    with CACHE_LOCK:
        _TAG_CACHE['artist'][key] = tags
    _save_tag_cache()
    return tags


# --- Data Collection ---

def fetch_liked_songs(username=LASTFM_USERNAME, max_pages=72, limit_per_page=200):
    """Scrape user's top tracks from Last.fm -> Target = 1."""
    output_file = FILE_LIKED_RAW
    print(f"\n{'='*60}")
    print(f"  FETCH LIKED SONGS -- user: {username}")
    print(f"{'='*60}\n")

    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(['Artist Name', 'Song Name', 'Plays', 'Rank', 'Track Tags', 'Artist Tags'])

    total_songs = 0
    for page in range(1, max_pages + 1):
        print(f"--- Pagina {page}/{max_pages} ---")
        data = lastfm_request('user.getTopTracks', user=username, limit=limit_per_page, page=page)
        if not data:
            continue

        tracks = data.get('toptracks', {}).get('track', [])
        if not tracks:
            break

        for song in tracks:
            artist = song['artist']['name']
            name = song['name']
            track_tags = get_track_tags(artist, name)
            time.sleep(LASTFM_DELAY)
            artist_tags = get_artist_tags(artist)
            time.sleep(LASTFM_DELAY)

            row = [artist, name, song.get('playcount', 0), song.get('@attr', {}).get('rank', 0),
                   ", ".join(track_tags), ", ".join(artist_tags)]

            with open(output_file, mode='a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(row)
            total_songs += 1

    print(f"\n[OK] {total_songs} piese liked salvate in {output_file}")
    return total_songs


def fetch_disliked_songs(genres=None, max_pages=2, limit_per_page=200):
    """Scrape top tracks for genres the user doesn't listen to -> Target = 0."""
    if genres is None:
        genres = DEFAULT_NEGATIVE_GENRES
    output_file = FILE_DISLIKED_RAW

    print(f"\n{'='*60}")
    print(f"  FETCH DISLIKED SONGS -- genuri: {genres}")
    print(f"{'='*60}\n")

    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(['Artist Name', 'Song Name', 'Plays', 'Rank', 'Track Tags', 'Artist Tags'])

    total_songs = 0
    for genre in genres:
        print(f"\n--- Gen: {genre} ---")
        for page in range(1, max_pages + 1):
            data = lastfm_request('tag.gettoptracks', tag=genre, limit=limit_per_page, page=page)
            if not data:
                continue
            tracks = data.get('tracks', {}).get('track', [])
            if not tracks:
                break

            for song in tracks:
                artist = song['artist']['name']
                name = song['name']
                track_tags = get_track_tags(artist, name)
                time.sleep(LASTFM_DELAY)
                artist_tags = get_artist_tags(artist)
                time.sleep(LASTFM_DELAY)

                row = [artist, name, song.get('playcount', 0), song.get('@attr', {}).get('rank', 0),
                       ", ".join(track_tags), ", ".join(artist_tags)]

                with open(output_file, mode='a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(row)
                total_songs += 1

    print(f"\n[OK] {total_songs} piese disliked salvate in {output_file}")
    return total_songs


def combine_datasets():
    """Merge liked (Target=1) + disliked (Target=0), remove duplicates."""
    print(f"\n{'='*60}")
    print(f"  COMBINE DATASETS")
    print(f"{'='*60}\n")

    if not FILE_LIKED_RAW.exists() or not FILE_DISLIKED_RAW.exists():
        print("[ERR] Lipsesc fisierele. Ruleaza 'fetch-liked' si 'fetch-disliked' mai intai.")
        return

    df_liked = pd.read_csv(FILE_LIKED_RAW)
    df_liked['Target'] = 1
    df_disliked = pd.read_csv(FILE_DISLIKED_RAW)
    df_disliked['Target'] = 0

    df = pd.concat([df_liked, df_disliked], ignore_index=True)
    before = len(df)
    df = df.drop_duplicates(subset=['Artist Name', 'Song Name'], keep='first')

    print(f"  Liked: {len(df_liked)}, Disliked: {len(df_disliked)}")
    print(f"  Duplicate eliminate: {before - len(df)}, Total final: {len(df)}")

    df.to_csv(FILE_MASTER, index=False)
    print(f"\n[OK] Salvat in {FILE_MASTER}")


# --- Tag Processing ---

def clean_tag_text(text):
    """Clean a tag string: lowercase, remove punctuation, collapse spaces."""
    if pd.isna(text) or not str(text).strip():
        return ""

    cleaned = []
    for tag in str(text).split(','):
        t = tag.lower().strip()
        t = re.sub(r'[^a-z0-9\s]', '', t)
        t = t.replace(" ", "")  # "hip hop" -> "hiphop"
        if t:
            cleaned.append(t)
    return " ".join(cleaned)


def clean_and_merge_tags(df):
    """Clean Track Tags + Artist Tags and merge into a single 'Tags' column."""
    if 'Track Tags' in df.columns and 'Artist Tags' in df.columns:
        df['TTags'] = df['Track Tags'].apply(clean_tag_text)
        df['ATags'] = df['Artist Tags'].apply(clean_tag_text)
        df['Tags'] = (df['ATags'].fillna('') + " " + df['TTags'].fillna('')).str.strip()
        df = df.drop(['Track Tags', 'Artist Tags', 'TTags', 'ATags'], axis=1, errors='ignore')
    elif 'Tags' in df.columns:
        df['Tags'] = df['Tags'].apply(clean_tag_text)
    else:
        df['Tags'] = ""
    return df


# --- Vectorization ---

def vectorize_tags(df, max_features=200, vectorizer=None):
    """Apply TF-IDF on the 'Tags' column. Returns (df_with_tfidf, fitted_vectorizer)."""
    df['Tags'] = df['Tags'].fillna('')

    if vectorizer is None:
        vectorizer = TfidfVectorizer(max_features=max_features)
        tfidf_matrix = vectorizer.fit_transform(df['Tags'])
    else:
        tfidf_matrix = vectorizer.transform(df['Tags'])

    tfidf_df = pd.DataFrame(tfidf_matrix.toarray(), columns=vectorizer.get_feature_names_out(), index=df.index)
    return pd.concat([df, tfidf_df], axis=1), vectorizer


# --- Processing & Training ---

def process_all_songs():
    """Process all songs: clean tags, TF-IDF, compute taste centroid + cosine similarity."""
    print(f"\n{'='*60}")
    print(f"  PROCESS ALL SONGS")
    print(f"{'='*60}\n")

    if not FILE_MASTER.exists():
        print(f"[ERR] {FILE_MASTER} nu exista!")
        return

    df = pd.read_csv(FILE_MASTER)
    print(f"  Incarcat {len(df)} piese (Target=1: {(df['Target']==1).sum()}, Target=0: {(df['Target']==0).sum()})")

    df = clean_and_merge_tags(df)
    empty_tags = (df['Tags'] == '') | df['Tags'].isna()
    df = df[~empty_tags].reset_index(drop=True)
    print(f"  Piese cu tag-uri valide: {len(df)}")

    df, vectorizer = vectorize_tags(df, max_features=200)
    joblib.dump(vectorizer, FILE_VECTORIZER)

    # Taste centroid (weighted by log playcount)
    df_liked = df[df['Target'] == 1]
    vocab_cols = vectorizer.get_feature_names_out()
    X_liked = df_liked[vocab_cols].fillna(0).values

    plays = pd.to_numeric(df_liked['Plays'], errors='coerce').fillna(0).clip(lower=0)
    weights = np.log1p(plays) + 1
    taste_centroid = np.dot(weights.values, X_liked) / weights.sum()
    joblib.dump(taste_centroid, FILE_TASTE_CENTROID)

    # Cosine similarity for all songs
    X_all = df[vocab_cols].fillna(0).values
    df['Cosine_Sim'] = cosine_similarity(taste_centroid.reshape(1, -1), X_all)[0]

    df.to_csv(FILE_PROCESSED_ALL, index=False)
    print(f"\n[OK] Salvat {len(df)} piese procesate in {FILE_PROCESSED_ALL}")
    return df


def get_feature_columns(df):
    """Return feature columns (exclude metadata and Cosine_Sim)."""
    exclude = set(META_COLS) | {'Cosine_Sim'}
    return [c for c in df.columns if c not in exclude]


def train_and_evaluate(X, y, model_name="Model", n_splits=5, sample_weights=None):
    """Train and evaluate a Random Forest with cross-validation."""
    print(f"\n  --- {model_name} ---")
    print(f"  Features: {X.shape[1]}, Samples: {X.shape[0]}")

    if sample_weights is not None:
        X_train, X_test, y_train, y_test, w_train, _ = train_test_split(
            X, y, sample_weights, test_size=0.20, random_state=42, stratify=y)
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42, stratify=y)
        w_train = None

    model = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42, n_jobs=-1)

    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    cv_acc = cross_val_score(model, X_train, y_train, cv=cv, scoring='accuracy')
    cv_f1 = cross_val_score(model, X_train, y_train, cv=cv, scoring='f1')
    cv_auc = cross_val_score(model, X_train, y_train, cv=cv, scoring='roc_auc')

    print(f"  CV Accuracy: {cv_acc.mean():.4f}, F1: {cv_f1.mean():.4f}, AUC: {cv_auc.mean():.4f}")

    model.fit(X_train, y_train, sample_weight=w_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print(f"  Test Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"  Test F1: {f1_score(y_test, y_pred):.4f}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['Disliked', 'Liked'])}")

    cm = confusion_matrix(y_test, y_pred)
    print("  Confusion Matrix:")
    print("                  Predicted Disliked (0)   Predicted Liked (1)")
    print(f"  Actual Disliked (0)  {cm[0][0]:>18}   {cm[0][1]:>19}")
    print(f"  Actual Liked (1)     {cm[1][0]:>18}   {cm[1][1]:>19}\n")

    # Top 20 features
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:20]
    feature_names = X.columns.tolist()
    print("  Top 20 Features:")
    for i, idx in enumerate(indices):
        print(f"    {i+1:>2}. {feature_names[idx]:<30} {importances[idx]:.4f}")

    return model, {
        'cv_accuracy': f"{cv_acc.mean():.4f}", 'cv_f1': f"{cv_f1.mean():.4f}",
        'test_accuracy': f"{accuracy_score(y_test, y_pred):.4f}",
        'test_f1': f"{f1_score(y_test, y_pred):.4f}",
    }


def train_models():
    """Train the tags-only model on all processed songs."""
    print(f"\n{'='*60}")
    print(f"  TRAIN MODEL (Tags Only)")
    print(f"{'='*60}")

    if not FILE_PROCESSED_ALL.exists():
        print(f"  [!] {FILE_PROCESSED_ALL} nu exista. Ruleaza 'process-all' mai intai.")
        return

    df = pd.read_csv(FILE_PROCESSED_ALL, low_memory=False)
    feature_cols = get_feature_columns(df)
    X = df[feature_cols].fillna(0)
    y = df['Target']

    # Sample weights based on playcount
    plays = pd.to_numeric(df['Plays'], errors='coerce').fillna(0).clip(lower=0)
    weights = np.log1p(plays) + 1
    weights = weights / weights.mean()

    model, metrics = train_and_evaluate(X, y, "Tags Only (Weighted)", sample_weights=weights.values)

    joblib.dump(model, FILE_MODEL)
    with open(FILE_FEATURE_COLS, 'w') as f:
        json.dump(feature_cols, f)

    print(f"\n  Model salvat: {FILE_MODEL}")
    print(f"  Feature columns salvate: {FILE_FEATURE_COLS}")


# --- Prediction ---

def verify_track_exists(artist, track):
    """Check if a track exists on Last.fm."""
    data = lastfm_request('track.getInfo', artist=artist, track=track)
    return data is not None and 'error' not in data


def predict_song(artist, song_name):
    """End-to-end prediction for a single song."""
    print(f"\n  Predictie pentru: {artist} - {song_name}")

    if not verify_track_exists(artist, song_name):
        print(f"  [ERR] Piesa nu a fost gasita pe Last.fm!")
        return None
    time.sleep(LASTFM_DELAY)

    track_tags = get_track_tags(artist, song_name)
    time.sleep(LASTFM_DELAY)
    artist_tags = get_artist_tags(artist)
    cleaned_tags = clean_tag_text(", ".join(artist_tags + track_tags))

    if not cleaned_tags.strip():
        print(f"  [ERR] Nu s-au putut extrage tag-uri valide!")
        return None

    for path in [FILE_MODEL, FILE_VECTORIZER, FILE_FEATURE_COLS]:
        if not path.exists():
            print(f"[ERR] {path.name} nu exista. Ruleaza 'train' mai intai.")
            return None

    model = joblib.load(FILE_MODEL)
    vectorizer = joblib.load(FILE_VECTORIZER)
    with open(FILE_FEATURE_COLS, 'r') as f:
        feature_cols = json.load(f)

    tfidf_matrix = vectorizer.transform([cleaned_tags])
    tfidf_df = pd.DataFrame(tfidf_matrix.toarray(), columns=vectorizer.get_feature_names_out())

    feature_vector = pd.DataFrame(0, index=[0], columns=feature_cols)
    for col in tfidf_df.columns:
        if col in feature_vector.columns:
            feature_vector[col] = tfidf_df[col].values

    # Cosine similarity with taste profile (for display only)
    if FILE_TASTE_CENTROID.exists():
        taste_centroid = joblib.load(FILE_TASTE_CENTROID)
        vocab_cols = vectorizer.get_feature_names_out()
        song_vec = np.zeros(len(vocab_cols))
        for i, col in enumerate(vocab_cols):
            if col in tfidf_df.columns:
                song_vec[i] = tfidf_df[col].values[0]
        sim = cosine_similarity(taste_centroid.reshape(1, -1), song_vec.reshape(1, -1))[0][0]
        print(f"  Cosine Similarity cu gusturile tale: {sim:.2%}")

    prediction = model.predict(feature_vector)[0]
    probability = model.predict_proba(feature_vector)[0]

    liked = prediction == 1
    emoji = "<3" if liked else "[X]"
    label = "ITI PLACE" if liked else "NU ITI PLACE"

    print(f"\n  {emoji} Predictie: {label}")
    print(f"  Probabilitate liked: {probability[1]:.1%}, disliked: {probability[0]:.1%}")

    return {
        'artist': artist, 'song': song_name, 'prediction': int(prediction),
        'liked': liked, 'prob_liked': float(probability[1]), 'tags': cleaned_tags
    }


def predict_batch(songs_file):
    """Batch predictions from a text file (format: Artist - Song per line)."""
    if not os.path.exists(songs_file):
        print(f"[ERR] Fisierul {songs_file} nu exista!")
        return

    print(f"\n{'='*60}\n  BATCH PREDICTION\n{'='*60}\n")

    results = []
    with open(songs_file, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    for i, line in enumerate(lines):
        if ' - ' not in line:
            continue
        artist, song = line.split(' - ', 1)
        print(f"\n  [{i+1}/{len(lines)}]")
        result = predict_song(artist.strip(), song.strip())
        if result:
            results.append(result)
        time.sleep(LASTFM_DELAY)

    if results:
        print(f"\n\n{'='*60}\n  SUMAR PREDICTII\n{'='*60}\n")
        for r in results:
            emoji = "<3" if r['liked'] else "[X]"
            print(f"  {r['artist']:<25} {r['song']:<30} {emoji:<12} {r['prob_liked']:.1%}")

    return results


# --- Dataset Management ---

def add_negatives(genres=None, max_pages=2):
    """Add new negative samples to master dataset (with individual tag fetching)."""
    if genres is None:
        genres = ['schlager', 'latin pop', 'gospel', 'children', 'new age',
                  'smooth jazz', 'dancehall', 'cumbia', 'bollywood', 'folk metal']

    print(f"\n{'='*60}\n  ADD NEGATIVE SAMPLES\n{'='*60}\n")

    if not FILE_MASTER.exists():
        print(f"[ERR] {FILE_MASTER} nu exista!")
        return

    df_master = pd.read_csv(FILE_MASTER)
    existing = set(zip(df_master['Artist Name'].str.lower(), df_master['Song Name'].str.lower()))
    new_songs = []

    for genre in genres:
        print(f"\n  --- Gen: {genre} ---")
        for page in range(1, max_pages + 1):
            data = lastfm_request('tag.gettoptracks', tag=genre, limit=200, page=page)
            if not data:
                continue
            tracks = data.get('tracks', {}).get('track', [])
            if not tracks:
                break

            for song in tracks:
                artist, name = song['artist']['name'], song['name']
                if (artist.lower(), name.lower()) in existing:
                    continue

                t_tags = get_track_tags(artist, name)
                time.sleep(LASTFM_DELAY)
                a_tags = get_artist_tags(artist)
                time.sleep(LASTFM_DELAY)

                new_songs.append({
                    'Artist Name': artist, 'Song Name': name,
                    'Plays': song.get('playcount', 0), 'Rank': 0,
                    'Track Tags': ", ".join(t_tags), 'Artist Tags': ", ".join(a_tags), 'Target': 0
                })
                existing.add((artist.lower(), name.lower()))

    if new_songs:
        df = pd.concat([df_master, pd.DataFrame(new_songs)], ignore_index=True)
        df.to_csv(FILE_MASTER, index=False)
        print(f"\n[OK] Adaugat {len(new_songs)} piese negative! Total: {len(df)}")


def smart_negatives(genres=None, max_pages=2):
    """Add negative samples FAST (uses genre tag directly, no individual API calls)."""
    if genres is None:
        genres = ['hard rock', 'classic rock', 'heavy metal', 'hair metal',
                  'power metal', 'thrash metal', 'nu metal', 'southern rock',
                  'arena rock', 'glam rock', 'blues rock', 'punk',
                  'schlager', 'new age', 'smooth jazz', 'gospel',
                  'children', 'bollywood', 'cumbia', 'dancehall']

    print(f"\n{'='*60}\n  SMART NEGATIVES (fast mode)\n{'='*60}\n")

    if not FILE_MASTER.exists():
        print(f"[ERR] {FILE_MASTER} nu exista!")
        return

    df_master = pd.read_csv(FILE_MASTER)
    existing = set(zip(df_master['Artist Name'].str.lower().fillna(''),
                       df_master['Song Name'].str.lower().fillna('')))
    new_songs = []

    for genre in genres:
        genre_count = 0
        for page in range(1, max_pages + 1):
            data = lastfm_request('tag.gettoptracks', tag=genre, limit=200, page=page)
            if not data:
                continue
            tracks = data.get('tracks', {}).get('track', [])
            if not tracks:
                break

            for song in tracks:
                artist, name = song['artist']['name'], song['name']
                if (artist.lower(), name.lower()) in existing:
                    continue
                new_songs.append({
                    'Artist Name': artist, 'Song Name': name,
                    'Plays': 0, 'Rank': 0,
                    'Track Tags': genre, 'Artist Tags': genre, 'Target': 0
                })
                existing.add((artist.lower(), name.lower()))
                genre_count += 1

        print(f"  {genre}: +{genre_count} piese")

    if new_songs:
        df = pd.concat([df_master, pd.DataFrame(new_songs)], ignore_index=True)
        df.to_csv(FILE_MASTER, index=False)
        print(f"\n[OK] Adaugat {len(new_songs)} piese negative! Total: {len(df)}")


def reclassify_by_playcount(max_playcount=1):
    """Reclassify songs with low playcount from Target=1 to Target=0."""
    print(f"\n{'='*60}\n  RECLASSIFY BY PLAYCOUNT (<= {max_playcount})\n{'='*60}\n")

    if not FILE_MASTER.exists():
        print(f"[ERR] {FILE_MASTER} nu exista!")
        return

    # Backup
    backup_file = BASE_DIR / "master_dataset_BACKUP.csv"
    if not backup_file.exists():
        import shutil
        shutil.copy2(FILE_MASTER, backup_file)
        print(f"  Backup creat: {backup_file}")

    df = pd.read_csv(FILE_MASTER)
    mask = (df['Target'] == 1) & (df['Plays'] <= max_playcount)
    print(f"  Piese reclasificate: {mask.sum()}")
    df.loc[mask, 'Target'] = 0
    df.to_csv(FILE_MASTER, index=False)

    print(f"  Target=1: {(df['Target']==1).sum()}, Target=0: {(df['Target']==0).sum()}")
    print(f"\n[OK] Ruleaza 'process-all' si 'train' pentru re-antrenare.")


def analyze_tags(input_file=None):
    """Display most frequent tags in the dataset."""
    if input_file is None:
        if FILE_PROCESSED_ALL.exists():
            input_file = FILE_PROCESSED_ALL
        elif FILE_MASTER.exists():
            input_file = FILE_MASTER
        else:
            print("[ERR] Nu gasesc niciun dataset!")
            return

    df = pd.read_csv(input_file)
    if 'Tags' not in df.columns:
        df = clean_and_merge_tags(df)

    all_tags = []
    for tags_str in df['Tags'].dropna():
        all_tags.extend(str(tags_str).split())

    counter = Counter(all_tags)
    print(f"\n  Top 50 tag-uri ({len(counter)} unice, {len(df)} piese):\n")
    for tag, count in counter.most_common(50):
        print(f"  {tag:<30} {count:<10} {count/len(df)*100:.1f}%")


# --- Recommendation Engine ---

def get_recommendation_candidates(num_candidates=15):
    """Generate diverse candidate songs using 3 strategies:
    A: Safe Artist Deep Cuts, B: Similar Artists, C: Similar Tracks."""

    if not FILE_MASTER.exists():
        return []

    df = pd.read_csv(FILE_MASTER)
    existing = set(zip(df['Artist Name'].str.lower().fillna(''),
                       df['Song Name'].str.lower().fillna('')))

    artist_plays = df[df['Target'] == 1].groupby('Artist Name')['Plays'].sum()
    safe_artists = artist_plays[artist_plays >= 50]
    if safe_artists.empty:
        safe_artists = artist_plays.head(10)

    weights = safe_artists.values / safe_artists.values.sum()
    candidates = []
    seen = set()
    strategies = ['safe_deep_cuts', 'similar_artists', 'similar_tracks']

    for _ in range(30):
        if len(candidates) >= num_candidates:
            break

        strategy = np.random.choice(strategies)

        if strategy == 'safe_deep_cuts' and not safe_artists.empty:
            artist = np.random.choice(safe_artists.index, p=weights)
            data = lastfm_request('artist.getTopTracks', artist=artist, limit=100)
            if data:
                tracks = data.get('toptracks', {}).get('track', [])
                if isinstance(tracks, list):
                    np.random.shuffle(tracks)
                    for t in tracks:
                        key = (t['artist']['name'].lower(), t['name'].lower())
                        if key not in existing and key not in seen:
                            candidates.append({'Artist Name': t['artist']['name'], 'Song Name': t['name']})
                            seen.add(key)
                            break

        elif strategy == 'similar_artists' and not safe_artists.empty:
            artist = np.random.choice(safe_artists.index, p=weights)
            data = lastfm_request('artist.getSimilar', artist=artist, limit=10)
            if data:
                sim_artists = data.get('similarartists', {}).get('artist', [])
                if isinstance(sim_artists, list):
                    np.random.shuffle(sim_artists)
                    for art in sim_artists:
                        sim_name = art['name']
                        if df[df['Artist Name'].str.lower() == sim_name.lower()].empty:
                            td = lastfm_request('artist.getTopTracks', artist=sim_name, limit=5)
                            if td:
                                for t in td.get('toptracks', {}).get('track', []):
                                    key = (sim_name.lower(), t['name'].lower())
                                    if key not in existing and key not in seen:
                                        candidates.append({'Artist Name': sim_name, 'Song Name': t['name']})
                                        seen.add(key)
                                        break
                                break

        elif strategy == 'similar_tracks':
            top = df[(df['Target'] == 1) & (df['Plays'] >= 10)].sort_values('Plays', ascending=False)
            if not top.empty:
                row = top.iloc[:min(len(top), 50)].sample(1).iloc[0]
                data = lastfm_request('track.getSimilar', artist=row['Artist Name'], track=row['Song Name'], limit=10)
                if data:
                    sim = data.get('similartracks', {}).get('track', [])
                    if isinstance(sim, list):
                        np.random.shuffle(sim)
                        for t in sim:
                            key = (t['artist']['name'].lower(), t['name'].lower())
                            if key not in existing and key not in seen:
                                candidates.append({'Artist Name': t['artist']['name'], 'Song Name': t['name']})
                                seen.add(key)
                                break

    print(f"  [OK] {len(candidates)} piese candidate gasite.")
    return candidates


def run_recommendations(limit_display=5):
    """Active recommendation loop with ML scoring and interactive feedback."""
    print(f"\n{'='*60}\n  RECOMMENDATION ENGINE\n{'='*60}\n")

    if not FILE_MODEL.exists() or not FILE_VECTORIZER.exists():
        print("[ERR] Modelul nu este antrenat!")
        return

    model = joblib.load(FILE_MODEL)
    vectorizer = joblib.load(FILE_VECTORIZER)
    with open(FILE_FEATURE_COLS, 'r') as f:
        feature_cols = json.load(f)

    candidates = get_recommendation_candidates()
    if not candidates:
        return

    # Score candidates through ML
    scored = []
    for c in candidates[:20]:
        artist, song = c['Artist Name'], c['Song Name']
        t_tags = get_track_tags(artist, song)
        time.sleep(LASTFM_DELAY)
        a_tags = get_artist_tags(artist)
        time.sleep(LASTFM_DELAY)

        cleaned = clean_tag_text(", ".join(a_tags + t_tags))
        if not cleaned.strip():
            continue

        tfidf = vectorizer.transform([cleaned])
        tfidf_df = pd.DataFrame(tfidf.toarray(), columns=vectorizer.get_feature_names_out())

        fv = pd.DataFrame(0, index=[0], columns=feature_cols)
        for col in tfidf_df.columns:
            if col in fv.columns:
                fv[col] = tfidf_df[col].values

        prob = model.predict_proba(fv)[0][1]
        scored.append({**c, 'prob_liked': prob,
                       'track_tags': ", ".join(t_tags), 'artist_tags': ", ".join(a_tags)})

    scored.sort(key=lambda x: x['prob_liked'], reverse=True)

    # Interactive swipe loop
    df_master = pd.read_csv(FILE_MASTER)
    new_feedbacks = []

    for i, c in enumerate(scored[:limit_display]):
        print(f"\n[{i+1}/{limit_display}] {c['Artist Name']} - {c['Song Name']} (Match: {c['prob_liked']:.1%})")

        while True:
            feedback = input("    (1-Like / 0-Dislike / s-Skip / q-Quit): ").strip().lower()
            if feedback == 'q':
                break
            elif feedback == 's':
                break
            elif feedback in ['1', '0']:
                new_feedbacks.append({
                    'Artist Name': c['Artist Name'], 'Song Name': c['Song Name'],
                    'Plays': 0, 'Rank': 0,
                    'Track Tags': c['track_tags'], 'Artist Tags': c['artist_tags'],
                    'Target': int(feedback)
                })
                print(f"    {'Liked' if feedback == '1' else 'Disliked'}!")
                break
        if feedback == 'q':
            break

    if new_feedbacks:
        df = pd.concat([df_master, pd.DataFrame(new_feedbacks)], ignore_index=True)
        df = df.drop_duplicates(subset=['Artist Name', 'Song Name'], keep='last')
        df.to_csv(FILE_MASTER, index=False)
        print(f"\n[OK] {len(new_feedbacks)} interactiuni salvate. Ruleaza 'process-all' + 'train' pt update.")


# --- Sync & Playlist Generation ---

def sync_recent_tracks(days=7, min_interval_hours=6, force=False):
    """Sync recent listening history from Last.fm into master dataset.
    Throttled by default: skips if last sync was within min_interval_hours unless force=True."""
    print(f"\n{'='*60}\n  SYNC RECENT TRACKS ({days} zile)\n{'='*60}\n")

    if not FILE_MASTER.exists():
        print("[ERR] master dataset nu exista!")
        return False

    # Check last sync timestamp
    now_ts = int(time.time())
    if not force and FILE_LAST_SYNC.exists():
        try:
            with open(FILE_LAST_SYNC, 'r', encoding='utf-8') as f:
                sync_info = json.load(f)
                last_ts = sync_info.get('last_sync_timestamp', 0)
                hours_passed = (now_ts - last_ts) / 3600.0
                if hours_passed < min_interval_hours:
                    print(f"  [INFO] Sincronizarea a fost facuta recent ({hours_passed:.1f} ore in urma). Sar peste sync.")
                    return False
        except Exception:
            pass

    df_master = pd.read_csv(FILE_MASTER)
    existing = {}
    for idx, row in df_master.iterrows():
        key = (row['Artist Name'].lower().strip(), row['Song Name'].lower().strip())
        existing[key] = {'index': idx, 'Plays': int(row['Plays']), 'Target': int(row['Target'])}

    uts_from = int((datetime.now() - timedelta(days=days)).timestamp())

    # Pull recent tracks from Last.fm — also store original casing
    recent_plays = Counter()
    original_casing = {}  # (lower_artist, lower_song) -> (Artist, Song)
    page = 1
    while True:
        data = lastfm_request('user.getRecentTracks', user=LASTFM_USERNAME, from_time=uts_from, limit=200, page=page)
        if not data:
            break

        tracks = data.get('recenttracks', {}).get('track', [])
        if not tracks:
            break
        if isinstance(tracks, dict):
            tracks = [tracks]

        for t in tracks:
            if t.get('@attr', {}).get('nowplaying') == 'true':
                continue
            artist_orig = t['artist']['#text'].strip()
            song_orig = t['name'].strip()
            key = (artist_orig.lower(), song_orig.lower())
            recent_plays[key] += 1
            if key not in original_casing:
                original_casing[key] = (artist_orig, song_orig)

        total_pages = int(data.get('recenttracks', {}).get('@attr', {}).get('totalPages', 1))
        if page >= 2 or page >= total_pages:
            break
        page += 1

    print(f"  {sum(recent_plays.values())} redari, {len(recent_plays)} piese unice.")

    # Save sync timestamp regardless
    try:
        with open(FILE_LAST_SYNC, 'w', encoding='utf-8') as f:
            json.dump({
                'last_sync_timestamp': now_ts,
                'last_sync_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, f)
    except Exception:
        pass

    if not recent_plays:
        print("  Baza de date e la zi!")
        return False

    # Update master dataset
    new_rows = []
    for (artist_l, song_l), new_plays in recent_plays.items():
        original_artist, original_song = original_casing.get((artist_l, song_l), (artist_l, song_l))

        key = (artist_l, song_l)
        if key in existing:
            info = existing[key]
            new_total = info['Plays'] + new_plays
            df_master.at[info['index'], 'Plays'] = new_total
            if new_total >= 3 and info['Target'] == 0:
                df_master.at[info['index'], 'Target'] = 1
                print(f"    [Promo] {original_artist} - {original_song} -> LIKED (Plays: {new_total})")
        else:
            # Song not in master — check Last.fm for TOTAL playcount to determine if truly new
            total_plays = new_plays
            try:
                info_data = lastfm_request('track.getInfo', track=original_song, artist=original_artist,
                                           username=LASTFM_USERNAME)
                if info_data and 'track' in info_data:
                    user_pc = info_data['track'].get('userplaycount', '0')
                    total_plays = max(int(user_pc), new_plays)
                time.sleep(LASTFM_DELAY)
            except Exception:
                pass

            t_tags = get_track_tags(original_artist, original_song)
            a_tags = get_artist_tags(original_artist)

            target = 1 if total_plays >= 3 else 0

            new_rows.append({
                'Artist Name': original_artist, 'Song Name': original_song,
                'Plays': total_plays, 'Rank': 0,
                'Track Tags': ", ".join(t_tags), 'Artist Tags': ", ".join(a_tags),
                'Target': target
            })

            if total_plays > new_plays:
                print(f"    [RECOVERED] {original_artist} - {original_song} ({total_plays} total plays, was missing from DB)")
            else:
                print(f"    [NEW] {original_artist} - {original_song} ({new_plays} plays)")

    if new_rows:
        df_master = pd.concat([df_master, pd.DataFrame(new_rows)], ignore_index=True)
    df_master.to_csv(FILE_MASTER, index=False)

    print(f"\n[OK] Sincronizare terminata!")
    process_all_songs()
    train_models()
    return True


def generate_weekly_playlist(days=7, num_recent=12, num_discovery=18):
    """Generate a personalized weekly playlist combining recent favorites + ML-filtered discoveries."""
    # Pasul 0: Sincronizam automat ultimele piese ascultate pe Last.fm in baza de date
    sync_recent_tracks(days=days)

    # Step 1: Get top tracks (try 7day -> 1month -> overall -> local master DB fallback)
    tracks = []
    for period in ['7day', '1month', 'overall']:
        data = lastfm_request('user.getTopTracks', user=LASTFM_USERNAME, period=period, limit=num_recent)
        if data:
            t_list = data.get('toptracks', {}).get('track', [])
            if isinstance(t_list, dict):
                t_list = [t_list]
            if t_list:
                tracks = t_list
                break

    recent_songs = []
    top_seeds = []

    if tracks:
        for t in tracks:
            artist = t['artist']['name'].strip()
            song = t['name'].strip()
            recent_songs.append({
                'Artist Name': artist, 'Song Name': song,
                'Plays_This_Week': int(t.get('playcount', 1)),
                'Match_Score': '100% (Listen History)', 'Type': 'Recent Favourite'
            })
            top_seeds.append((artist.lower(), song.lower(), artist, song))

    # Local fallback if Last.fm returned no recent seeds
    if not top_seeds and FILE_MASTER.exists():
        df_m = pd.read_csv(FILE_MASTER)
        liked_m = df_m[df_m['Target'] == 1].sort_values('Plays', ascending=False).head(num_recent)
        for _, r in liked_m.iterrows():
            art = str(r['Artist Name']).strip()
            sng = str(r['Song Name']).strip()
            recent_songs.append({
                'Artist Name': art, 'Song Name': sng,
                'Plays_This_Week': int(r.get('Plays', 1)),
                'Match_Score': '100% (Listen History)', 'Type': 'Recent Favourite'
            })
            top_seeds.append((art.lower(), sng.lower(), art, sng))

    print(f"  Ancore: {len(recent_songs)} piese recente.")

    # Step 2: Generate discovery candidates
    if not FILE_MASTER.exists() or not FILE_MODEL.exists():
        print("[ERR] Lipseste modelul sau datasetul!")
        return []

    df_master = pd.read_csv(FILE_MASTER)
    existing = set((a, s) for a, s, _, _ in top_seeds)
    candidates = []
    seen = set()

    # Select 10 random seeds from top 20
    pool = top_seeds[:min(len(top_seeds), 20)]
    seeds = random.sample(pool, min(len(pool), 10))

    print(f"  Generam descoperiri din {len(seeds)} seed-uri...")
    for s_idx, (_, _, orig_art, orig_s) in enumerate(seeds, 1):
        # Similar Artists
        data = lastfm_request('artist.getSimilar', artist=orig_art, limit=15)
        if data:
            for art in data.get('similarartists', {}).get('artist', []):
                td = lastfm_request('artist.getTopTracks', artist=art['name'], limit=5)
                if td:
                    for tr in td.get('toptracks', {}).get('track', []):
                        key = (art['name'].lower(), tr['name'].lower())
                        if key not in existing and key not in seen:
                            candidates.append({'Artist Name': art['name'], 'Song Name': tr['name']})
                            seen.add(key)
                            break

        # Similar Tracks
        data = lastfm_request('track.getSimilar', artist=orig_art, track=orig_s, limit=20)
        if data:
            for tr in data.get('similartracks', {}).get('track', []):
                key = (tr['artist']['name'].lower(), tr['name'].lower())
                if key not in existing and key not in seen:
                    candidates.append({'Artist Name': tr['artist']['name'], 'Song Name': tr['name']})
                    seen.add(key)

    # Safe Deep Cuts
    for _, _, orig_art, _ in top_seeds:
        data = lastfm_request('artist.getTopTracks', artist=orig_art, limit=20)
        if data:
            for tr in data.get('toptracks', {}).get('track', []):
                key = (orig_art.lower(), tr['name'].lower())
                if key not in existing and key not in seen:
                    candidates.append({'Artist Name': orig_art, 'Song Name': tr['name']})
                    seen.add(key)

    # Step 3: ML filtering
    model = joblib.load(FILE_MODEL)
    vectorizer = joblib.load(FILE_VECTORIZER)
    with open(FILE_FEATURE_COLS, 'r') as f:
        feature_cols = json.load(f)

    discovery_songs = []
    for threshold in [0.60, 0.50]:
        if len(discovery_songs) >= num_discovery:
            break
        for c in candidates:
            if len(discovery_songs) >= num_discovery:
                break
            artist, song = c['Artist Name'], c['Song Name']
            if any(d['Artist Name'].lower() == artist.lower() and d['Song Name'].lower() == song.lower()
                   for d in discovery_songs):
                continue

            t_tags = get_track_tags(artist, song)
            a_tags = get_artist_tags(artist)
            cleaned = clean_tag_text(", ".join(a_tags + t_tags))
            if not cleaned.strip():
                continue

            tfidf = vectorizer.transform([cleaned])
            tfidf_df = pd.DataFrame(tfidf.toarray(), columns=vectorizer.get_feature_names_out())
            fv = pd.DataFrame(0, index=[0], columns=feature_cols)
            for col in tfidf_df.columns:
                if col in fv.columns:
                    fv[col] = tfidf_df[col].values

            prob = model.predict_proba(fv)[0][1]
            if prob >= threshold:
                discovery_songs.append({
                    'Artist Name': artist, 'Song Name': song,
                    'Plays_This_Week': 0, 'Match_Score': f"{prob:.1%}", 'Type': 'New Discovery'
                })
                print(f"    [+{len(discovery_songs)}/{num_discovery}] {artist} - {song} ({prob:.1%})")

    # Step 4: Combine and save
    playlist = recent_songs + discovery_songs
    np.random.shuffle(playlist)
    df_playlist = pd.DataFrame(playlist)
    output_file = BASE_DIR / "weekly_playlist.csv"
    df_playlist.to_csv(output_file, index=False)

    print(f"\n{'='*60}\n  PLAYLIST FINAL ({len(playlist)} piese)\n{'='*60}")
    for idx, row in df_playlist.iterrows():
        print(f"  {idx+1:02d}. [{row['Type']}] {row['Artist Name']} - {row['Song Name']} ({row['Match_Score']})")
    print(f"\n[OK] Salvat in {output_file}")
    return playlist


def prompt_to_tags(prompt):
    """Convert a text prompt to Last.fm tags using Gemini LLM (with dictionary fallback)."""
    if _GEMINI_CLIENT is not None:
        try:
            system_prompt = (
                "You are a music tagging expert. Given a mood/activity/style description, "
                "return ONLY a JSON list of 6-10 Last.fm-compatible music tags. "
                "Tags: lowercase, hyphens for multi-word (e.g. 'post-punk'). "
                "No explanation, no markdown. Example: [\"melancholic\", \"atmospheric\", \"shoegaze\"]"
            )
            response = _GEMINI_CLIENT.models.generate_content(
                model="gemini-flash-latest",
                contents=f"{system_prompt}\n\nDescription: \"{prompt}\""
            )
            raw = response.text.strip().strip("```json").strip("```").strip()
            tags_list = json.loads(raw)
            if isinstance(tags_list, list) and tags_list:
                print(f"  [Gemini] Tag-uri generate: {tags_list}")
                return " ".join(str(t).lower() for t in tags_list)
        except Exception as e:
            print(f"  [WARNING] Gemini a esuat ({e}), folosesc fallback.")

    # Fallback: dictionary mapping
    words = prompt.translate(str.maketrans('', '', string.punctuation)).lower().split()
    return " ".join(PROMPT_TAG_MAP.get(w, w) for w in words)


def generate_prompt_playlist(prompt, num_songs=30):
    """Generate a playlist from a text prompt.
    Source A (~40%): local DB scored by TF-IDF cosine similarity.
    Source B (~60%): new tracks from Last.fm, scored by ML model."""

    print(f"\n{'='*60}")
    print(f"  PROMPT PLAYLIST GENERATOR")
    print(f"  Prompt: \"{prompt}\"")
    print(f"{'='*60}\n")

    tags_string = prompt_to_tags(prompt)
    tags_list = tags_string.split()
    print(f"  Tag-uri extrase: {tags_list}\n")

    if not FILE_VECTORIZER.exists() or not FILE_PROCESSED_ALL.exists():
        print("[!] Lipseste vectorizatorul sau baza de date. Ruleaza 'train' inainte.")
        return []

    vectorizer = joblib.load(FILE_VECTORIZER)
    model = joblib.load(FILE_MODEL)
    prompt_vector = vectorizer.transform([tags_string])

    # Source A: Local DB
    print(f"  [A] Cautare in baza de date locala...")
    df = pd.read_csv(FILE_PROCESSED_ALL, low_memory=False, encoding='utf-8')
    vocab_cols = vectorizer.get_feature_names_out()

    missing = [c for c in vocab_cols if c not in df.columns]
    if missing:
        df = pd.concat([df, pd.DataFrame(0, index=df.index, columns=missing)], axis=1)

    similarities = cosine_similarity(prompt_vector, df[list(vocab_cols)].fillna(0).values)
    df = df.copy()
    df['prompt_similarity'] = similarities[0]
    df_sorted = df[df['prompt_similarity'] > 0].sort_values('prompt_similarity', ascending=False)

    local_quota = max(4, int(num_songs * 0.4))
    local_results = df_sorted.head(local_quota)
    local_set = set(
        (str(r.get('Artist Name', '')).lower(), str(r.get('Song Name', '')).lower())
        for _, r in local_results.iterrows()
    )
    print(f"  [A] {len(local_results)} piese din baza locala.\n")

    # Source B: Last.fm tag discovery
    discovery_quota = num_songs - len(local_results)
    print(f"  [B] Cautare pe Last.fm pentru {discovery_quota} piese noi...")

    discovery_candidates = []
    seen = set()
    for tag in tags_list[:6]:
        data = lastfm_request('tag.getTopTracks', tag=tag, limit=100)
        if not data:
            continue
        for t in data.get('tracks', {}).get('track', []):
            artist, name = t.get('artist', {}).get('name', ''), t.get('name', '')
            key = (artist.lower(), name.lower())
            if key not in seen and key not in local_set and artist and name:
                seen.add(key)
                discovery_candidates.append({'Artist Name': artist, 'Song Name': name})

    print(f"  [B] {len(discovery_candidates)} candidati bruti. Evaluez cu ML...")

    # Fetch tags in parallel and score with ML
    validated = []
    if discovery_candidates:
        tag_strings = []
        valid_cands = []
        total = len(discovery_candidates)

        def fetch_tags(cand):
            a, t = cand['Artist Name'], cand['Song Name']
            return cand, (' '.join(get_track_tags(a, t)) + ' ' + ' '.join(get_artist_tags(a))).strip()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_tags, c): c for c in discovery_candidates}
            done = 0
            for future in concurrent.futures.as_completed(futures):
                done += 1
                if done % 25 == 0 or done == total:
                    print(f"      ...tag-uri Last.fm ({done}/{total})")
                try:
                    cand, combined = future.result()
                    if combined:
                        tag_strings.append(combined)
                        valid_cands.append(cand)
                except Exception:
                    pass

        if tag_strings:
            feature_cols = json.load(open(FILE_FEATURE_COLS))
            cand_tfidf = vectorizer.transform(tag_strings)
            cand_df = pd.DataFrame(cand_tfidf.toarray(), columns=vectorizer.get_feature_names_out())
            for col in feature_cols:
                if col not in cand_df.columns:
                    cand_df[col] = 0

            proba = model.predict_proba(cand_df[feature_cols].values)[:, 1]
            for cand, score in zip(valid_cands, proba):
                cand['ml_score'] = score
                validated.append(cand)

        validated.sort(key=lambda x: x.get('ml_score', 0), reverse=True)
        validated = validated[:discovery_quota]

    print(f"  [B] {len(validated)} piese noi validate.\n")

    # Combine and display
    print(f"{'='*60}")
    print(f"  PLAYLIST FINAL ({len(local_results) + len(validated)} piese)")
    print(f"{'='*60}\n")

    entries = []
    for _, row in local_results.iterrows():
        entries.append({
            'Artist': str(row.get('Artist Name', '?')),
            'Track': str(row.get('Song Name', '?')),
            'Score': row['prompt_similarity'] * 100,
            'Source': 'Local DB'
        })

    for cand in validated:
        entries.append({
            'Artist': cand['Artist Name'], 'Track': cand['Song Name'],
            'Score': cand.get('ml_score', 0) * 100, 'Source': 'Last.fm Discovery'
        })

    random.shuffle(entries)

    for i, e in enumerate(entries, 1):
        label = "[Din biblioteca ta]" if e['Source'] == 'Local DB' else "[Descoperire noua]  "
        line = f"  {i:02d}. {label} {e['Artist']} - {e['Track']} (Match: {e['Score']:.1f}%)"
        print(line.encode('cp1252', errors='replace').decode('cp1252'))

    out_file = BASE_DIR / "prompt_playlist.csv"
    pd.DataFrame(entries).to_csv(out_file, index=False, encoding='utf-8')
    print(f"\n[OK] Playlist salvat in {out_file}")
    return entries


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="Music Preference Prediction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemple:
  python pipeline.py fetch-liked --pages 72
  python pipeline.py fetch-disliked --genres "pop,kpop,trap"
  python pipeline.py combine
  python pipeline.py process-all
  python pipeline.py train
  python pipeline.py predict "Radiohead" "Creep"
  python pipeline.py predict-batch songs.txt
  python pipeline.py generate-prompt "muzica trista atmosferica"
  python pipeline.py generate-weekly
        """
    )

    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('fetch-liked')
    p.add_argument('--pages', type=int, default=72)
    p.add_argument('--user', type=str, default=LASTFM_USERNAME)

    p = sub.add_parser('fetch-disliked')
    p.add_argument('--genres', type=str, default=None)
    p.add_argument('--pages', type=int, default=2)

    sub.add_parser('combine')
    sub.add_parser('process-all')
    sub.add_parser('train')

    p = sub.add_parser('predict')
    p.add_argument('artist', type=str)
    p.add_argument('song', type=str)

    p = sub.add_parser('predict-batch')
    p.add_argument('file', type=str)

    p = sub.add_parser('add-negatives')
    p.add_argument('--genres', type=str, default=None)
    p.add_argument('--pages', type=int, default=2)

    p = sub.add_parser('smart-negatives')
    p.add_argument('--genres', type=str, default=None)
    p.add_argument('--pages', type=int, default=2)

    p = sub.add_parser('reclassify')
    p.add_argument('--max-playcount', type=int, default=1)

    p = sub.add_parser('recommend')
    p.add_argument('--limit', type=int, default=5)

    p = sub.add_parser('sync-recent')
    p.add_argument('--days', type=int, default=7)

    p = sub.add_parser('generate-weekly')
    p.add_argument('--days', type=int, default=7)

    p = sub.add_parser('generate-prompt')
    p.add_argument('prompt', type=str)
    p.add_argument('--limit', type=int, default=30)

    sub.add_parser('analyze-tags')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cmd = args.command
    if cmd == 'fetch-liked':
        fetch_liked_songs(username=args.user, max_pages=args.pages)
    elif cmd == 'fetch-disliked':
        genres = args.genres.split(',') if args.genres else None
        fetch_disliked_songs(genres=genres, max_pages=args.pages)
    elif cmd == 'combine':
        combine_datasets()
    elif cmd == 'process-all':
        process_all_songs()
    elif cmd == 'train':
        train_models()
    elif cmd == 'predict':
        predict_song(args.artist, args.song)
    elif cmd == 'predict-batch':
        predict_batch(args.file)
    elif cmd == 'add-negatives':
        genres = args.genres.split(',') if args.genres else None
        add_negatives(genres=genres, max_pages=args.pages)
    elif cmd == 'smart-negatives':
        genres = args.genres.split(',') if args.genres else None
        smart_negatives(genres=genres, max_pages=args.pages)
    elif cmd == 'reclassify':
        reclassify_by_playcount(max_playcount=args.max_playcount)
    elif cmd == 'recommend':
        run_recommendations(limit_display=args.limit)
    elif cmd == 'sync-recent':
        sync_recent_tracks(days=args.days)
    elif cmd == 'generate-weekly':
        generate_weekly_playlist(days=args.days)
    elif cmd == 'generate-prompt':
        generate_prompt_playlist(args.prompt, num_songs=args.limit)
    elif cmd == 'analyze-tags':
        analyze_tags()


if __name__ == '__main__':
    main()
