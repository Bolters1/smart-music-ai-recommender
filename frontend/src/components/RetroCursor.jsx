import React, { useEffect } from 'react'

/**
 * RetroCursor.jsx — JavaScript Love Heart & Music Note Cursor (mf2fm web-design)
 * Floating music notes (♫, ♪) and hearts with pastel retro colors.
 * Notes spawn gently from the cursor, float upward slowly, grow slightly, then fade out.
 */
export default function RetroCursor() {
  useEffect(() => {
    const colours = ['#8e7dbe', '#2B345B', '#5e8597', '#ffffff', '#e07a97', '#ffccd5', '#88ab89']
    const minisize = 10
    const maxisize = 20
    const poolSize = 30
    const symbols = [String.fromCharCode(9835), '♪', '♫', '♡', '★']

    // Spawn throttle — don't spawn faster than every 80ms
    const SPAWN_COOLDOWN = 80
    // How far mouse must move before spawning a new note
    const MIN_MOVE_DIST = 8

    let mouseX = -100, mouseY = -100
    let lastSpawnX = -100, lastSpawnY = -100
    let lastSpawnTime = 0
    let animId = null

    const container = document.createElement('div')
    container.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:99999;overflow:hidden;'
    document.body.appendChild(container)

    // Pre-create a pool of note elements (all hidden initially)
    const pool = []
    for (let i = 0; i < poolSize; i++) {
      const div = document.createElement('div')
      div.style.cssText = 'position:absolute;pointer-events:none;user-select:none;visibility:hidden;font-family:monospace,sans-serif;will-change:transform,opacity;'
      div.style.textShadow = '0 0 4px rgba(0,0,0,0.25)'
      container.appendChild(div)
      pool.push({
        el: div,
        active: false,
        x: 0,
        y: 0,
        vx: 0,        // horizontal drift velocity
        vy: 0,        // upward velocity
        size: minisize,
        growRate: 0,
        opacity: 0,
        age: 0,
        maxAge: 0,
      })
    }

    const spawnNote = () => {
      // Find an inactive note in the pool
      for (let i = 0; i < poolSize; i++) {
        const n = pool[i]
        if (!n.active) {
          const sym = symbols[Math.floor(Math.random() * symbols.length)]
          const col = colours[Math.floor(Math.random() * colours.length)]
          n.el.textContent = sym
          n.el.style.color = col
          n.active = true
          n.x = mouseX + (Math.random() * 12 - 6)
          n.y = mouseY + (Math.random() * 8 - 4)
          n.vx = (Math.random() - 0.5) * 0.6   // gentle horizontal drift
          n.vy = -(0.5 + Math.random() * 1.0)   // float upward (slow)
          n.size = minisize + Math.random() * 3
          n.growRate = 0.02 + Math.random() * 0.03
          n.opacity = 0.9
          n.age = 0
          n.maxAge = 120 + Math.floor(Math.random() * 80) // ~2-3 seconds at 60fps
          n.el.style.fontSize = n.size + 'px'
          n.el.style.opacity = '0.9'
          n.el.style.visibility = 'visible'
          n.el.style.transform = `translate(${n.x}px, ${n.y}px)`
          return
        }
      }
    }

    const onMouseMove = (e) => {
      mouseX = e.clientX
      mouseY = e.clientY
    }

    // Click burst — spawn a few extra notes
    let clickInterval = null
    const onMouseDown = () => {
      for (let k = 0; k < 3; k++) spawnNote()
      clickInterval = setInterval(() => {
        for (let k = 0; k < 2; k++) spawnNote()
      }, 100)
    }
    const onMouseUp = () => {
      if (clickInterval) { clearInterval(clickInterval); clickInterval = null }
    }

    const animate = (now) => {
      // Maybe spawn a new note (throttled by distance + time)
      const dx = mouseX - lastSpawnX
      const dy = mouseY - lastSpawnY
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist > MIN_MOVE_DIST && now - lastSpawnTime > SPAWN_COOLDOWN) {
        spawnNote()
        lastSpawnX = mouseX
        lastSpawnY = mouseY
        lastSpawnTime = now
      }

      // Update all active notes
      for (let i = 0; i < poolSize; i++) {
        const n = pool[i]
        if (!n.active) continue

        n.age++
        n.x += n.vx
        n.y += n.vy

        // Grow slightly over time
        if (n.size < maxisize) {
          n.size += n.growRate
        }

        // Fade out in the last 40% of life
        const fadeStart = n.maxAge * 0.6
        if (n.age > fadeStart) {
          n.opacity = Math.max(0, 0.9 * (1 - (n.age - fadeStart) / (n.maxAge - fadeStart)))
        }

        // Die when age exceeded
        if (n.age >= n.maxAge || n.opacity <= 0) {
          n.active = false
          n.el.style.visibility = 'hidden'
          continue
        }

        n.el.style.transform = `translate(${n.x}px, ${n.y}px)`
        n.el.style.fontSize = n.size + 'px'
        n.el.style.opacity = String(n.opacity)
      }

      animId = requestAnimationFrame(animate)
    }
    animId = requestAnimationFrame(animate)

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mouseup', onMouseUp)

    return () => {
      cancelAnimationFrame(animId)
      if (clickInterval) clearInterval(clickInterval)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mouseup', onMouseUp)
      if (container.parentNode) container.parentNode.removeChild(container)
    }
  }, [])

  return null
}
