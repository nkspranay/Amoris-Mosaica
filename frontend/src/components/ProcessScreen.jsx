import { useEffect, useRef, useState } from 'react'
import styles from './ProcessScreen.module.css'
import { apiUrl, wsUrl } from '../config.js'

const STAGE_MESSAGES = {
  preprocess: 'Enhancing your image...',
  load_tiles: 'Loading tile dataset...',
  split:      'Splitting into grid...',
  match:      'Matching tiles by color...',
  assemble:   'Assembling your mosaic...',
}

const STAGE_ORDER = Object.keys(STAGE_MESSAGES)

const TILE_COLORS = [
  '#2d4a3e','#1a3a4a','#4a2d2d','#3a3a1a','#2d2d4a',
  '#4a3a2d','#1a4a3a','#3a1a4a','#4a4a2d','#2d3a4a',
  '#3e2d4a','#4a2d3e','#2d4a2d','#4a3e2d','#1a2d4a',
  '#c4841a','#8b5e3c','#4a6741','#3d5a7a','#7a3d5a',
]

export default function ProcessScreen({ config, onComplete, onError }) {
  const [stage,   setStage]   = useState('preprocess')
  const [percent, setPercent] = useState(0)
  const [etaMs,   setEtaMs]   = useState(null)
  const [tiles,   setTiles]   = useState([])
  const [error,   setError]   = useState('')

  const wsRef           = useRef(null)
  const pollRef         = useRef(null)
  const jobIdRef        = useRef(null)
  const startedRef      = useRef(false)
  const doneRef         = useRef(false)
  const isUnmountingRef = useRef(false)

  const GRID_COLS   = 24
  const GRID_ROWS   = 16
  const TOTAL_CELLS = GRID_COLS * GRID_ROWS

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    startGeneration()
    return () => {
      isUnmountingRef.current = true
      if (doneRef.current && wsRef.current) wsRef.current.close()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  useEffect(() => {
    const target = Math.floor((percent / 100) * TOTAL_CELLS)
    if (target > tiles.length) {
      setTiles(prev => {
        if (prev.length >= target) return prev
        const newTiles = [...prev]
        while (newTiles.length < target) {
          newTiles.push({
            id:    newTiles.length,
            color: TILE_COLORS[Math.floor(Math.random() * TILE_COLORS.length)],
            delay: Math.random() * 0.3,
          })
        }
        return newTiles
      })
    }
  }, [percent])

  async function startGeneration() {
    const { inputMode, file, prompt, datasetId, quality, sessionId } = config

    const ws = new WebSocket(wsUrl(`/ws/progress/${sessionId}`))
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'ping') return
      if (data.stage)               setStage(data.stage)
      if (data.percent !== undefined) setPercent(prev => Math.max(prev, data.percent))
      if (data.eta_ms)              setEtaMs(data.eta_ms)
      if (data.done && !doneRef.current) {
        doneRef.current = true
        fetchResult(jobIdRef.current)
      }
      if (data.error) {
        setError('Generation failed. Please try again.')
        setTimeout(onError, 2000)
      }
    }

    ws.onopen  = () => console.log('[ws] connected')
    ws.onclose = () => { if (!isUnmountingRef.current) console.log('[ws] closed') }
    ws.onerror = (err) => console.log('[ws] error', err)

    await new Promise((resolve) => {
      if (ws.readyState === WebSocket.OPEN) return resolve()
      ws.onopen = resolve
      setTimeout(resolve, 2000)
    })

    const formData = new FormData()
    formData.append('dataset_id', datasetId)
    formData.append('quality',    quality)
    formData.append('session_id', sessionId)

    let endpoint
    if (inputMode === 'upload') {
      formData.append('file', file)
      endpoint = '/api/generate'
    } else {
      formData.append('prompt', prompt)
      endpoint = '/api/generate-from-text'
    }

    try {
      const response = await fetch(apiUrl(endpoint), { method: 'POST', body: formData })
      const { job_id } = await response.json()
      jobIdRef.current = job_id
      startPolling(job_id)
    } catch {
      setError('Something went wrong.')
      setTimeout(onError, 2000)
    }
  }

  function startPolling(jobId) {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const r    = await fetch(apiUrl(`/api/status/${jobId}`))
        const data = await r.json()
        if (data.status === 'done' && !doneRef.current) {
          doneRef.current = true
          clearInterval(pollRef.current)
          fetchResult(jobId)
        }
        if (data.status === 'failed') {
          clearInterval(pollRef.current)
          setError(data.error || 'Generation failed.')
          setTimeout(onError, 2000)
        }
      } catch {}
    }, 5000)
  }

  async function fetchResult(jobId) {
    if (!jobId) return
    clearInterval(pollRef.current)
    try {
      const response = await fetch(apiUrl(`/api/result/${jobId}`))
      const blob     = await response.blob()
      const imageUrl = URL.createObjectURL(blob)
      setPercent(100)
      await new Promise(r => setTimeout(r, 600))
      onComplete({
        imageUrl,
        tileCount:    parseInt(response.headers.get('X-Tile-Count')    || '0'),
        processingMs: parseInt(response.headers.get('X-Processing-Ms') || '0'),
        gridWidth:    parseInt(response.headers.get('X-Grid-Width')    || '0'),
        gridHeight:   parseInt(response.headers.get('X-Grid-Height')   || '0'),
        datasetId: config.datasetId,
      })
    } catch {
      setError('Could not retrieve result.')
      setTimeout(onError, 2000)
    }
  }

  const etaSeconds = etaMs ? Math.ceil(etaMs / 1000) : null

  return (
    <div className={styles.screen}>
      <header className={styles.header}>
        <div className={styles.logo}>
            <img 
              src="/logo.png" 
              alt="Amoris Mosaica" 
              className={styles.logoImg}
            />
            <span>Amoris Mosaica</span>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.canvasWrapper}>
          <div className={styles.tileGrid} style={{
            gridTemplateColumns: `repeat(${GRID_COLS}, 1fr)`,
            gridTemplateRows:    `repeat(${GRID_ROWS}, 1fr)`,
          }}>
            {Array.from({ length: TOTAL_CELLS }).map((_, i) => {
              const tile = tiles[i]
              return (
                <div
                  key={i}
                  className={`${styles.tile} ${tile ? styles.tileVisible : ''}`}
                  style={tile ? { backgroundColor: tile.color, animationDelay: `${tile.delay}s` } : {}}
                />
              )
            })}
          </div>
          <div className={styles.canvasOverlay}>
            <div className={styles.percentDisplay}>
              <span className={styles.percentNum}>{percent}</span>
              <span className={styles.percentSym}>%</span>
            </div>
          </div>
        </div>

        <div className={styles.status}>
          <p className={styles.stageMsg}>
            {error || STAGE_MESSAGES[stage] || 'Working...'}
          </p>
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${percent}%` }} />
          </div>
          <div className={styles.stagePips}>
            {STAGE_ORDER.map(s => (
              <div key={s} className={`${styles.pip}
                ${stage === s ? styles.pipActive : ''}
                ${STAGE_ORDER.indexOf(s) < STAGE_ORDER.indexOf(stage) ? styles.pipDone : ''}`}>
                <span className={styles.pipDot} />
                <span className={styles.pipLabel}>{s}</span>
              </div>
            ))}
          </div>
          {etaSeconds && percent < 100 && (
            <p className={styles.eta}>~{etaSeconds}s remaining</p>
          )}
        </div>
      </main>
    </div>
  )
}