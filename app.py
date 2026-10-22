"""
Flask Backend API Server
Expune functiile din pipeline.py ca endpoint-uri REST JSON
+ Spotify OAuth pentru Web Playback SDK (redare piese intregi).

Rulare: python app.py
Server: http://localhost:5000
"""

import os
from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
import pandas as pd
from collections import Counter
import requests as http_requests   # redenumit ca sa nu se confunde cu flask.request
import base64
import urllib.parse
import time

import pipeline

app = Flask(__name__)

# "secret_key" e necesar pentru session (cookie-uri criptate).
# Flask Session stocheaza date intre cereri (ex: token-ul Spotify).
# Practic, browserul primeste un cookie criptat care contine token-ul.
app.secret_key = 'smart-music-ai-secret-key-2024'

# CORS permite React-ului (pe port 5173) sa comunice cu Flask (pe port 5000)
CORS(app, supports_credentials=True)


# ═══════════════════════════════════════════════════════════════════
# SPOTIFY OAUTH CONFIG
#
# OAuth = protocol de autorizare. Flow-ul:
#   1. User apasa "Login with Spotify"
#   2. Flask il redirecteaza la Spotify ("vrei sa dai acces?")
#   3. Spotify redirecteaza inapoi la /callback cu un COD
#   4. Flask schimba codul pe un ACCESS TOKEN (cheia de acces)
#   5. Access token-ul permite Web Playback SDK sa redea muzica
#
# Scopes = permisiunile pe care le cerem:
#   - streaming: dreptul de a reda muzica
#   - user-read-email: Spotify cere asta obligatoriu pt SDK
#   - user-modify-playback-state: dreptul de a da play/pause/next
#   - user-read-playback-state: dreptul de a vedea ce canta acum
# ═══════════════════════════════════════════════════════════════════

from dotenv import load_dotenv
load_dotenv()

SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', '')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', '')
SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:5555/callback'
SPOTIFY_SCOPES = 'streaming user-read-email user-read-private user-modify-playback-state user-read-playback-state user-library-read user-library-modify playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private'

# Stocam token-urile intr-un fisier JSON ca sa NU se piarda cand opresti serverul.
# Dupa primul login, nu mai trebuie sa te loghezi niciodata (refresh token-ul e permanent).
import json as json_lib
from pathlib import Path as PathLib

SPOTIFY_TOKENS_FILE = PathLib(__file__).parent / 'spotify_tokens.json'

def load_spotify_tokens():
    """Incarca token-urile salvate din fisier (daca exista)."""
    if SPOTIFY_TOKENS_FILE.exists():
        try:
            with open(SPOTIFY_TOKENS_FILE, 'r') as f:
                return json_lib.load(f)
        except:
            pass
    return {'access_token': None, 'refresh_token': None, 'expires_at': 0}

def save_spotify_tokens():
    """Salveaza token-urile in fisier pentru persistenta."""
    with open(SPOTIFY_TOKENS_FILE, 'w') as f:
        json_lib.dump(spotify_tokens, f)

spotify_tokens = load_spotify_tokens()


@app.route('/login')
def spotify_login():
    """
    Pasul 1: Redirecteaza user-ul la pagina de login Spotify.
    
    Construim un URL lung care contine:
    - client_id: cine suntem noi (aplicatia noastra)
    - response_type: 'code' = vrem un cod de autorizare
    - redirect_uri: unde sa ne trimita inapoi Spotify
    - scope: ce permisiuni cerem
    """
    params = urllib.parse.urlencode({
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'scope': SPOTIFY_SCOPES,
        'show_dialog': 'true',  # Forteaza afisarea ecranului de permisiuni
    })
    # redirect() = trimite browser-ul la alta adresa
    return redirect(f'https://accounts.spotify.com/authorize?{params}')


