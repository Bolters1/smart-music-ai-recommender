/**
 * HomePage.jsx — Pagina de start (Home)
 * 
 * Ce face:
 * - Ofera o introducere simpatica in aplicatie.
 * - Explica ce e fiecare functionalitate (tab).
 * - Are butoane care te duc direct la acele tab-uri
 *   folosind functia `onNavigate` primita ca "prop" (parametru) din App.jsx.
 */

import React from 'react'
import { Sparkles, Search, CalendarHeart, BarChart3, Star } from 'lucide-react'

// "props" sunt parametrii pe care componenta parinte (App) ii da componentei copil (HomePage).
// Aici primim functia "onNavigate", pe care o apelam ca onNavigate('prompt') cand dam click pe un buton.
function HomePage({ onNavigate }) {
  return (
    <div className="home-container">
      {/* Titlul paginii */}
      <h2 className="section-heading">★ Welcome to your ML Music Assistant ★</h2>
      
      <p style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
        Aici poti descoperi muzica noua bazata pe istoricul tau de ascultare 
        sau poti vedea ce crede modelul meu ML (Machine Learning) despre piesele tale preferate!
      </p>

      {/* Grid cu carduri pentru fiecare sectiune */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', // Cardurile se aseaza automat in randuri si coloane
        gap: '20px'
      }}>
        
        {/* Card: Prompt Generator */}
        <div className="retro-card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <Sparkles size={18} color="var(--accent-pink)" />
            Prompt Generator
          </h3>
          <p style={{ fontSize: '0.9rem', marginBottom: '16px', color: 'var(--text-secondary)' }}>
            Scrie un text (ex: "muzica de ploaie cu chitara") si AI-ul iti va genera 
            un playlist personalizat folosind gusturile tale si recomandari noi.
          </p>
          {/* Cand dam click, spunem parintelui App.jsx sa schimbe tab-ul activ la 'prompt' */}
          <button className="btn-secondary" onClick={() => onNavigate('prompt')}>
            Go to Generator {'>>'}
          </button>
        </div>

        {/* Card: Song Predictor */}
        <div className="retro-card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <Search size={18} color="var(--accent-lavender)" />
            Song Predictor
          </h3>
          <p style={{ fontSize: '0.9rem', marginBottom: '16px', color: 'var(--text-secondary)' }}>
            Cauta o piesa anume si modelul ML iti va spune daca o sa iti placa sau nu, 
            bazat pe istoricul tau de pe Last.fm.
          </p>
          <button className="btn-secondary" onClick={() => onNavigate('predict')}>
            Go to Predictor {'>>'}
          </button>
        </div>

        {/* Card: Song Recommendations */}
        <div className="retro-card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <Star size={18} color="var(--accent-light)" />
            Song Recommendations
          </h3>
          <p style={{ fontSize: '0.9rem', marginBottom: '16px', color: 'var(--text-secondary)' }}>
            Primesti 5 recomandari personalizate de piese noi, alese si scorte de modelul ML 
            pe baza gusturilor tale muzicale.
          </p>
          <button className="btn-secondary" onClick={() => onNavigate('recommend')}>
            Go to Recommendations {'>>'}
          </button>
        </div>

        {/* Card: Weekly Discover */}
        <div className="retro-card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <CalendarHeart size={18} color="var(--accent-mint)" />
            Weekly Discover
          </h3>
          <p style={{ fontSize: '0.9rem', marginBottom: '16px', color: 'var(--text-secondary)' }}>
            Genereaza-ti doza saptamanala de muzica! Un mix perfect intre ancore (piese cunoscute)
            si descoperiri muzicale.
          </p>
          <button className="btn-secondary" onClick={() => onNavigate('weekly')}>
            Go to Weekly {'>>'}
          </button>
        </div>

        {/* Card: Stats */}
        <div className="retro-card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <BarChart3 size={18} color="var(--accent-peach)" />
            Database Stats
          </h3>
          <p style={{ fontSize: '0.9rem', marginBottom: '16px', color: 'var(--text-secondary)' }}>
            Vezi cate piese a procesat modelul, cate iti plac si care sunt 
            tag-urile tale muzicale cele mai ascultate.
          </p>
          <button className="btn-secondary" onClick={() => onNavigate('stats')}>
            Go to Stats {'>>'}
          </button>
        </div>

      </div>
      
      {/* Un mic divider retro */}
      <hr className="retro-divider" />
      <div style={{ textAlign: 'center' }}>
        <span className="blink">✧･ﾟ: *✧･ﾟ:*</span> Have fun! <span className="blink">*:･ﾟ✧*:･ﾟ✧</span>
      </div>
    </div>
  )
}

export default HomePage
