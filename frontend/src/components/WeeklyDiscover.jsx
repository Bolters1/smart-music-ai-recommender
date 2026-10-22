/**
 * WeeklyDiscover.jsx — Playlist saptamanal personalizat
 * 
 * FLOW:
 * 1. Apeai "Generate Weekly Playlist"
 * 2. fetch() → Flask → pipeline.generate_weekly_playlist()
 * 3. Pipeline face sync cu Last.fm (daca nu s-a facut recent),
 *    alege "ancore" (piese pe care le asculti deja) si
 *    "descoperiri" (piese noi recomandate de ML)
 * 4. Afisam playlist-ul cu badge-uri colorate pt sursa fiecarei piese
 * 
 * CONCEPT NOU: useEffect
 * - Nu il folosim inca aici, dar il vei vedea la StatsPage.
 *   useEffect ruleaza cod automat cand componenta apare pe ecran.
 *   Aici totul porneste de la un buton, deci nu avem nevoie de el.
 */

import React, { useState } from 'react'
import { CalendarHeart, Loader2, Music, Star, RefreshCw, Heart, ListPlus } from 'lucide-react'


function WeeklyDiscover() {
  const [tracks, setTracks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [trackUris, setTrackUris] = useState({})
  const [savedToSpotify, setSavedToSpotify] = useState({})
  const [savingPlaylist, setSavingPlaylist] = useState(false)
  const [playlistUrl, setPlaylistUrl] = useState('')


  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    setTracks([])

    try {
      const response = await fetch('/api/generate-weekly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days: 7 }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Nu am putut genera playlist-ul.')
      }

      setTracks(data.tracks || [])
      
      if (data.tracks && data.tracks.length > 0) {
        const uris = {}
        Promise.allSettled(
          data.tracks.map(async (track, index) => {
            const res = await fetch(`/api/spotify-search?artist=${encodeURIComponent(track.artist)}&track=${encodeURIComponent(track.song)}`)
            if (res.ok) {
              const sData = await res.json()
              if (sData.uri) {
                uris[index] = sData.uri
              }
            }
          })
        ).then(() => {
          setTrackUris(uris)
        })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }


  // Functie helper care returneaza clasa CSS + textul badge-ului
  // pe baza sursei piesei (anchor/discovery/fallback)
  const getSourceBadge = (source) => {
    switch (source) {
      case 'anchor':
        return { className: 'badge badge-local', text: '♡ anchor' }
      case 'discovery':
        return { className: 'badge badge-discovery', text: '✧ discovery' }
      default:
        return { className: 'badge badge-tag', text: source || 'unknown' }
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
      }
    } catch (err) {
      console.error('Eroare la salvarea/stergerea piesei pe Spotify:', err)
    }
  }

  // ═══════ SAVE PLAYLIST ═══════
  const handleSavePlaylist = async () => {
    setSavingPlaylist(true)
    setError('')
    
    const uris = Object.values(trackUris).filter(Boolean)
    if (uris.length === 0) {
      setError('Asteapta incarcarea datelor de la Spotify pentru piese.')
      setSavingPlaylist(false)
      return
    }

    try {
      const response = await fetch('/api/spotify-create-playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          name: `Weekly Discover - ${new Date().toLocaleDateString()}`,
          uris: uris
        })
      })
      
      const data = await response.json()
      if (response.ok) {
        setPlaylistUrl(data.playlist_url)
      } else {
        throw new Error(data.error || 'Eroare la salvarea playlistului')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingPlaylist(false)
    }
  }


  return (
    <div>
      <h2 className="section-heading">
        <CalendarHeart size={18} /> Weekly Discover Playlist
      </h2>

      {/* Buton de generare (nu e in <form>, e un simplu buton) */}
      <div className="retro-card" style={{ marginBottom: '24px' }}>
        <p style={{ marginBottom: '12px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          Genereaza un mix saptamanal de <strong>ancore</strong> (piese pe care le asculti deja
          si stii ca iti plac) si <strong>descoperiri</strong> (piese noi selectate de ML pe baza
          gusturilor tale).
        </p>

        {/* 
          onClick vs onSubmit:
          - onSubmit se foloseste pe <form> (si prinde si Enter)
          - onClick se foloseste pe <button> simplu (fara <form>)
          
          Aici nu avem niciun input, doar un buton, deci onClick e suficient.
        */}
        <button
          className="btn-primary"
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 size={16} className="spin" />
              Se genereaza... (poate dura cateva secunde)
            </>
          ) : (
            <>
              <RefreshCw size={16} />
              Generate Weekly Playlist
            </>
          )}
        </button>
      </div>

      {/* Eroare */}
      {error && (
        <div className="retro-card" style={{ borderColor: '#e57373', marginBottom: '20px' }}>
          <p style={{ color: '#c62828' }}>✘ {error}</p>
        </div>
      )}

      {/* Lista de piese */}
      {tracks.length > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 className="section-heading" style={{ margin: 0 }}>
              <Music size={16} /> Your Weekly Mix ({tracks.length} piese)
            </h3>
            
            {playlistUrl ? (
              <a href={playlistUrl} target="_blank" rel="noreferrer" className="btn-primary" style={{ backgroundColor: '#4ade80', color: '#1a1a1a', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Star size={16} fill="#1a1a1a" /> Playlist Saved!
              </a>
            ) : (
              <button 
                className="btn-secondary" 
                onClick={handleSavePlaylist} 
                disabled={savingPlaylist || Object.keys(trackUris).length === 0}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {savingPlaylist ? <Loader2 size={16} className="spin" /> : <ListPlus size={16} />}
                Save as Spotify Playlist
              </button>
            )}
          </div>

          <div className="scrollbox" style={{ maxHeight: '500px' }}>
            {tracks.map((track, index) => {
              const badge = getSourceBadge(track.source)
              return (
                <div key={index} className="track-row">
                  <span style={{
                    fontFamily: 'var(--font-heading)',
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)',
                    width: '28px',
                    textAlign: 'right'
                  }}>
                    {index + 1}.
                  </span>

                  <Star
                    size={14}
                    fill={track.source === 'anchor' ? 'var(--accent-peach)' : 'none'}
                    color="var(--accent-peach)"
                  />

                  <div style={{ flex: 1 }}>
                    <span style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>
                      {track.song}
                    </span>
                    <span style={{ color: 'var(--text-muted)', margin: '0 6px' }}>—</span>
                    <span style={{ fontSize: '0.9rem' }}>{track.artist}</span>
                  </div>

                  {track.score !== undefined && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div className="score-bar">
                        <div
                          className="score-bar-fill"
                          style={{ width: `${Math.round(track.score * 100)}%` }}
                        />
                      </div>
                      <span style={{
                        fontFamily: 'var(--font-heading)',
                        fontSize: '0.7rem',
                        color: 'var(--text-secondary)',
                        width: '32px'
                      }}>
                        {Math.round(track.score * 100)}%
                      </span>
                    </div>
                  )}

                  <span className={badge.className}>{badge.text}</span>

                  <div style={{ display: 'flex', gap: '4px' }}>
                    {/* Buton Save/Remove Liked Songs */}
                    {trackUris[index] && (
                      <button
                        className="btn-secondary"
                        style={{ 
                          padding: '4px 8px', 
                          color: savedToSpotify[index] ? '#4ade80' : 'inherit',
                          borderColor: savedToSpotify[index] ? '#4ade80' : 'var(--border-color)',
                          cursor: 'pointer'
                        }}
                        onClick={() => handleSaveToSpotify(index)}
                        title={savedToSpotify[index] ? "Remove from Liked Songs" : "Save to Liked Songs"}
                      >
                        <Heart size={14} fill={savedToSpotify[index] ? '#4ade80' : 'none'} />
                      </button>
                    )}

                    {/* Buton play — trimite piesa la playerul Spotify din sidebar */}
                    <button
                      className="btn-secondary"
                      style={{ padding: '4px 8px', fontSize: '0.7rem' }}
                      onClick={() => window.playTrackOnPlayer?.(track.artist, track.song)}
                      title="Play in sidebar player"
                    >
                      ▶
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Mesaj initial */}
      {!loading && tracks.length === 0 && !error && (
        <div className="retro-card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          <CalendarHeart size={24} style={{ marginBottom: '8px' }} />
          <p>Apasa butonul de mai sus ca sa iti generezi playlist-ul saptamanal! ✿</p>
        </div>
      )}
    </div>
  )
}

export default WeeklyDiscover
