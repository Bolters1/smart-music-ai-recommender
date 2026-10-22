/**
 * StatsPage.jsx — Statistici Last.fm + Baza de date ML
 * 
 * FLOW:
 * 1. La incarcare, fetch /api/stats (ML stats, o singura data)
 *    + fetch /api/lastfm-stats?period=7day (Last.fm, se re-fetcha la schimbare perioada)
 * 2. Afisam: profil user, top piese, top artisti, top albume, ML stats, top tags
 * 
 * Perioada se poate schimba: This Week / This Month / 3 Months / 6 Months / All Time
 */

import React, { useState, useEffect } from 'react'
import { 
  BarChart3, Loader2, Music, Heart, HeartOff, Tag, 
  Play, User, Disc, Mic2, TrendingUp 
} from 'lucide-react'

// Perioadele disponibile pe Last.fm API
const PERIODS = [
  { value: '7day',    label: 'This Week' },
  { value: '1month',  label: 'This Month' },
  { value: '3month',  label: '3 Months' },
  { value: '6month',  label: '6 Months' },
  { value: '12month', label: 'This Year' },
  { value: 'overall', label: 'All Time' },
]

function StatsPage() {
  const [period, setPeriod] = useState('7day')
  const [lastfmData, setLastfmData] = useState(null)
  const [mlStats, setMlStats] = useState(null)
  const [loadingLastfm, setLoadingLastfm] = useState(true)
  const [loadingMl, setLoadingMl] = useState(true)
  const [error, setError] = useState('')
  
  // State pentru imaginile incarcate dinamic (cand Last.fm nu are poze bune)
  const [trackImages, setTrackImages] = useState({})
  const [artistImages, setArtistImages] = useState({})

  // ═══════ ML Stats — se incarca O SINGURA DATA ═══════
  useEffect(() => {
    fetch('/api/stats')
      .then(res => res.json())
      .then(data => setMlStats(data))
      .catch(err => console.error('ML stats error:', err))
      .finally(() => setLoadingMl(false))
  }, [])

  // ═══════ Last.fm Stats — se re-incarca la schimbarea perioadei ═══════
  useEffect(() => {
    setLoadingLastfm(true)
    setError('')
    fetch(`/api/lastfm-stats?period=${period}`)
      .then(res => res.json())
      .then(data => {
        if (data.error) throw new Error(data.error)
        setLastfmData(data)
        
        // Incarcam imaginile lipsa pentru piese si artisti de pe Spotify asincron
        if (data.top_tracks) {
          data.top_tracks.forEach((track, i) => {
            if (!track.image || track.image.includes('2a96cbd8')) {
              fetch(`/api/spotify-search?artist=${encodeURIComponent(track.artist)}&track=${encodeURIComponent(track.name)}`)
                .then(res => res.ok ? res.json() : Promise.reject())
                .then(sData => {
                  if (sData.album_art) setTrackImages(p => ({ ...p, [i]: sData.album_art }))
                })
                .catch(() => {})
            }
          })
        }
        
        if (data.top_artists) {
          data.top_artists.forEach((artist, i) => {
            if (!artist.image || artist.image.includes('2a96cbd8')) {
              fetch(`/api/spotify-artist-search?artist=${encodeURIComponent(artist.name)}`)
                .then(res => res.ok ? res.json() : Promise.reject())
                .then(sData => {
                  if (sData.image) setArtistImages(p => ({ ...p, [i]: sData.image }))
                })
                .catch(() => {})
            }
          })
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoadingLastfm(false))
  }, [period])

  // ═══════ Play track pe Spotify ═══════
  const handlePlay = (artist, song) => {
    if (window.playTrackOnPlayer) {
      window.playTrackOnPlayer(artist, song)
    }
  }

  return (
    <div>
      <h2 className="section-heading">
        <TrendingUp size={18} /> Your Listening Stats
      </h2>

      {/* ─── SELECTOR PERIOADA ─── */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '20px' }}>
        {PERIODS.map(p => (
          <button
            key={p.value}
            onClick={() => setPeriod(p.value)}
            className={period === p.value ? 'btn-primary' : 'btn-secondary'}
            style={{ fontSize: '0.75rem', padding: '5px 12px' }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* ─── EROARE ─── */}
      {error && (
        <div className="retro-card" style={{ borderColor: 'var(--accent-pink)', marginBottom: '16px' }}>
          <p style={{ color: 'var(--accent-pink)' }}>✘ {error}</p>
        </div>
      )}

      {/* ─── PROFIL + ML STATS ─── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {/* Total Scrobbles */}
        <div className="retro-card" style={{ textAlign: 'center' }}>
          <User size={24} color="var(--accent-lavender)" />
          <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.8rem', color: 'var(--accent-lavender)', margin: '8px 0 4px' }}>
            {lastfmData ? parseInt(lastfmData.user_info?.playcount || 0).toLocaleString() : '...'}
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Total Scrobbles</p>
        </div>

        {/* ML: Total piese */}
        <div className="retro-card" style={{ textAlign: 'center' }}>
          <Music size={24} color="var(--accent-mint)" />
          <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.8rem', color: 'var(--accent-mint)', margin: '8px 0 4px' }}>
            {mlStats?.total_songs?.toLocaleString() || '...'}
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Songs in DB</p>
        </div>

        {/* ML: Liked */}
        <div className="retro-card" style={{ textAlign: 'center' }}>
          <Heart size={24} color="#66bb6a" fill="#66bb6a" />
          <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.8rem', color: '#43a047', margin: '8px 0 4px' }}>
            {mlStats?.liked_count?.toLocaleString() || '...'}
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Liked</p>
        </div>

        {/* ML: Disliked */}
        <div className="retro-card" style={{ textAlign: 'center' }}>
          <HeartOff size={24} color="#ef5350" />
          <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.8rem', color: '#e53935', margin: '8px 0 4px' }}>
            {mlStats?.disliked_count?.toLocaleString() || '...'}
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Disliked</p>
        </div>

        {/* ML: Model status */}
        <div className="retro-card" style={{ textAlign: 'center' }}>
          <BarChart3 size={24} color="var(--accent-peach)" />
          <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.2rem', color: mlStats?.has_model ? '#43a047' : '#e53935', margin: '8px 0 4px' }}>
            {mlStats?.has_model ? '✓ Trained' : '✗ Not trained'}
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>ML Model</p>
        </div>
      </div>

      {/* ─── LOADING LASTFM ─── */}
      {loadingLastfm && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Loader2 size={28} className="spin" color="var(--accent-pink)" />
          <p style={{ marginTop: '8px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Se incarca datele de pe Last.fm...
          </p>
        </div>
      )}

      {/* ─── TOP 10 TRACKS ─── */}
      {!loadingLastfm && (
        <div className="retro-card" style={{ marginBottom: '20px' }}>
          <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Music size={16} color="var(--accent-pink)" />
            Top 10 Tracks — {PERIODS.find(p => p.value === period)?.label}
          </h3>
          {lastfmData?.top_tracks?.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {lastfmData.top_tracks.map((track, i) => (
                <div key={i} className="stats-row">
                  <span className="stats-rank">{i + 1}</span>
                  <div className="stats-img-wrap">
                    {(track.image && !track.image.includes('2a96cbd8')) || trackImages[i] ? (
                      <img src={trackImages[i] || track.image} alt="" className="stats-img" />
                    ) : (
                      <div className="stats-img-placeholder"><Music size={14} /></div>
                    )}
                  </div>
                  <div className="stats-info">
                    <div className="stats-primary">{track.name}</div>
                    <div className="stats-secondary">{track.artist}</div>
                  </div>
                  <span className="stats-count">{parseInt(track.playcount).toLocaleString()} plays</span>
                  <button
                    className="stats-play-btn"
                    onClick={() => handlePlay(track.artist, track.name)}
                    title="Play"
                  >
                    <Play size={12} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', padding: '20px 0' }}>
              Nu ai ascultat nicio piesă în această perioadă.
            </p>
          )}
        </div>
      )}

      {/* ─── TOP 10 ARTISTS ─── */}
      {!loadingLastfm && (
        <div className="retro-card" style={{ marginBottom: '20px' }}>
          <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Mic2 size={16} color="var(--accent-lavender)" />
            Top 10 Artists — {PERIODS.find(p => p.value === period)?.label}
          </h3>
          {lastfmData?.top_artists?.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {lastfmData.top_artists.map((artist, i) => (
                <div key={i} className="stats-row">
                  <span className="stats-rank">{i + 1}</span>
                  <div className="stats-img-wrap">
                    {(artist.image && !artist.image.includes('2a96cbd8')) || artistImages[i] ? (
                      <img src={artistImages[i] || artist.image} alt="" className="stats-img" />
                    ) : (
                      <div className="stats-img-placeholder"><Mic2 size={14} /></div>
                    )}
                  </div>
                  <div className="stats-info">
                    <div className="stats-primary">{artist.name}</div>
                  </div>
                  <span className="stats-count">{parseInt(artist.playcount).toLocaleString()} plays</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', padding: '20px 0' }}>
              Nu ai ascultat niciun artist în această perioadă.
            </p>
          )}
        </div>
      )}

      {/* ─── TOP 10 ALBUMS ─── */}
      {!loadingLastfm && (
        <div className="retro-card" style={{ marginBottom: '20px' }}>
          <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Disc size={16} color="var(--accent-mint)" />
            Top 10 Albums — {PERIODS.find(p => p.value === period)?.label}
          </h3>
          {lastfmData?.top_albums?.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {lastfmData.top_albums.map((album, i) => (
                <div key={i} className="stats-row">
                  <span className="stats-rank">{i + 1}</span>
                  <div className="stats-img-wrap">
                    {album.image ? (
                      <img src={album.image} alt="" className="stats-img" />
                    ) : (
                      <div className="stats-img-placeholder"><Disc size={14} /></div>
                    )}
                  </div>
                  <div className="stats-info">
                    <div className="stats-primary">{album.name}</div>
                    <div className="stats-secondary">{album.artist}</div>
                  </div>
                  <span className="stats-count">{parseInt(album.playcount).toLocaleString()} plays</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', padding: '20px 0' }}>
              Nu ai ascultat niciun album în această perioadă.
            </p>
          )}
        </div>
      )}

      {/* ─── TOP TAGS (din ML DB) ─── */}
      {mlStats?.top_tags && mlStats.top_tags.length > 0 && (
        <div className="retro-card">
          <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Tag size={16} color="var(--accent-pink)" />
            Top 15 Tags in Your ML Database
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {mlStats.top_tags.map((item, index) => (
              <div key={item.tag} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontFamily: 'var(--font-heading)', fontSize: '0.75rem', color: 'var(--text-secondary)', width: '24px', textAlign: 'right' }}>
                  {index + 1}.
                </span>
                <span style={{ fontFamily: 'var(--font-heading)', fontSize: '0.8rem', width: '120px' }}>
                  {item.tag}
                </span>
                <div style={{ flex: 1, height: '14px', background: 'var(--bg-page)', borderRadius: '7px', overflow: 'hidden', border: '1px solid var(--border-color)' }}>
                  <div style={{
                    width: `${item.percentage}%`,
                    height: '100%',
                    borderRadius: '7px',
                    background: 'linear-gradient(90deg, var(--accent-pink), var(--accent-lavender))',
                    transition: 'width 0.5s ease'
                  }} />
                </div>
                <span style={{ fontFamily: 'var(--font-heading)', fontSize: '0.7rem', color: 'var(--text-secondary)', width: '45px', textAlign: 'right' }}>
                  {item.percentage}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default StatsPage
