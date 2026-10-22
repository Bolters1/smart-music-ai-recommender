import React, { useEffect } from 'react'

/**
 * RetroSnowBackground.jsx — Winter Snow Flakes Effect with Snowplow
 * Falling retro snowflakes & stars accumulate at the bottom.
 * When enough pile up, a cute pixel-art snowplow drives across and sweeps them away!
 */

function createPlowImage() {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 32
  const ctx = canvas.getContext('2d')

  // Plow blade (front)
  ctx.fillStyle = '#FFD700'
  ctx.beginPath()
  ctx.moveTo(0, 28)
  ctx.lineTo(8, 12)
  ctx.lineTo(14, 12)
  ctx.lineTo(14, 28)
  ctx.closePath()
  ctx.fill()
  ctx.strokeStyle = '#B8860B'
  ctx.lineWidth = 1.5
  ctx.stroke()

  // Truck body
  ctx.fillStyle = '#E74C3C'
  ctx.fillRect(14, 10, 30, 18)
  ctx.strokeStyle = '#922B21'
  ctx.strokeRect(14, 10, 30, 18)

  // Cabin window
  ctx.fillStyle = '#AED6F1'
  ctx.fillRect(18, 13, 10, 8)
  ctx.strokeStyle = '#5DADE2'
  ctx.lineWidth = 1
  ctx.strokeRect(18, 13, 10, 8)

  // Cabin roof
  ctx.fillStyle = '#C0392B'
  ctx.fillRect(16, 8, 16, 4)

  // Exhaust pipe
  ctx.fillStyle = '#555'
  ctx.fillRect(38, 4, 3, 8)

  // Smoke puffs
  ctx.fillStyle = 'rgba(200,200,200,0.6)'
  ctx.beginPath()
  ctx.arc(40, 3, 3, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(43, 1, 2.5, 0, Math.PI * 2)
  ctx.fill()

  // Rear flatbed
  ctx.fillStyle = '#E74C3C'
  ctx.fillRect(44, 14, 14, 14)
  ctx.strokeStyle = '#922B21'
  ctx.strokeRect(44, 14, 14, 14)

  // Snow in the back
  ctx.fillStyle = '#fff'
  ctx.beginPath()
  ctx.moveTo(45, 15)
  ctx.quadraticCurveTo(51, 8, 57, 15)
  ctx.closePath()
  ctx.fill()

  // Wheels
  ctx.fillStyle = '#2C3E50'
  ctx.beginPath()
  ctx.arc(22, 30, 4, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(50, 30, 4, 0, Math.PI * 2)
  ctx.fill()

  // Wheel hubcaps
  ctx.fillStyle = '#95A5A6'
  ctx.beginPath()
  ctx.arc(22, 30, 1.5, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(50, 30, 1.5, 0, Math.PI * 2)
  ctx.fill()

  return canvas.toDataURL('image/png')
}

export default function RetroSnowBackground() {
  useEffect(() => {
    const speed = 45
    const maxFlakes = 30
    const sizes = 28
    const colours = ['#ffffff', '#c5e3f6', '#9bc4db', '#d8eefc', '#b1d4e0', '#e8d5ef', '#f0e0f4']

    const snowChars = [
      String.fromCharCode(10047), String.fromCharCode(10030),
      String.fromCharCode(10025), String.fromCharCode(9885),
      String.fromCharCode(8902),  String.fromCharCode(10022),
      String.fromCharCode(11089), String.fromCharCode(10023),
      String.fromCharCode(11090),
    ]

    let swide = window.innerWidth || 800
    let shigh = window.innerHeight || 600
    let deeex = 0
    let hasFocus = true
    let intervalId = null
    let landedCount = 0

    // Container
    const boddie = document.createElement('div')
    boddie.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;overflow:hidden;background:transparent;pointer-events:none;z-index:0;'
    document.body.insertBefore(boddie, document.body.firstChild)

    // Snowplow element (generated via canvas — no external image!)
    const plow = document.createElement('img')
    plow.src = createPlowImage()
    plow.style.cssText = 'position:absolute;bottom:0px;left:-80px;z-index:9999;pointer-events:none;image-rendering:pixelated;width:64px;height:32px;'
    boddie.appendChild(plow)

    let plowing = false
    let plowX = -80
    let plowAnimId = null

    const flakesArr = []

    const createFlake = (startY) => {
      const el = document.createElement('div')
      const charIdx = Math.floor(Math.random() * snowChars.length)
      const colIdx = Math.floor(Math.random() * colours.length)
      const fontSize = Math.floor(sizes * (0.25 + 0.75 * Math.random()))

      el.textContent = snowChars[charIdx]
      el.style.cssText = `position:absolute;pointer-events:none;user-select:none;font-family:monospace,sans-serif;color:${colours[colIdx]};font-size:${fontSize}px;line-height:${fontSize}px;opacity:0.8;will-change:transform,opacity;`
      el.style.textShadow = `0 0 3px rgba(0,0,0,0.3), 0 0 6px ${colours[colIdx]}`
      boddie.appendChild(el)

      return {
        el,
        x: Math.random() * swide,
        y: startY - fontSize,
        dx: Math.random(),
        dy: 0.4 + Math.random() * 1.5,
        am: 6 + Math.random() * sizes * 0.5,
        fs: fontSize,
        state: 'falling',
        opacity: 0.8,
      }
    }

    for (let i = 0; i < maxFlakes; i++) {
      flakesArr.push(createFlake(Math.random() * shigh * 0.75))
    }

    const resetFlake = (f) => {
      f.x = Math.random() * swide
      f.y = -f.fs
      f.dx = Math.random()
      f.dy = 0.4 + Math.random() * 1.5
      f.state = 'falling'
      f.opacity = 0.8
      f.el.style.opacity = '0.8'
      f.el.style.visibility = 'visible'
    }

    // ─── SNOWPLOW ANIMATION ───
    const startPlow = () => {
      if (plowing) return
      plowing = true
      plowX = swide + 10 // start from right side
      plow.style.transform = 'scaleX(-1)' // face left (driving left)
      plow.style.left = plowX + 'px'
      plow.style.visibility = 'visible'

      const drivePlow = () => {
        plowX -= 4 // drive across screen

        // Push/clear any landed flakes in the plow's path
        for (let i = 0; i < flakesArr.length; i++) {
          const f = flakesArr[i]
          if (f.state === 'landed') {
            const flakeRight = f.x + f.am * Math.sin(f.dx)
            // If the flake is near the plow's position, push it
            if (flakeRight < plowX + 70 && flakeRight > plowX - 10) {
              f.x -= 6
              f.el.style.transform = `translate(${f.x + f.am * Math.sin(f.dx)}px, ${f.y}px)`
              // If pushed off screen, reset
              if (f.x < -f.fs * 2) {
                landedCount--
                resetFlake(f)
              }
            }
          }
        }

        plow.style.left = plowX + 'px'

        if (plowX < -80) {
          // Plow has exited left side
          plowing = false
          plow.style.visibility = 'hidden'
          landedCount = 0
          // Reset any remaining landed flakes
          for (let i = 0; i < flakesArr.length; i++) {
            if (flakesArr[i].state === 'landed') {
              resetFlake(flakesArr[i])
            }
          }
        } else {
          plowAnimId = requestAnimationFrame(drivePlow)
        }
      }
      plowAnimId = requestAnimationFrame(drivePlow)
    }

    // ─── MAIN UPDATE LOOP ───
    const updateFlakes = () => {
      for (let i = 0; i < flakesArr.length; i++) {
        const f = flakesArr[i]

        if (f.state === 'falling') {
          f.y += f.dy
          f.dx += 0.015 + Math.random() / 40
          f.x += deeex * 0.3

          if (f.x > swide + f.fs || f.x < -f.fs * 2) {
            resetFlake(f)
            continue
          }

          const displayX = f.x + f.am * Math.sin(f.dx)

          if (f.y >= shigh - f.fs * 0.8) {
            f.state = 'landed'
            f.y = shigh - f.fs * 0.8
            landedCount++
          }

          f.el.style.transform = `translate(${displayX}px, ${f.y}px)`
        }
      }

      // Trigger the plow when enough snow has accumulated!
      if (landedCount >= maxFlakes * 0.6 && !plowing) {
        startPlow()
      }
    }

    const onMouseMove = (e) => {
      const mouseX = e.clientX || e.pageX || 0
      deeex = hasFocus ? (-1 + (2.5 * mouseX) / swide) : 0
    }
    const onResize = () => { swide = window.innerWidth || 800; shigh = window.innerHeight || 600 }
    const onFocus = () => { hasFocus = true }
    const onBlur = () => { hasFocus = false; deeex = 0 }

    intervalId = setInterval(updateFlakes, speed)

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('resize', onResize)
    window.addEventListener('focus', onFocus)
    window.addEventListener('blur', onBlur)

    return () => {
      if (intervalId) clearInterval(intervalId)
      if (plowAnimId) cancelAnimationFrame(plowAnimId)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('blur', onBlur)
      for (const f of flakesArr) {
        if (f.el.parentNode) f.el.parentNode.removeChild(f.el)
      }
      if (boddie.parentNode) boddie.parentNode.removeChild(boddie)
    }
  }, [])

  return null
}
