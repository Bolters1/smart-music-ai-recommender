/**
 * SongPredictor.jsx — Predictor: iti va placea piesa asta?
 * 
 * FLOW:
 * 1. Scrii un artist si o piesa
 * 2. Apeai "Predict"
 * 3. fetch() trimite la Flask → pipeline.predict_song()
 * 4. ML-ul analizeaza tag-urile piesei si returneaza:
 *    - prediction: 'liked' sau 'disliked'
 *    - probability: cat de sigur e modelul (0.0 → 1.0)
 *    - tags: tag-urile Last.fm ale piesei
 * 5. Afisam rezultatul cu un card colorat (verde = liked, rosu = disliked)
 * 
 * CONCEPTE NOI:
 * - Doua input-uri controlate de state-uri separate
 * - Afisare conditionala pe baza rezultatului (liked vs disliked)
 */

import React, { useState } from 'react'
import { Search, Loader2, ThumbsUp, ThumbsDown, AlertCircle } from 'lucide-react'


function SongPredictor() {
  // State-uri: artist, song = ce scrie user-ul
  // result = raspunsul de la server (null = inca nu am cautat)
  const [artist, setArtist] = useState('')
  const [song, setSong] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')


  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!artist.trim() || !song.trim()) return

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ artist: artist, song: song }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Nu am putut face predictia.')
      }

      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Determinam daca predictia e "liked" — folosim asta pt culori
  const isLiked = result?.prediction === 'liked'
  // "?." se numeste "optional chaining"
  // Daca result e null, result?.prediction returneaza undefined (fara eroare)
  // Fara "?.", result.prediction ar da eroare: "Cannot read property of null"


  return (
    <div>
      <h2 className="section-heading">
        <Search size={18} /> Song Predictor
      </h2>

      {/* ─── FORMULAR CU 2 INPUT-URI ─── */}
      <form onSubmit={handleSubmit} className="retro-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', flexWrap: 'wrap' }}>
          {/* 
            Fiecare input are propriul state (artist / song).
            "flex: 1" = ocupa spatiul disponibil in mod egal.
            Ambele input-uri vor avea aceeasi latime.
          */}
          <div style={{ flex: 1, minWidth: '200px' }}>
            <label
              htmlFor="artist-input"
              style={{
                display: 'block',
                marginBottom: '6px',
                fontFamily: 'var(--font-heading)',
                fontSize: '0.8rem'
              }}
            >
              ♪ Artist:
            </label>
            <input
              id="artist-input"
              className="input-field"
              type="text"
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
              placeholder="ex: Radiohead"
              disabled={loading}
            />
          </div>

          <div style={{ flex: 1, minWidth: '200px' }}>
            <label
              htmlFor="song-input"
              style={{
                display: 'block',
                marginBottom: '6px',
                fontFamily: 'var(--font-heading)',
                fontSize: '0.8rem'
              }}
            >
              ♫ Song:
            </label>
            <input
              id="song-input"
              className="input-field"
              type="text"
              value={song}
              onChange={(e) => setSong(e.target.value)}
              placeholder="ex: Creep"
              disabled={loading}
            />
          </div>
        </div>

        <button
          type="submit"
          className="btn-primary"
          disabled={loading || !artist.trim() || !song.trim()}
        >
          {loading ? (
            <>
              <Loader2 size={16} className="spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Search size={16} />
              Predict
            </>
          )}
        </button>
      </form>

      {/* ─── EROARE ─── */}
      {error && (
        <div className="retro-card" style={{ borderColor: '#e57373', marginBottom: '20px' }}>
          <p style={{ color: '#c62828', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={16} /> {error}
          </p>
        </div>
      )}

      {/* ─── REZULTATUL PREDICTIEI ─── */}
      {result && (
        <div
          className="retro-card fade-in"
          style={{
            // Bordura si fundalul se schimba in functie de rezultat:
            // liked = verde, disliked = rosu
            borderColor: isLiked ? '#a5d6a7' : '#ef9a9a',
            background: isLiked ? '#e8f5e9' : '#fce4ec',
          }}
        >
          {/* Iconita mare + titlu */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '16px'
          }}>
            {isLiked ? (
              <ThumbsUp size={32} color="#2e7d32" />
            ) : (
              <ThumbsDown size={32} color="#c62828" />
            )}
            <div>
              <h3 style={{
                fontFamily: 'var(--font-heading)',
                color: isLiked ? '#2e7d32' : '#c62828',
                margin: 0
              }}>
                {isLiked ? 'You\'ll probably LIKE this! ♡' : 'You might NOT like this...'}
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                {artist} — {song}
              </p>
            </div>
          </div>

          {/* Probabilitate */}
          {result.probability !== undefined && (
            <div style={{ marginBottom: '12px' }}>
              <p style={{
                fontFamily: 'var(--font-heading)',
                fontSize: '0.8rem',
                marginBottom: '6px'
              }}>
                Confidence: {Math.round(result.probability * 100)}%
              </p>
              {/* Bara vizuala de confidence */}
              <div style={{
                width: '100%',
                height: '12px',
                background: '#ddd',
                borderRadius: '6px',
                overflow: 'hidden',
                border: '1px solid var(--border-color)'
              }}>
                <div style={{
                  width: `${Math.round(result.probability * 100)}%`,
                  height: '100%',
                  borderRadius: '6px',
                  background: isLiked
                    ? 'linear-gradient(90deg, #66bb6a, #43a047)'
                    : 'linear-gradient(90deg, #ef5350, #c62828)',
                  transition: 'width 0.5s ease'
                }} />
              </div>
            </div>
          )}

          {/* Tag-urile piesei */}
          {result.tags && result.tags.length > 0 && (
            <div>
              <p style={{
                fontFamily: 'var(--font-heading)',
                fontSize: '0.8rem',
                marginBottom: '6px'
              }}>
                Tags Last.fm:
              </p>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {result.tags.map((tag) => (
                  <span key={tag} className="badge badge-tag">{tag}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Mesaj initial */}
      {!loading && !result && !error && (
        <div className="retro-card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          <Search size={24} style={{ marginBottom: '8px' }} />
          <p>Scrie un artist si o piesa ca sa vezi daca o sa iti placa! ✿</p>
        </div>
      )}
    </div>
  )
}

export default SongPredictor
