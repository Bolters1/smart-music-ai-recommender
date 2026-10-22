# Smart Music AI

A music recommendation system that learns your taste from Last.fm listening history and predicts whether you'll like a song before you even hear it. It combines a trained ML model, natural language playlist generation (via Gemini), and Spotify playback — all wrapped in a retro-themed React frontend.

## What it does

The core idea: take ~14,000 songs I've actually listened to (pulled from Last.fm scrobbles), combine them with ~8,000 negative samples from genres I don't listen to, extract genre/subgenre tags, and train a Random Forest classifier on TF-IDF vectors of those tags. The model learns to distinguish between music I'd enjoy and music I wouldn't — not from audio features, but purely from the "tag fingerprint" of each track.

On top of that base, there are several features built around it:

- **Song Prediction** — give it any artist + track, and it tells you the probability you'd like it
- **Prompt Playlists** — describe a mood in plain text (e.g. "rainy day acoustic guitar"), Gemini extracts relevant tags, and the system finds matching songs from both your library and Last.fm discovery
- **Tinder-style Recommendations** — swipe through recommendations pulled from deep cuts of artists you love, similar artists, and similar tracks. Your feedback goes back into the training data
- **Weekly Discover** — auto-generated playlist based on what you listened to this week, mixing familiar anchors (40%) with ML-validated discoveries (60%)
- **Auto Sync** — pulls recent scrobbles and updates the model. Songs played 3+ times get marked as liked, 1-2 plays become soft negatives
- **Listening Stats** — breakdowns of your top genres, artists, and model confidence distributions

## Architecture

```
React Frontend (Vite)  ──>  Flask API  ──>  ML Pipeline (scikit-learn)
       │                        │                    │
  Spotify Web SDK          Spotify OAuth       Last.fm API + Gemini
  (full playback)          (auth flow)         (data + tag extraction)
```

**Backend** (`pipeline.py` + `app.py`):
- `pipeline.py` — the entire ML pipeline: data collection, tag cleaning, TF-IDF vectorization, model training, prediction, recommendation engine, playlist generation. ~1500 lines, runs as CLI or gets called by the Flask API
- `app.py` — Flask server exposing the pipeline as REST endpoints, handles Spotify OAuth for in-browser playback

**Frontend** (`frontend/`):
- React 19 + Vite, retro Y2K-inspired design (think early 2000s fan sites)
- Components for each feature: `PromptGenerator`, `SongPredictor`, `RecommendPage`, `WeeklyDiscover`, `StatsPage`
- Integrated Spotify Web Playback SDK for full song previews

**ML Model**:
- Random Forest classifier on 200 TF-IDF features from Last.fm tags
- Chose RF over LightGBM/XGBoost after ablation tests — boosting kept overfitting on the dominant `rock` tag, while bagging handled the sparse subgenre boundaries better
- Sample weighting: `w = log(plays + 1) + 1`, so heavily-played tracks carry more weight
- Metrics: **87.4% ROC-AUC**, **78.4% accuracy**, **0.73 F1**

## Tech Stack

| Layer | Tech |
|-------|------|
| ML | scikit-learn, pandas, numpy, TF-IDF, Random Forest |
| NLP | Google Gemini (tag extraction from natural language prompts) |
| Backend | Flask, Flask-CORS |
| Frontend | React 19, Vite, Lucide icons |
| Music Data | Last.fm API (scrobbles, tags, similar tracks/artists) |
| Playback | Spotify Web Playback SDK + OAuth |
| Caching | JSON-based persistent tag cache (~22k entries), Spotify image cache |

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- A Last.fm account with API key
- A Spotify Developer app (for playback)
- A Google Gemini API key (for prompt playlists)

### Backend

```bash
# Install Python dependencies
pip install flask flask-cors pandas numpy scikit-learn joblib python-dotenv requests lightgbm google-genai

# Create .env with your API keys
cp .env.example .env
# Edit .env with your Last.fm API key, username, Gemini key, and Spotify credentials

# Run the full pipeline (fetch data, process, train)
python pipeline.py process-all
python pipeline.py train

# Start the Flask server
python app.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` and talks to Flask on `http://localhost:5000`.

### CLI Usage

The pipeline also works standalone without the web UI:

```bash
python pipeline.py sync-recent --days 7     # sync recent scrobbles
python pipeline.py recommend --limit 5       # interactive recommendations
python pipeline.py generate-weekly --days 7  # weekly discovery playlist
python pipeline.py generate-prompt "sad atmospheric music for a rainy day" --limit 30
python pipeline.py predict "Radiohead" "Creep"
```

## How it evolved

This started as a simple "can I predict if I'll like a song" experiment and grew from there.

**Phase 1** — Built the data pipeline. Pulled all my scrobbles from Last.fm, generated negative samples from genres I never listen to, cleaned and merged track + artist tags, and trained the first model. Initially tried audio features via AcousticBrainz but that API was unreliable, so I pivoted to a tags-only approach with TF-IDF — turned out to work better anyway.

**Phase 2** — Added the interactive recommendation engine (the Tinder-style swiper), weekly playlist generation that adapts to your recent mood, and the text-to-playlist feature using Gemini for NLP tag extraction. Also built the persistent tag cache at this point, which cut API calls by ~95% and brought the recommendation latency down significantly.

**Phase 3** — Built the React frontend with the retro aesthetic, integrated Spotify Web Playback SDK for full song playback, and connected everything through a Flask API. Added auto-sync with smart thresholds (3-play rule), cascade fallbacks for playlist generation, and cleaned up the codebase from ~2270 lines down to ~1500.

## License

MIT
