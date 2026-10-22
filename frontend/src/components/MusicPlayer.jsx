/**
 * MusicPlayer.jsx — Player retro cute cu Spotify Web Playback SDK
 * 
 * Ce face:
 * - Se conecteaza la Spotify prin Web Playback SDK
 * - Reda piese INTREGI (nu doar preview) daca user-ul are Premium
 * - Arata ca un mini-player oldschool cu album art, artist, titlu, progress bar
 * - Controluri: play/pause, next, previous
 * 
 * CONCEPTE NOI:
 * 
 * useRef:
 *   Similar cu useState, dar NU cauzeaza re-render cand se schimba.
 *   Folosim pt obiectul player-ului Spotify (nu vrem sa redesenam UI-ul
 *   de fiecare data cand player-ul trimite un event intern).
 *   
 *   const playerRef = useRef(null)
 *   playerRef.current = valoarea stocata (citire/scriere directa)
 * 
 * useEffect cu cleanup:
 *   useEffect poate returna o functie de "cleanup" care ruleaza
 *   cand componenta e distrusa (cand navighezi pe alta pagina).
 *   O folosim ca sa deconectam playerul Spotify.
 *   
 *   useEffect(() => {
 *     // setup code
 *     return () => { // cleanup code }
 *   }, [])
 * 
 * setInterval:
 *   Ruleaza o functie la fiecare X milisecunde.
 *   O folosim ca sa actualizam progress bar-ul in timp real.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'


function MusicPlayer() {
  // ═══════ STATE-URI ═══════
  const [isConnected, setIsConnected] = useState(false)   // Conectat la Spotify?
  const [isPlaying, setIsPlaying] = useState(false)        // Reda muzica acum?
  const [currentTrack, setCurrentTrack] = useState(null)   // Piesa curenta {name, artist, albumArt}
  const [position, setPosition] = useState(0)              // Pozitia curenta (milisecunde)
  const [duration, setDuration] = useState(0)              // Durata totala (milisecunde)
  const [deviceId, setDeviceId] = useState(null)           // ID-ul "dispozitivului" virtual

  // ═══════ REFS ═══════
  // useRef = variabila care NU cauzeaza re-render
  const playerRef = useRef(null)        // Instanta Spotify.Player
  const intervalRef = useRef(null)      // ID-ul interval-ului de progress bar


  // ═══════ INITIALIZARE SPOTIFY SDK ═══════
  useEffect(() => {
    // Pasul 1: Verificam daca user-ul e conectat la Spotify
    const initSpotify = async () => {
      try {
        const res = await fetch('/api/spotify-token')
        const data = await res.json()

        if (!data.connected || !data.access_token) {
          setIsConnected(false)
          return
        }

        // Verificam daca are premium
        try {
          const meRes = await fetch('/api/me')
          const meData = await meRes.json()
          if (meData.product !== 'premium') {
             console.warn(`Atentie: Contul tau este '${meData.product}'. E nevoie de premium!`)
          }
        } catch (e) {
          console.error("Nu am putut verifica profilul", e)
        }

        setIsConnected(true)

        // Pasul 2: Incarcam SDK-ul Spotify (un script extern)
        // Adaugam un <script> tag in <head> care incarca SDK-ul de pe serverele Spotify
        if (!document.getElementById('spotify-sdk-script')) {
          const script = document.createElement('script')
          script.id = 'spotify-sdk-script'
          script.src = 'https://sdk.scdn.co/spotify-player.js'
          script.async = true
          document.head.appendChild(script)
        }

        // Pasul 3: Cand SDK-ul e incarcat, Spotify apeleaza aceasta functie
        // E un "callback global" — Spotify o cauta pe window (obiectul global al browserului)
        window.onSpotifyWebPlaybackSDKReady = () => {
          // Cream un "Player" — un dispozitiv virtual in browser
          const player = new window.Spotify.Player({
            name: '✿ Smart Music AI ✿',     // Numele care apare in Spotify Connect
            getOAuthToken: async (cb) => {
              try {
                const tokenRes = await fetch('/api/spotify-token')
                const tokenData = await tokenRes.json()
                const token = tokenData.access_token
                cb(token)
              } catch (err) {
                console.error(`Eroare fetch token: ${err.message}`)
                cb(null)
              }
            },
            volume: 0.5
          })

          // ─── EVENT LISTENERS ───
          // SDK-ul trimite events cand se intampla ceva

          player.addListener('initialization_error', ({ message }) => {
            console.error('Init Error:', message);
          });
          player.addListener('authentication_error', ({ message }) => {
            console.error('Auth Error:', message);
          });
          player.addListener('account_error', ({ message }) => {
            console.error('Account Error:', message);
          });
          player.addListener('playback_error', ({ message }) => {
            console.error('Playback Error:', message);
          });

          // "ready" = playerul e gata sa redea muzica
          player.addListener('ready', ({ device_id }) => {
            console.log('✿ Spotify Player ready! Device ID:', device_id)
            setDeviceId(device_id)
          })

          // "not_ready" = playerul s-a deconectat
          player.addListener('not_ready', ({ device_id }) => {
            console.log('✘ Spotify Player not ready:', device_id)
            setDeviceId(null)
          })

          // "player_state_changed" = s-a schimbat ceva (piesa, play/pause, pozitie)
          // Asta e event-ul PRINCIPAL — il folosim ca sa actualizam UI-ul
          player.addListener('player_state_changed', (state) => {
            if (!state) {
              console.log("Spotify: state is null")
              return
            }

            const track = state.track_window.current_track
            if (!track) {
              console.log("Spotify: current_track is null")
              return
            }

            setCurrentTrack({
              name: track.name,
              artist: track.artists.map(a => a.name).join(', '),
              albumArt: track.album.images[0]?.url || '',
            })
            setIsPlaying(!state.paused)
            setPosition(state.position)
            setDuration(state.duration)
          })

          // Conectam playerul la Spotify
          player.connect()
          playerRef.current = player
        }

      } catch (err) {
        console.error('Spotify init error:', err)
      }
    }

    initSpotify()

    // Cleanup: cand componenta se distruge, deconectam playerul
    return () => {
      if (playerRef.current) {
        playerRef.current.disconnect()
      }
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])  // [] = ruleaza o singura data


  // ═══════ PROGRESS BAR UPDATE ═══════
  // Actualizam pozitia la fiecare 500ms cand piesa reda
  useEffect(() => {
    if (isPlaying) {
      intervalRef.current = setInterval(() => {
        setPosition(prev => prev + 500)  // prev = valoarea anterioara
      }, 500)
    } else {
      clearInterval(intervalRef.current)
    }
    // Cleanup: oprim interval-ul cand isPlaying se schimba
    return () => clearInterval(intervalRef.current)
  }, [isPlaying])


  // ═══════ CONTROLURI ═══════
  const [isLoadingRandom, setIsLoadingRandom] = useState(false)

  const handlePlayPause = async () => {
    if (playerRef.current) {
      // Activăm audio context-ul browserului la click
      if (typeof playerRef.current.activateElement === 'function') {
        await playerRef.current.activateElement()
      }

      // Daca nu exista o piesa activa si apasam Play
      if (!currentTrack?.name && !isPlaying) {
        try {
          setIsLoadingRandom(true)
          const res = await fetch('/api/random-recent')
          
          if (!res.ok) {
            console.error(`Backend Error: ${res.status}`)
            return
          }
          
          const data = await res.json()
          
          if (data.artist && data.song) {
            if (window.playTrackOnPlayer) {
              await window.playTrackOnPlayer(data.artist, data.song)
            }
          }
        } catch (err) {
          console.error("Eroare la incarcarea piesei random:", err)
        } finally {
          setIsLoadingRandom(false)
        }
        return
      }
      
      playerRef.current.togglePlay()
    }
  }

  const handleNext = async () => {
    if (playerRef.current) {
      // In loc sa incercam sa dam skip in lista de asteptare Spotify (care e goala 
      // pentru ca i-am trimis o singura piesa), ii cerem backend-ului alta piesa random.
      try {
        setIsLoadingRandom(true)
        const res = await fetch('/api/random-recent')
        if (res.ok) {
          const data = await res.json()
          if (data.artist && data.song && window.playTrackOnPlayer) {
            await window.playTrackOnPlayer(data.artist, data.song)
          }
        }
      } catch (err) {
        console.error("Eroare la next track random:", err)
      } finally {
        setIsLoadingRandom(false)
      }
    }
  }

  const handlePrev = () => {
    if (playerRef.current) {
      playerRef.current.previousTrack()
    }
  }

  const handleSeek = (e) => {
    // Cand user-ul trage progress bar-ul, schimbam pozitia piesei
    const newPosition = parseInt(e.target.value)
    setPosition(newPosition)
    if (playerRef.current) {
      playerRef.current.seek(newPosition)
    }
  }

  // Functie helper: converteste milisecunde in MM:SS
  const formatTime = (ms) => {
    const totalSeconds = Math.floor(ms / 1000)
    const min = Math.floor(totalSeconds / 60)
    const sec = totalSeconds % 60
    return `${min}:${sec < 10 ? '0' : ''}${sec}`
  }


  // ═══════ FUNCTIE PUBLICA: reda o piesa dupa artist + titlu ═══════
  // Aceasta functie e exportata prin window ca sa poata fi apelata
  // din alte componente (PromptGenerator, WeeklyDiscover etc.)
  useEffect(() => {
    window.playTrackOnPlayer = async (artist, song) => {
      if (!deviceId) return

      try {
        const searchRes = await fetch(
          `/api/spotify-search?q=${encodeURIComponent(artist + ' ' + song)}`
        )
        const searchData = await searchRes.json()

        if (!searchData.uri) return

        const tokenData = await (await fetch('/api/spotify-token')).json()
        const token = tokenData.access_token

        const playRes = await fetch(`https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ uris: [searchData.uri] })
        })

        if (!playRes.ok) {
           const errText = await playRes.text()
           console.error(`Spotify API Err: ${playRes.status} - ${errText}`)
        }
      } catch (err) {
        console.error('Play track error:', err)
      }
    }
  }, [deviceId])


  // ═══════ RENDER ═══════

  // Daca nu e conectat la Spotify, afisam buton de login
  if (!isConnected) {
    return (
      <div className="music-player">
        <div className="music-player-login">
          <p style={{ fontSize: '0.75rem', marginBottom: '8px', textAlign: 'center' }}>
            ♪ Music Player ♪
          </p>
          <a href="http://127.0.0.1:5000/login" className="btn-primary" style={{
            fontSize: '0.7rem', padding: '6px 12px', textDecoration: 'none',
            display: 'block', textAlign: 'center'
          }}>
            ✿ Login with Spotify
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="music-player">
      {/* Album art */}
      <div className="music-player-art" style={{ position: 'relative' }}>
        {currentTrack?.albumArt ? (
          <img src={currentTrack.albumArt} alt="Album art" />
        ) : (
          <div className="music-player-art-placeholder">♪</div>
        )}
      </div>

      {/* Track info */}
      <div className="music-player-info">
        <div className="music-player-title">
          {currentTrack?.name || (isLoadingRandom ? 'Loading track...' : 'Click ▶ to shuffle')}
        </div>
        <div className="music-player-artist">
          {currentTrack?.artist || 'Your Recent Mix'}
        </div>
      </div>

      {/* Progress bar */}
      <div className="music-player-progress">
        <span className="music-player-time">{formatTime(position)}</span>
        <input
          type="range"
          className="music-player-bar"
          min="0"
          max={duration || 0}
          value={position}
          onChange={handleSeek}
        />
        <span className="music-player-time">{formatTime(duration)}</span>
      </div>

      {/* Controls */}
      <div className="music-player-controls">
        <button onClick={handlePrev} className="music-player-btn" title="Previous">
          ⏮
        </button>
        <button onClick={handlePlayPause} className="music-player-btn music-player-btn-play" title="Play/Pause">
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button onClick={handleNext} className="music-player-btn" title="Next">
          ⏭
        </button>
      </div>
    </div>
  )
}

export default MusicPlayer
