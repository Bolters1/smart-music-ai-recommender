import { useState } from 'react'
import {
  Home,
  Sparkles,
  Search,
  CalendarHeart,
  BarChart3,
  Music,
  Heart,
  Star,
} from 'lucide-react'

import PromptGenerator from './components/PromptGenerator'
import SongPredictor from './components/SongPredictor'
import WeeklyDiscover from './components/WeeklyDiscover'
import StatsPage from './components/StatsPage'
import HomePage from './components/HomePage'
import MusicPlayer from './components/MusicPlayer'
import RecommendPage from './components/RecommendPage'
import RetroCursor from './components/RetroCursor'
import RetroSnowBackground from './components/RetroSnowBackground'

import './App.css'

const TABS = [
  { id: 'home',      label: 'home',       icon: Home,          emoji: '★' },
  { id: 'prompt',    label: 'prompt',     icon: Sparkles,      emoji: '♪' },
  { id: 'predict',   label: 'predict',    icon: Search,        emoji: '♫' },
  { id: 'recommend', label: 'recommend',  icon: Star,          emoji: '✧' },
  { id: 'weekly',    label: 'weekly',     icon: CalendarHeart, emoji: '☆' },
  { id: 'stats',     label: 'stats',      icon: BarChart3,     emoji: '❤' },
]

function App() {
  const [activeTab, setActiveTab] = useState('home')

  return (
    <>
      {/* ─── RETRO BACKGROUND SNOW & STARS (mf2fm with Snowplow) ─── */}
      <RetroSnowBackground />

      <div className="wrapper">
        {/* ─── RETRO CURSOR EFFECT (Music Notes & Hearts) ─── */}
        <RetroCursor />
      
      {/* ─── HEADER ─── */}
      <div className="header">
        {/* Straturile de fundal ale ferestrei (imagini retro) */}
        <div className="outside"></div>
        <div className="window-frame">
          <div className="window-left"></div>
          <div className="window-right"></div>
          <div className="window-draggable-area"></div>
        </div>
        
        {/* Continutul header-ului */}
        <div className="header-content">
          <div className="site-title">
            <a href="#" onClick={(e) => { e.preventDefault(); setActiveTab('home'); }}>
              ✿ smart music ai ✿
            </a>
          </div>
          <div className="site-subtitle">powered by machine learning & last.fm</div>
          
          <div className="menu">
            <ul>
              {TABS.map(tab => (
                <li key={tab.id}>
                  <a 
                    href="#" 
                    className={activeTab === tab.id ? 'active' : ''}
                    onClick={(e) => { e.preventDefault(); setActiveTab(tab.id); }}
                  >
                    {tab.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* ─── MAIN AREA ─── */}
      <div className="main">
        {/* Continut principal (stanga) - Toate tab-urile sunt montate dar 
             doar cel activ e vizibil. Asta pastreaza starea (rezultate, inputuri) 
             cand schimbi intre tab-uri. */}
        <div className="content">
          <div style={{ display: activeTab === 'home' ? 'block' : 'none' }}>
            <HomePage onNavigate={setActiveTab} />
          </div>
          <div style={{ display: activeTab === 'prompt' ? 'block' : 'none' }}>
            <PromptGenerator />
          </div>
          <div style={{ display: activeTab === 'predict' ? 'block' : 'none' }}>
            <SongPredictor />
          </div>
          <div style={{ display: activeTab === 'recommend' ? 'block' : 'none' }}>
            <RecommendPage />
          </div>
          <div style={{ display: activeTab === 'weekly' ? 'block' : 'none' }}>
            <WeeklyDiscover />
          </div>
          <div style={{ display: activeTab === 'stats' ? 'block' : 'none' }}>
            <StatsPage />
          </div>
        </div>
        
        {/* Sidebar (dreapta) */}
        <div className="sidebar">
          <MusicPlayer />
          
          <div style={{ marginTop: '24px', textAlign: 'center', opacity: 0.8 }}>
            <p>
              <Heart size={10} fill="currentColor" />
              {' '}made with love{' '}
              <Heart size={10} fill="currentColor" />
            </p>
            <p style={{ marginTop: '4px' }}>
              layout design inspired by teppyslayouts
            </p>
            <img src="/img/gif.gif" alt="decorative gif" style={{ marginTop: '16px', maxWidth: '100%' }} />
          </div>
        </div>
      </div>
    </div>
    </>
  )
}

export default App