@app.route('/logout')
def spotify_logout():
    """Sterge token-urile si forteaza re-login cu permisiuni noi."""
    spotify_tokens['access_token'] = None
    spotify_tokens['refresh_token'] = None
    spotify_tokens['expires_at'] = 0
    if SPOTIFY_TOKENS_FILE.exists():
        SPOTIFY_TOKENS_FILE.unlink()
    return redirect('/login')


@app.route('/callback')
def spotify_callback():
    """
    Pasul 2: Spotify trimite user-ul inapoi aici cu un COD in URL.
    
    Ex: http://localhost:5000/callback?code=AQBx7s...
    
    Noi luam acel cod si il schimbam pe un ACCESS TOKEN
    prin un POST request catre Spotify.
    
    Token Exchange:
      COD (de unica folosinta) → ACCESS TOKEN (valabil 1 ora) + REFRESH TOKEN (permanent)
    """
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return redirect(f'http://localhost:5173?spotify_error={error}')

    # Construim Authorization header (Base64 encoded client_id:client_secret)
    # Spotify cere asta ca sa verifice ca suntem noi, nu altcineva
    auth_string = f'{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}'
    auth_base64 = base64.b64encode(auth_string.encode()).decode()

    # Facem POST request catre Spotify pentru a schimba codul pe token
    response = http_requests.post(
        'https://accounts.spotify.com/api/token',
        headers={
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': SPOTIFY_REDIRECT_URI,
        }
    )

    if response.status_code != 200:
        return redirect('http://localhost:5173?spotify_error=token_exchange_failed')

    token_data = response.json()

    # Salvam token-urile si scope-urile
    spotify_tokens['access_token'] = token_data['access_token']
    spotify_tokens['refresh_token'] = token_data.get('refresh_token')
    spotify_tokens['scope'] = token_data.get('scope', '')
    spotify_tokens['expires_at'] = time.time() + token_data.get('expires_in', 3600)
    save_spotify_tokens()  # Persistam in fisier

    print(f"\n[SPOTIFY LOGIN] Succes! Scopes acordate: {token_data.get('scope')}\n")

    # Redirectam inapoi la frontend
    return redirect('http://localhost:5173?spotify=connected')


