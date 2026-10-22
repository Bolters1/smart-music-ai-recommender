/**
 * RecommendPage.jsx — Recomandari ML personalizate (5 piese)
 * 
 * FLOW:
 * 1. Apesi "Get Recommendations"
 * 2. fetch() → Flask → pipeline.get_recommendation_candidates() + ML scoring
 * 3. Pipeline cauta piese candidate din Last.fm (deep cuts, artisti similari,
 *    piese similare), le scoreaza cu Random Forest
 * 4. Afisam top 5 piese cu scor ML, buton Play, si Like/Dislike feedback
 * 
 * Feedback-ul (like/dislike) este salvat in master_dataset_pre_spotify.csv
 * pentru reantrenarea modelului, similar cu swipe-ul din terminal.
 */

import React, { useState } from 'react'
import { Star, Loader2, ThumbsUp, ThumbsDown, Play, RefreshCw, Heart } from 'lucide-react'


function RecommendPage() {
  // State-uri (variabile reactive):
  const [recommendations, setRecommendations] = useState([])  // Lista de piese recomandate
  const [loading, setLoading] = useState(false)                // Spinner de incarcare
  const [error, setError] = useState('')                       // Mesaj de eroare
  const [feedbackGiven, setFeedbackGiven] = useState({})       // Tracking: care piese au primit feedback
  const [albumArts, setAlbumArts] = useState({})               // Cache pt album art de pe Spotify
  const [trackUris, setTrackUris] = useState({})               // Cache pt URI-uri Spotify
  const [savedToSpotify, setSavedToSpotify] = useState({})     // Tracking piese salvate in Spotify


  // ═══════ GENERARE RECOMANDARI ═══════
  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    setRecommendations([])
    setFeedbackGiven({})
    setAlbumArts({})
    setTrackUris({})
    setSavedToSpotify({})

    try {
      // Apelam backend-ul nostru Flask care ruleaza modelul ML
      const response = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Nu am putut genera recomandari.')
      }

      const recs = data.recommendations || []
      setRecommendations(recs)

      // Luam album art + URI de pe Spotify pentru fiecare piesa (in paralel, fara sa blocam)
      recs.forEach((rec, index) => {
        fetch(`/api/spotify-search?artist=${encodeURIComponent(rec.artist)}&track=${encodeURIComponent(rec.song)}`)
          .then(res => res.ok ? res.json() : Promise.reject('no spotify'))
          .then(spotifyData => {
            // Salvam URI-ul separat — chiar daca nu are album art
            if (spotifyData.uri) {
              setTrackUris(prev => ({ ...prev, [index]: spotifyData.uri }))
            }
            if (spotifyData.album_art) {
              setAlbumArts(prev => ({ ...prev, [index]: spotifyData.album_art }))
            } else {
              // Fallback: Last.fm track image (doar pt poza, URI-ul e deja salvat)
              return fetch(`https://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key=a88d4c09c53d1de3607a4cc3bcc0e1e6&artist=${encodeURIComponent(rec.artist)}&track=${encodeURIComponent(rec.song)}&format=json`)
                .then(res => res.json())
                .then(lfm => {
                  const images = lfm?.track?.album?.image || []
                  const large = images.find(i => i.size === 'large') || images[images.length - 1]
                  if (large && large['#text']) {
                    setAlbumArts(prev => ({ ...prev, [index]: large['#text'] }))
                  }
                })
            }
          })
          .catch(() => {
            // Spotify search a esuat complet — incercam Last.fm pt imagine
            fetch(`https://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key=a88d4c09c53d1de3607a4cc3bcc0e1e6&artist=${encodeURIComponent(rec.artist)}&track=${encodeURIComponent(rec.song)}&format=json`)
              .then(res => res.json())
              .then(lfm => {
                const images = lfm?.track?.album?.image || []
                const large = images.find(i => i.size === 'large') || images[images.length - 1]
                if (large && large['#text']) {
                  setAlbumArts(prev => ({ ...prev, [index]: large['#text'] }))
                }
              })
              .catch(() => {})
          })
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }


  // ═══════ PLAY TRACK ═══════
  const handlePlay = async (artist, song) => {
    if (window.playTrackOnPlayer) {
      await window.playTrackOnPlayer(artist, song)
    }
  }

  // ═══════ TOGGLE SAVE TO SPOTIFY ═══════
  const handleSaveToSpotify = async (index) => {
    const uri = trackUris[index]
    if (!uri) return
    
    const isCurrentlySaved = !!savedToSpotify[index]
    const endpoint = isCurrentlySaved ? '/api/spotify-unlike' : '/api/spotify-like'
    
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uri })
      })
      
      if (response.ok) {
        setSavedToSpotify(prev => ({ ...prev, [index]: !isCurrentlySaved }))
      } else {
        const errData = await response.json().catch(() => ({}))
        console.error('Toggle spotify failed:', errData)
        if (response.status === 401) {
          alert('Nu esti conectat la Spotify! Te rog sa te reconectezi.')
        }
      }
    } catch (err) {
      console.error('Eroare la salvarea/stergerea piesei pe Spotify:', err)
    }
  }


  // ═══════ FEEDBACK (LIKE / DISLIKE) ═══════
  const handleFeedback = async (index, artist, song, liked) => {
    try {
      await fetch('/api/recommend-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          artist: artist,
          song: song,
          feedback: liked ? 1 : 0
        })
      })

      // Marcam ca s-a dat feedback pt piesa asta
      setFeedbackGiven(prev => ({ ...prev, [index]: liked ? 'liked' : 'disliked' }))
    } catch (err) {
      console.error('Eroare la salvarea feedback-ului:', err)
    }
  }


  // ═══════ HELPER: Culoare bara de scor ═══════
  const getScoreColor = (score) => {
    if (score >= 0.8) return '#4ade80'  // Verde stralucitor = super match
    if (score >= 0.6) return '#a3e635'  // Verde-galben = match bun
    if (score >= 0.4) return '#facc15'  // Galben = decent
    return '#fb923c'                     // Portocaliu = risky
  }


  return (
    <div>
      <h2 className="section-heading">
        <Star size={18} /> Song Recommendations
      </h2>

      {/* Zona de generare */}
      <div className="retro-card" style={{ marginBottom: '24px' }}>
        <p style={{ marginBottom: '12px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          Modelul ML analizeaza gusturile tale muzicale si iti recomanda <strong>5 piese noi</strong> pe
          care probabil le vei adora. Fiecare piesa vine cu un scor de compatibilitate.
          Poti da <strong>Like</strong> sau <strong>Dislike</strong> pentru a imbunatati recomandarile viitoare!
        </p>
        <p style={{ marginBottom: '16px', fontSize: '0.8rem', color: 'var(--text-secondary)', opacity: 0.7 }}>
          ⏱ Generarea dureaza ~30-60 secunde (cauta piese pe Last.fm si le scoreaza cu ML)
        </p>

        <button
          className="btn-primary"
          onClick={handleGenerate}
          disabled={loading}
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          {loading ? (
            <>
              <Loader2 size={14} className="spin" />
              Analyzing your taste...
            </>
          ) : (
            <>
              <RefreshCw size={14} />
              Get 5 Recommendations
            </>
          )}
        </button>
      </div>

      {/* Eroare */}
      {error && (
        <div className="retro-card" style={{ borderColor: 'var(--accent-pink)', marginBottom: '16px' }}>
          <p style={{ color: 'var(--accent-pink)' }}>✘ {error}</p>
        </div>
      )}

      {/* Lista de recomandari */}
      {recommendations.length > 0 && (
        <div className="recommend-list">
          {recommendations.map((rec, index) => (
            <div key={index} className="recommend-card retro-card">
              
              {/* Album Art */}
              <div className="recommend-art">
                {albumArts[index] ? (
                  <img src={albumArts[index]} alt="Album art" />
                ) : (
                  <div className="recommend-art-placeholder">♪</div>
                )}
              </div>

              {/* Info */}
              <div className="recommend-info">
                <div className="recommend-song">{rec.song}</div>
                <div className="recommend-artist">{rec.artist}</div>

                {/* Scor ML */}
                <div className="recommend-score-row">
                  <span className="recommend-score-label">ML Match:</span>
                  <div className="recommend-score-bar-bg">
                    <div
                      className="recommend-score-bar-fill"
                      style={{
                        width: `${Math.round(rec.prob_liked * 100)}%`,
                        backgroundColor: getScoreColor(rec.prob_liked)
                      }}
                    />
                  </div>
                  <span className="recommend-score-value" style={{ color: getScoreColor(rec.prob_liked) }}>
                    {Math.round(rec.prob_liked * 100)}%
                  </span>
                </div>

                {/* Tags */}
                {rec.track_tags && rec.track_tags.length > 0 && (
                  <div className="recommend-tags">
                    {rec.track_tags.slice(0, 3).map((tag, i) => (
                      <span key={i} className="badge badge-tag">{tag}</span>
                    ))}
                  </div>
                )}
              </div>

              {/* Actiuni */}
              <div className="recommend-actions">
                {/* Play Button */}
                <button
                  className="recommend-btn recommend-btn-play"
                  onClick={() => handlePlay(rec.artist, rec.song)}
                  title="Play on Spotify"
                >
                  <Play size={16} />
                </button>
                
                {/* Save/Remove Spotify Button */}
                {trackUris[index] && (
                  <button
                    className="recommend-btn"
                    onClick={() => handleSaveToSpotify(index)}
                    title={savedToSpotify[index] ? "Remove from Liked Songs" : "Save to Liked Songs"}
                    style={{ 
                      color: savedToSpotify[index] ? '#4ade80' : 'var(--text-secondary)',
                      borderColor: savedToSpotify[index] ? '#4ade80' : 'var(--border-color)',
                      cursor: 'pointer'
                    }}
                  >
                    <Heart size={16} fill={savedToSpotify[index] ? '#4ade80' : 'none'} />
                  </button>
                )}

                {/* Like/Dislike Feedback */}
                {feedbackGiven[index] ? (
                  <div className={`recommend-feedback-done ${feedbackGiven[index]}`}>
                    {feedbackGiven[index] === 'liked' ? '♡' : '✘'}
                  </div>
                ) : (
                  <>
                    <button
                      className="recommend-btn recommend-btn-like"
                      onClick={() => handleFeedback(index, rec.artist, rec.song, true)}
                      title="Like - imi place!"
                    >
                      <ThumbsUp size={14} />
                    </button>
                    <button
                      className="recommend-btn recommend-btn-dislike"
                      onClick={() => handleFeedback(index, rec.artist, rec.song, false)}
                      title="Dislike - nu imi place"
                    >
                      <ThumbsDown size={14} />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Mesaj dupa ce s-au dat toate feedback-urile */}
      {recommendations.length > 0 && Object.keys(feedbackGiven).length === recommendations.length && (
        <div className="retro-card" style={{ textAlign: 'center', marginTop: '16px' }}>
          <p style={{ fontSize: '0.9rem' }}>
            ✧ Multumim pentru feedback! Ruleaza <code>python pipeline.py process-all</code> si apoi
            <code> python pipeline.py train</code> in terminal pentru a imbunatati modelul.
          </p>
        </div>
      )}
    </div>
  )
}

export default RecommendPage
