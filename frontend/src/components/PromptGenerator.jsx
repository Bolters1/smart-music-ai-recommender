/**
 * PromptGenerator.jsx — Generatorul de playlist-uri din text
 * 
 * FLOW:
 * 1. User-ul scrie un prompt (ex: "muzica trista cu pian")
 * 2. Apasam butonul "Generate"
 * 3. React trimite prompt-ul la Flask cu fetch()
 * 4. Flask il trimite la Gemini AI care extrage tag-uri muzicale
 * 5. pipeline.py cauta piese care se potrivesc cu acele tag-uri
 * 6. React primeste lista de piese si le afiseaza
 * 
 * CONCEPTE NOI:
 * - useState: mai multe state-uri (prompt, tracks, loading, error, tags)
 * - async/await: asteptam raspunsul de la server
 * - fetch(): trimitem cereri HTTP
 * - conditional rendering: afisam chestii diferite daca e loading/error/success
 * - .map(): iteram prin lista de piese si cream un element HTML pt fiecare
 */

import React, { useState } from 'react'
import { Sparkles, Send, Loader2, Music, Star, Heart, ListPlus } from 'lucide-react'


function PromptGenerator() {
  // ═══════════════════════════════════════════════════════════════
  // STATE-URI (variabile reactive)
  //
  // Fiecare useState returneaza un array cu 2 elemente:
  //   [valoarea curenta, functia care o schimba]
  //
  // Cand apelam setPrompt('ceva'), React REDESENEAZA automat
  // componenta cu noua valoare. Asta e "magia" React-ului.
  // ═══════════════════════════════════════════════════════════════

  const [prompt, setPrompt] = useState('')           // Ce a scris user-ul in input
  const [tracks, setTracks] = useState([])           // Lista de piese primite de la server
  const [tags, setTags] = useState([])               // Tag-urile extrase de Gemini din prompt
  const [loading, setLoading] = useState(false)      // true cat timp asteptam raspunsul
  const [error, setError] = useState('')             // Mesajul de eroare (daca apare una)
  const [trackUris, setTrackUris] = useState({})
  const [savedToSpotify, setSavedToSpotify] = useState({})
  const [savingPlaylist, setSavingPlaylist] = useState(false)
  const [playlistUrl, setPlaylistUrl] = useState('')


  // ═══════════════════════════════════════════════════════════════
  // FUNCTIA handleSubmit — ce se intampla cand apeai "Generate"
  //
  // "async" = aceasta functie contine operatii care dureaza
  //           (API call-uri). "await" = asteapta sa se termine.
  //
  // Fara async/await, codul ar continua imediat fara sa astepte
  // raspunsul de la server, si am afisa o lista goala.
  // ═══════════════════════════════════════════════════════════════

  const handleSubmit = async (e) => {
    // e = "event" (evenimentul de submit al formularului)
    // preventDefault() opreste comportamentul default al <form>:
    // fara el, browser-ul ar reincarca TOATA pagina (asa functioneaza HTML-ul vechi).
    // Noi nu vrem asta — vrem sa ramana pe pagina si sa afisam rezultatele.
    e.preventDefault()

    // Verificam ca prompt-ul nu e gol
    if (!prompt.trim()) return    // .trim() scoate spatiile de la inceput/sfarsit

    // Setam starea: incepem loading-ul, stergem erorile vechi si piesele vechi
    setLoading(true)
    setError('')
    setTracks([])
    setTags([])
    setTrackUris({})
    setSavedToSpotify({})
    setPlaylistUrl('')

    try {
      // ─── FETCH: trimitem cererea la server ───
      //
      // fetch(url, optiuni) trimite o cerere HTTP.
      //   - method: 'POST' = trimitem date (nu cerem, ci TRIMITEM)
      //   - headers: spunem serverului ca trimitem JSON
      //   - body: datele pe care le trimitem (prompt-ul + limita)
      //
      // JSON.stringify() converteste obiectul JavaScript in text JSON:
      //   { prompt: "muzica trista", limit: 30 }  →  '{"prompt":"muzica trista","limit":30}'
      //
      // await = asteapta sa primim raspunsul inainte de a continua

      const response = await fetch('/api/generate-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt, limit: 30 }),
      })

      // response.json() parseaza raspunsul JSON de la server
      // (invers lui JSON.stringify: text JSON → obiect JavaScript)
      const data = await response.json()

      // Daca serverul a returnat un status de eroare (4xx, 5xx)
      if (!response.ok) {
        throw new Error(data.error || 'Ceva a mers prost...')
      }

      // ─── SUCCES: salvam datele in state ───
      setTracks(data.tracks || [])      // Lista de piese
      setTags(data.tags || [])          // Tag-urile extrase de Gemini
      
      // Fetch Spotify URIs pentru salvare
      if (data.tracks && data.tracks.length > 0) {
        const uris = {}
        Promise.allSettled(
          data.tracks.map(async (track, index) => {
            const res = await fetch(`/api/spotify-search?artist=${encodeURIComponent(track.artist)}&track=${encodeURIComponent(track.song)}`)
            if (res.ok) {
              const sData = await res.json()
              if (sData.uri) uris[index] = sData.uri
            }
          })
        ).then(() => setTrackUris(uris))
      }

    } catch (err) {
      // catch prinde orice eroare (network, server, etc.)
      // Echivalent Python: except Exception as err:
      setError(err.message)
    } finally {
      // finally ruleaza INTOTDEAUNA (si dupa success, si dupa eroare)
      // Oprim loading-ul indiferent de rezultat
      setLoading(false)
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
          name: `Prompt Playlist: ${prompt.substring(0, 30)}...`,
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

  // ═══════════════════════════════════════════════════════════════
  // RENDER (ce se afiseaza pe ecran)
  //
  // In React, HTML-ul se scrie direct in JavaScript (se numeste JSX).
  // E aproape identic cu HTML normal, cu cateva diferente:
  //   - class → className (class e cuvant rezervat in JS)
  //   - onclick → onClick (camelCase)
  //   - style={{color: 'red'}} (obiect JS, nu string CSS)
  //   - {variabila} = afiseaza valoarea unei variabile JS
  // ═══════════════════════════════════════════════════════════════

  return (
    <div>
      <h2 className="section-heading">
        <Sparkles size={18} /> Prompt Playlist Generator
      </h2>

      {/* ─── FORMULARUL DE INPUT ─── */}
      {/* 
        <form onSubmit={handleSubmit}> = cand apeai Enter sau butonul Submit,
        ruleaza functia handleSubmit. 
      */}
      <form onSubmit={handleSubmit} className="retro-card" style={{ marginBottom: '24px' }}>
        <label
          htmlFor="prompt-input"
          style={{
            display: 'block',
            marginBottom: '8px',
            fontFamily: 'var(--font-heading)',
            fontSize: '0.85rem'
          }}
        >
          ✿ Descrie ce muzica vrei:
        </label>

        {/* 
          Input-ul text:
          - value={prompt} = valoarea afisata vine din state
          - onChange={(e) => setPrompt(e.target.value)} = 
              de fiecare data cand tastezi o litera, actualizeaza state-ul "prompt"
              cu textul curent din input.
              e.target.value = textul actual din caseta de input
        */}
        <input
          id="prompt-input"
          className="input-field"
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="ex: sad rainy day music with acoustic guitar..."
          disabled={loading}
        />

        {/* Butonul de submit */}
        <button
          type="submit"
          className="btn-primary"
          disabled={loading || !prompt.trim()}
          style={{ marginTop: '12px' }}
        >
          {/* Conditional rendering:
              Daca loading e true → afiseaza Loader2 (rotita de incarcare)
              Daca loading e false → afiseaza Send (iconita de trimitere)
              
              Sintaxa: {conditie ? valoare_daca_true : valoare_daca_false}
              E echivalentul Python: valoare_daca_true if conditie else valoare_daca_false
          */}
          {loading ? (
            <>
              <Loader2 size={16} className="spin" />
              Se genereaza...
            </>
          ) : (
            <>
              <Send size={16} />
              Generate Playlist
            </>
          )}
        </button>
      </form>

      {/* ─── MESAJ DE EROARE ─── */}
      {/* 
        {error && <div>...</div>} = "short-circuit rendering"
        Daca error e un string gol (''), JavaScript il evalueaza ca false,
        deci <div>-ul NU se afiseaza.
        Daca error e 'Ceva a mers prost', il evalueaza ca true,
        deci <div>-ul SE afiseaza.
      */}
      {error && (
        <div className="retro-card" style={{ borderColor: '#e57373', marginBottom: '20px' }}>
          <p style={{ color: '#c62828' }}>✘ Eroare: {error}</p>
        </div>
      )}

      {/* ─── TAG-URILE EXTRASE DE GEMINI ─── */}
      {tags.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: '8px' }}>
            ✿ Tag-uri detectate de AI:
          </h3>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {/* 
              .map() itereaza prin array-ul "tags" si creeaza un <span> pt fiecare.
              
              Echivalent Python:
                for tag in tags:
                    print(f'<span>{tag}</span>')
              
              "key={tag}" = React are nevoie de un identificator unic pt fiecare 
              element dintr-o lista, ca sa stie ce s-a schimbat cand re-randeaza.
            */}
            {tags.map((tag) => (
              <span key={tag} className="badge badge-tag">{tag}</span>
            ))}
          </div>
        </div>
      )}

      {/* ─── LISTA DE PIESE ─── */}
      {tracks.length > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 className="section-heading" style={{ margin: 0 }}>
              <Music size={16} /> Playlist ({tracks.length} piese)
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
            {tracks.map((track, index) => (
              // Fiecare piesa e un rand cu: numar, artist, piesa, score, sursa
              <div key={index} className="track-row">
                {/* Numarul piesei */}
                <span style={{
                  fontFamily: 'var(--font-heading)',
                  fontSize: '0.75rem',
                  color: 'var(--text-muted)',
                  width: '28px',
                  textAlign: 'right'
                }}>
                  {index + 1}.
                </span>

                {/* Iconita de nota muzicala cu scor vizual */}
                <Star
                  size={14}
                  fill={track.score > 0.7 ? 'var(--accent-pink)' : 'none'}
                  color="var(--accent-pink)"
                />

                {/* Piesa si artist */}
                <div style={{ flex: 1 }}>
                  <span style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>
                    {track.song}
                  </span>
                  <span style={{ color: 'var(--text-muted)', margin: '0 6px' }}>—</span>
                  <span style={{ fontSize: '0.9rem' }}>{track.artist}</span>
                </div>

                {/* Scorul de match (cat de bine se potriveste) */}
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

                {/* Badge sursa: local (din DB-ul tau) sau discovery (piesa noua) */}
                <span className={`badge ${track.source === 'local' ? 'badge-local' : 'badge-discovery'}`}>
                  {track.source === 'local' ? '♡ local' : '✧ discovery'}
                </span>

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
            ))}
          </div>
        </div>
      )}

      {/* Mesaj cand nu exista inca rezultate si nu se incarca nimic */}
      {!loading && tracks.length === 0 && !error && (
        <div className="retro-card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          <Sparkles size={24} style={{ marginBottom: '8px' }} />
          <p>Scrie un prompt si apasa Generate pentru a descoperi muzica noua! ✿</p>
        </div>
      )}
    </div>
  )
}

export default PromptGenerator