def refresh_spotify_token():
    """
    Token-ul expira dupa 1 ora. Aceasta functie il reinnoieste automat
    folosind refresh_token-ul (care nu expira niciodata).
    """
    if not spotify_tokens['refresh_token']:
        return False

    auth_string = f'{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}'
    auth_base64 = base64.b64encode(auth_string.encode()).decode()

    response = http_requests.post(
        'https://accounts.spotify.com/api/token',
        headers={
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data={
            'grant_type': 'refresh_token',
            'refresh_token': spotify_tokens['refresh_token'],
        }
    )

    if response.status_code == 200:
        data = response.json()
        spotify_tokens['access_token'] = data['access_token']
        spotify_tokens['expires_at'] = time.time() + data.get('expires_in', 3600)
        save_spotify_tokens()  # Persistam in fisier
        return True
    return False


def get_valid_token():
    """Returneaza un access_token valid. Il reinnoieste automat daca a expirat."""
    if not SPOTIFY_TOKENS_FILE.exists():
        spotify_tokens['access_token'] = None
        spotify_tokens['refresh_token'] = None
        spotify_tokens['expires_at'] = 0
        return None

    if spotify_tokens['access_token'] and time.time() < spotify_tokens['expires_at'] - 60:
        return spotify_tokens['access_token']
    if refresh_spotify_token():
        return spotify_tokens['access_token']
    return None


@app.route('/api/spotify-token', methods=['GET'])
def api_spotify_token():
    """
    Frontend-ul apeleaza asta ca sa obtina token-ul pentru Web Playback SDK.
    Returneaza token-ul + statusul (connected/disconnected).
    """
    token = get_valid_token()
    if token:
        return jsonify({
            'access_token': token,
            'connected': True
        })
    return jsonify({
        'access_token': None,
        'connected': False
    })


@app.route('/api/me', methods=['GET'])
def api_me():
    token = get_valid_token()
    if not token:
        return jsonify({'error': 'No token'}), 401
    
    response = http_requests.get(
        'https://api.spotify.com/v1/me',
        headers={'Authorization': f'Bearer {token}'}
    )
    return jsonify(response.json())

# Caching pentru imaginile Spotify
SPOTIFY_CACHE_FILE = PathLib(__file__).parent / 'spotify_image_cache.json'

def load_image_cache():
    if SPOTIFY_CACHE_FILE.exists():
        try:
            with open(SPOTIFY_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json_lib.load(f)
        except:
            pass
    return {'tracks': {}, 'artists': {}}

def save_image_cache(cache_data):
    with open(SPOTIFY_CACHE_FILE, 'w', encoding='utf-8') as f:
        json_lib.dump(cache_data, f)

image_cache = load_image_cache()

@app.route('/api/spotify-search', methods=['GET'])
def api_spotify_search():
    """
    Cauta o piesa pe Spotify. Foloseste parametrii `artist` si `track` pentru acuratete maxima,
    sau parametrul `q` pentru backwards compatibility.
    """
    q = request.args.get('q', '').strip()
    artist = request.args.get('artist', '').strip()
    track_name = request.args.get('track', '').strip()

    if not q and not (artist and track_name):
        return jsonify({'error': 'Parametri lipsa'}), 400

    # Construim query-ul precis si cheia de cache
    if artist and track_name:
        query = f'track:{track_name} artist:{artist}'
        cache_key = f"{artist} - {track_name}".lower()
    else:
        query = q
        cache_key = q.lower()

    # Verificam cache-ul
    if cache_key in image_cache['tracks']:
        cached = image_cache['tracks'][cache_key]
        if 'error' in cached:
            return jsonify(cached), 404
        return jsonify(cached)

    token = get_valid_token()
    if not token:
        return jsonify({'error': 'Nu esti conectat la Spotify'}), 401

    response = http_requests.get(
        'https://api.spotify.com/v1/search',
        headers={'Authorization': f'Bearer {token}'},
        params={'q': query, 'type': 'track', 'limit': 1}
    )

    if response.status_code != 200:
        return jsonify({'error': 'Cautarea Spotify a esuat'}), 500

    data = response.json()
    tracks = data.get('tracks', {}).get('items', [])

    if not tracks:
        return jsonify({'error': 'Piesa nu a fost gasita pe Spotify'}), 404

    track = tracks[0]
    result = {
        'uri': track['uri'],
        'name': track['name'],
        'artist': ', '.join(a['name'] for a in track['artists']),
        'album': track['album']['name'],
        'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None,
        'duration_ms': track['duration_ms'],
        'external_url': track['external_urls'].get('spotify', ''),
    }
    
    # Salvam in cache
    image_cache['tracks'][cache_key] = result
    save_image_cache(image_cache)
    
    return jsonify(result)


@app.route('/api/spotify-artist-search', methods=['GET'])
def api_spotify_artist_search():
    """
    Cauta un artist pe Spotify si returneaza poza de profil.
    """
    artist_name = request.args.get('artist', '').strip()
    q = request.args.get('q', '').strip()
    
    name = artist_name or q
    if not name:
        return jsonify({'error': 'Parametru artist lipsa'}), 400

    query = f'artist:{name}' if artist_name else q
    cache_key = name.lower()

    if cache_key in image_cache['artists']:
        cached = image_cache['artists'][cache_key]
        if 'error' in cached:
            return jsonify(cached), 404
        return jsonify(cached)

    token = get_valid_token()
    if not token:
        return jsonify({'error': 'Nu esti conectat la Spotify'}), 401

    response = http_requests.get(
        'https://api.spotify.com/v1/search',
        headers={'Authorization': f'Bearer {token}'},
        params={'q': query, 'type': 'artist', 'limit': 1}
    )

    if response.status_code != 200:
        return jsonify({'error': 'Cautarea Spotify a esuat'}), 500

    data = response.json()
    artists = data.get('artists', {}).get('items', [])

    if not artists:
        return jsonify({'error': 'Artistul nu a fost gasit pe Spotify'}), 404

    artist = artists[0]
    result = {
        'name': artist['name'],
        'image': artist['images'][0]['url'] if artist.get('images') else None
    }
    
    image_cache['artists'][cache_key] = result
    save_image_cache(image_cache)
    
    return jsonify(result)


@app.route('/api/random-recent', methods=['GET'])
def api_random_recent():
    """
    Returneaza o piesa random din baza de date de piese liked,
    cu sansa de a alege si din ascultarile recente Last.fm.
    """
    import random
    try:
        all_tracks = []
        
        # Sursa 1: Piese liked din baza de date (sursa principala)
        if pipeline.FILE_MASTER.exists():
            df = pd.read_csv(pipeline.FILE_MASTER)
            liked = df[df['Target'] == 1]
            if not liked.empty:
                for _, row in liked.iterrows():
                    all_tracks.append({
                        'artist': str(row['Artist Name']),
                        'song': str(row['Song Name'])
                    })
        
        # Sursa 2: Top piese recente Last.fm (overall, nu doar 7 zile)
        data = pipeline.lastfm_request('user.getTopTracks', user=pipeline.LASTFM_USERNAME, period='overall', limit=50)
        if data and 'toptracks' in data and 'track' in data['toptracks']:
            tracks = data['toptracks']['track']
            if isinstance(tracks, dict):
                tracks = [tracks]
            for track in tracks:
                all_tracks.append({
                    'artist': track['artist']['name'],
                    'song': track['name']
                })
        
        if all_tracks:
            # Eliminam duplicate
            seen = set()
            unique = []
            for t in all_tracks:
                key = (t['artist'].lower(), t['song'].lower())
                if key not in seen:
                    seen.add(key)
                    unique.append(t)
            
            return jsonify(random.choice(unique))
                
        return jsonify({'error': 'Nicio piesa gasita'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════
# ENDPOINT-URILE EXISTENTE (Pipeline ML)
# ═══════════════════════════════════════════════════════════════════

@app.route('/api/generate-prompt', methods=['POST'])
def api_generate_prompt():
    """Primeste un prompt text, il trimite la Gemini + ML, returneaza playlist-ul."""
    data = request.get_json() or {}
    prompt = data.get('prompt', '').strip()
    limit = int(data.get('limit', 30))

    if not prompt:
        return jsonify({'error': 'Prompt-ul nu poate fi gol!'}), 400

    try:
        tags_string = pipeline.prompt_to_tags(prompt)
        tags_list = tags_string.split()
        tracks = pipeline.generate_prompt_playlist(prompt, num_songs=limit)

        return jsonify({
            'prompt': prompt,
            'tags': tags_list,
            'tracks': [
                {
                    'artist': t.get('Artist'),
                    'song': t.get('Track'),
                    'score': t.get('Score', 0) / 100, # Frontend asteapta 0-1, pipeline da 0-100
                    'source': 'local' if t.get('Source') == 'Local DB' else 'discovery'
                } for t in tracks
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict', methods=['POST'])
def api_predict():
    """Primeste artist + song, returneaza predictia ML (liked/disliked + probabilitate)."""
    data = request.get_json() or {}
    artist = data.get('artist', '').strip()
    song = data.get('song', '').strip()

    if not artist or not song:
        return jsonify({'error': 'Artistul si piesa sunt obligatorii!'}), 400

    try:
        result = pipeline.predict_song(artist, song)
        if result is None:
            return jsonify({'error': f'Piesa "{artist} - {song}" nu a fost gasita pe Last.fm.'}), 404
            
        return jsonify({
            'prediction': 'liked' if result['liked'] else 'disliked',
            'probability': result['prob_liked'],
            'tags': result['tags'].split(', ') if isinstance(result['tags'], str) else result['tags']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-weekly', methods=['POST'])
def api_generate_weekly():
    """Genereaza playlist-ul saptamanal (sync + ancore + descoperiri ML)."""
    data = request.get_json() or {}
    days = int(data.get('days', 7))

    try:
        tracks = pipeline.generate_weekly_playlist(days=days)
        formatted_tracks = []
        for t in tracks:
            # Match_Score format: "85.2%" or "100% (Listen History)"
            score_str = str(t.get('Match_Score', '0'))
            score = 0
            if '%' in score_str:
                score = float(score_str.split('%')[0]) / 100
                
            formatted_tracks.append({
                'artist': t.get('Artist Name'),
                'song': t.get('Song Name'),
                'score': score,
                'source': 'anchor' if t.get('Type') == 'Recent Favourite' else 'discovery'
            })
            
        return jsonify({'tracks': formatted_tracks})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    """
    Genereaza 5 recomandari personalizate de piese folosind motorul ML.
    
    Flow:
    1. Cauta piese candidate din Last.fm (deep cuts, artisti similari, piese similare)
    2. Extrage tag-uri pt fiecare candidat
    3. Scoreaza fiecare candidat cu modelul Random Forest antrenat
    4. Returneaza top 5 piese sortate dupa probabilitatea de liked
    """
    try:
        if not pipeline.FILE_MODEL.exists() or not pipeline.FILE_VECTORIZER.exists():
            return jsonify({'error': 'Modelul ML nu este antrenat! Ruleaza "python pipeline.py train" mai intai.'}), 400

        model = pipeline.joblib.load(pipeline.FILE_MODEL)
        vectorizer = pipeline.joblib.load(pipeline.FILE_VECTORIZER)
        with open(pipeline.FILE_FEATURE_COLS, 'r') as f:
            feature_cols = pipeline.json.load(f)

        # Pasul 1: Genereaza candidati
        candidates = pipeline.get_recommendation_candidates(num_candidates=15)
        if not candidates:
            return jsonify({'error': 'Nu am gasit piese candidate. Verifica conexiunea Last.fm.'}), 404

        # Pasul 2: Scoreaza cu ML
        scored = []
        for c in candidates[:20]:
            artist, song = c['Artist Name'], c['Song Name']
            t_tags = pipeline.get_track_tags(artist, song)
            time.sleep(pipeline.LASTFM_DELAY)
            a_tags = pipeline.get_artist_tags(artist)
            time.sleep(pipeline.LASTFM_DELAY)

            cleaned = pipeline.clean_tag_text(", ".join(a_tags + t_tags))
            if not cleaned.strip():
                continue

            tfidf = vectorizer.transform([cleaned])
            tfidf_df = pd.DataFrame(tfidf.toarray(), columns=vectorizer.get_feature_names_out())

            fv = pd.DataFrame(0, index=[0], columns=feature_cols)
            for col in tfidf_df.columns:
                if col in fv.columns:
                    fv[col] = tfidf_df[col].values

            prob = model.predict_proba(fv)[0][1]
            scored.append({
                'artist': artist,
                'song': song,
                'prob_liked': round(float(prob), 4),
                'track_tags': t_tags[:5],
                'artist_tags': a_tags[:5],
            })

        scored.sort(key=lambda x: x['prob_liked'], reverse=True)

        # Pasul 3: Returneaza top 5
        return jsonify({
            'recommendations': scored[:5],
            'total_candidates': len(candidates),
            'total_scored': len(scored),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recommend-feedback', methods=['POST'])
def api_recommend_feedback():
    """
    Salveaza feedback-ul utilizatorului (like/dislike) pentru o piesa recomandata.
    Acest feedback este adaugat in master_dataset pentru reantrenarea modelului.
    """
    data = request.get_json() or {}
    artist = data.get('artist', '').strip()
    song = data.get('song', '').strip()
    feedback = data.get('feedback')  # 1 = liked, 0 = disliked

    if not artist or not song or feedback not in [0, 1]:
        return jsonify({'error': 'Date invalide'}), 400

    try:
        if pipeline.FILE_MASTER.exists():
            df = pd.read_csv(pipeline.FILE_MASTER)
        else:
            df = pd.DataFrame(columns=['Artist Name', 'Song Name', 'Plays', 'Rank', 'Track Tags', 'Artist Tags', 'Target'])

        new_row = pd.DataFrame([{
            'Artist Name': artist,
            'Song Name': song,
            'Plays': 0,
            'Rank': 0,
            'Track Tags': '',
            'Artist Tags': '',
            'Target': int(feedback)
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        df = df.drop_duplicates(subset=['Artist Name', 'Song Name'], keep='last')
        df.to_csv(pipeline.FILE_MASTER, index=False)

        return jsonify({'status': 'ok', 'message': f'Feedback salvat: {artist} - {song} = {"liked" if feedback == 1 else "disliked"}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/lastfm-stats', methods=['GET'])
def api_lastfm_stats():
    """Returneaza statistici Last.fm (profil, top tracks, artists, albums)."""
    period = request.args.get('period', '7day')
    if period not in ['7day', '1month', '3month', '6month', '12month', 'overall']:
        period = '7day'
        
    try:
        # Get User Info
        user_info_resp = pipeline.lastfm_request('user.getInfo', user=pipeline.LASTFM_USERNAME)
        user_info = {}
        if user_info_resp and 'user' in user_info_resp:
            user = user_info_resp['user']
            user_info = {
                'playcount': user.get('playcount', '0'),
                'name': user.get('name', ''),
                'registered': user.get('registered', {}).get('unixtime', '')
            }
            
        # Get Top Tracks
        tracks_resp = pipeline.lastfm_request('user.getTopTracks', user=pipeline.LASTFM_USERNAME, period=period, limit=10)
        top_tracks = []
        if tracks_resp and 'toptracks' in tracks_resp and 'track' in tracks_resp['toptracks']:
            tracks = tracks_resp['toptracks']['track']
            if isinstance(tracks, dict): tracks = [tracks]
            for t in tracks:
                img_url = ''
                if 'image' in t:
                    images = t['image']
                    if isinstance(images, list):
                        for img in images:
                            if img.get('size') == 'large' and img.get('#text'):
                                img_url = img.get('#text')
                                break
                            elif img.get('size') == 'medium' and not img_url and img.get('#text'):
                                img_url = img.get('#text')
                top_tracks.append({
                    'name': t.get('name', ''),
                    'artist': t.get('artist', {}).get('name', ''),
                    'playcount': t.get('playcount', '0'),
                    'image': img_url
                })
                
        # Get Top Artists
        artists_resp = pipeline.lastfm_request('user.getTopArtists', user=pipeline.LASTFM_USERNAME, period=period, limit=10)
        top_artists = []
        if artists_resp and 'topartists' in artists_resp and 'artist' in artists_resp['topartists']:
            artists = artists_resp['topartists']['artist']
            if isinstance(artists, dict): artists = [artists]
            for a in artists:
                img_url = ''
                if 'image' in a:
                    images = a['image']
                    if isinstance(images, list):
                        for img in images:
                            if img.get('size') == 'large' and img.get('#text'):
                                img_url = img.get('#text')
                                break
                            elif img.get('size') == 'medium' and not img_url and img.get('#text'):
                                img_url = img.get('#text')
                top_artists.append({
                    'name': a.get('name', ''),
                    'playcount': a.get('playcount', '0'),
                    'image': img_url
                })
                
        # Get Top Albums
        albums_resp = pipeline.lastfm_request('user.getTopAlbums', user=pipeline.LASTFM_USERNAME, period=period, limit=10)
        top_albums = []
        if albums_resp and 'topalbums' in albums_resp and 'album' in albums_resp['topalbums']:
            albums = albums_resp['topalbums']['album']
            if isinstance(albums, dict): albums = [albums]
            for al in albums:
                img_url = ''
                if 'image' in al:
                    images = al['image']
                    if isinstance(images, list):
                        for img in images:
                            if img.get('size') == 'large' and img.get('#text'):
                                img_url = img.get('#text')
                                break
                            elif img.get('size') == 'medium' and not img_url and img.get('#text'):
                                img_url = img.get('#text')
                top_albums.append({
                    'name': al.get('name', ''),
                    'artist': al.get('artist', {}).get('name', ''),
                    'playcount': al.get('playcount', '0'),
                    'image': img_url
                })
                
        return jsonify({
            'user_info': user_info,
            'top_tracks': top_tracks,
            'top_artists': top_artists,
            'top_albums': top_albums,
            'period': period
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/spotify-like', methods=['POST'])
def api_spotify_like():
    """
    Salveaza o piesa in Liked Songs pe Spotify folosind noul endpoint unificat /v1/me/library.
    """
    data = request.get_json() or {}
    uri = data.get('uri', '').strip()
    
    if not uri:
        return jsonify({'error': 'URI invalid'}), 400
        
    token = get_valid_token()
    if not token:
        return jsonify({'error': 'Nu esti conectat la Spotify'}), 401
    
    # Asiguram formatul URI complet
    if not uri.startswith('spotify:track:'):
        uri = f'spotify:track:{uri}'
        
    track_id = uri.split(':')[-1]
    
    # 1. Noul endpoint Spotify (2025/2026): PUT /v1/me/library?uris=spotify:track:xxx
    response = http_requests.put(
        f'https://api.spotify.com/v1/me/library?uris={uri}',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    # 2. Fallback: PUT /v1/me/tracks?ids=xxx
    if response.status_code not in [200, 201, 204]:
        response = http_requests.put(
            f'https://api.spotify.com/v1/me/tracks?ids={track_id}',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'ids': [track_id]}
        )
        
    # 3. Fallback: PUT /v1/me/tracks cu header simplu
    if response.status_code not in [200, 201, 204]:
        response = http_requests.put(
            f'https://api.spotify.com/v1/me/tracks?ids={track_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
    
    if response.status_code in [200, 201, 204]:
        return jsonify({'status': 'ok'})
    print(f'[SPOTIFY-LIKE ERROR] Status: {response.status_code}, Body: {response.text}')
    return jsonify({'error': f'Spotify API a returnat {response.status_code}: {response.text}'}), response.status_code


@app.route('/api/spotify-unlike', methods=['POST'])
def api_spotify_unlike():
    """
    Sterge o piesa din Liked Songs pe Spotify folosind DELETE /v1/me/library.
    """
    data = request.get_json() or {}
    uri = data.get('uri', '').strip()
    
    if not uri:
        return jsonify({'error': 'URI invalid'}), 400
        
    token = get_valid_token()
    if not token:
        return jsonify({'error': 'Nu esti conectat la Spotify'}), 401
    
    if not uri.startswith('spotify:track:'):
        uri = f'spotify:track:{uri}'
        
    track_id = uri.split(':')[-1]
    
    # 1. Noul endpoint Spotify: DELETE /v1/me/library?uris=spotify:track:xxx
    response = http_requests.delete(
        f'https://api.spotify.com/v1/me/library?uris={uri}',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    # 2. Fallback: DELETE /v1/me/tracks?ids=xxx
    if response.status_code not in [200, 201, 204]:
        response = http_requests.delete(
            f'https://api.spotify.com/v1/me/tracks?ids={track_id}',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'ids': [track_id]}
        )
        
    if response.status_code in [200, 201, 204]:
        return jsonify({'status': 'ok'})
    print(f'[SPOTIFY-UNLIKE ERROR] Status: {response.status_code}, Body: {response.text}')
    return jsonify({'error': f'Spotify API a returnat {response.status_code}: {response.text}'}), response.status_code


@app.route('/api/spotify-create-playlist', methods=['POST'])
def api_spotify_create_playlist():
    """
    Creeaza un playlist si adauga piesele date in el folosind noile endpoint-uri Spotify.
    """
    data = request.get_json() or {}
    name = data.get('name', 'Smart Music Playlist')
    uris = data.get('uris', [])
    
    if not uris:
        return jsonify({'error': 'Nu exista piese pentru playlist'}), 400
        
    token = get_valid_token()
    if not token:
        return jsonify({'error': 'Nu esti conectat la Spotify'}), 401
        
    # 1. Cream playlist-ul folosind POST /v1/me/playlists
    pl_resp = http_requests.post(
        'https://api.spotify.com/v1/me/playlists',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        json={'name': name, 'description': 'Generat de Smart Music AI', 'public': False}
    )
    
    # Fallback daca /me/playlists returneaza eroare
    if pl_resp.status_code not in [200, 201]:
        me_resp = http_requests.get('https://api.spotify.com/v1/me', headers={'Authorization': f'Bearer {token}'})
        if me_resp.status_code == 200:
            user_id = me_resp.json().get('id')
            pl_resp = http_requests.post(
                f'https://api.spotify.com/v1/users/{user_id}/playlists',
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                json={'name': name, 'description': 'Generat de Smart Music AI', 'public': False}
            )
    
    if pl_resp.status_code not in [200, 201]:
        print(f'[SPOTIFY-PLAYLIST ERROR] Status: {pl_resp.status_code}, Body: {pl_resp.text}')
        return jsonify({'error': f'Eroare la crearea playlist-ului: {pl_resp.text}'}), pl_resp.status_code
        
    playlist_id = pl_resp.json().get('id')
    playlist_url = pl_resp.json().get('external_urls', {}).get('spotify')
    
    # 2. Adaugam piesele in grupuri de cate 50 (noul endpoint /v1/playlists/{id}/items)
    for i in range(0, len(uris), 50):
        batch = uris[i:i+50]
        add_resp = http_requests.post(
            f'https://api.spotify.com/v1/playlists/{playlist_id}/items',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'uris': batch}
        )
        # Fallback pe /tracks daca noul endpoint returneaza eroare
        if add_resp.status_code not in [200, 201]:
            http_requests.post(
                f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                json={'uris': batch}
            )
        
    return jsonify({'status': 'ok', 'playlist_url': playlist_url})


@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Returneaza statistici despre baza de date: total piese, liked/disliked, top tag-uri."""
    try:
        target_file = pipeline.FILE_PROCESSED_ALL if pipeline.FILE_PROCESSED_ALL.exists() else pipeline.FILE_MASTER
        if not target_file.exists():
            return jsonify({
                'total_songs': 0, 'liked_count': 0,
                'disliked_count': 0, 'top_tags': []
            })

        df = pd.read_csv(target_file, low_memory=False)
        total = len(df)
        liked = int((df['Target'] == 1).sum()) if 'Target' in df.columns else 0
        disliked = int((df['Target'] == 0).sum()) if 'Target' in df.columns else 0

        # Top 15 tag-uri din baza de date
        top_tags = []
        if 'Tags' in df.columns:
            all_tags = []
            for tags_str in df['Tags'].dropna():
                all_tags.extend(str(tags_str).split())
            counter = Counter(all_tags)
            top_tags = [
                {'tag': t, 'count': c, 'percentage': round(c / total * 100, 1)}
                for t, c in counter.most_common(15)
            ]

        return jsonify({
            'total_songs': total,
            'liked_count': liked,
            'disliked_count': disliked,
            'top_tags': top_tags,
            'has_model': pipeline.FILE_MODEL.exists()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("  Flask API Server — http://localhost:5555")
    print("  Spotify Login  — http://localhost:5555/login")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5555, debug=True)
