import { useState, useEffect } from 'react'
import styles from './ResultScreen.module.css'

export default function ResultScreen({ result, onReset }) {
  const [revealed, setRevealed] = useState(false)
  const { imageUrl, tileCount, processingMs, gridWidth, gridHeight, datasetId } = result

  useEffect(() => {
    const t = setTimeout(() => setRevealed(true), 100)
    return () => clearTimeout(t)
  }, [])

  function handleDownload() {
    const a = document.createElement('a')
    a.href = imageUrl
    a.download = `mosaic-${datasetId}-${Date.now()}.png`
    a.click()
  }

  const seconds   = (processingMs / 1000).toFixed(1)
  const totalTiles = (tileCount).toLocaleString()

  return (
    <div className={styles.screen}>
      <header className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoGrid}>▦</span>
          <span>Amoris Mosaica</span>
        </div>
        <button className={styles.newBtn} onClick={onReset}>
          ← Create Another
        </button>
      </header>

      <main className={styles.main}>
        {/* ── Mosaic Display ── */}
        <div className={`${styles.mosaicWrapper} ${revealed ? styles.mosaicRevealed : ''}`}>
          <img
            src={imageUrl}
            alt="Your mosaic"
            className={styles.mosaicImg}
          />
          <div className={styles.mosaicSheen} />
        </div>

        {/* ── Metadata + Actions ── */}
        <div className={`${styles.sidebar} ${revealed ? styles.sidebarRevealed : ''}`}>
          <div className={styles.sidebarInner}>
            <h1 className={styles.title}>
              Your mosaic<br />
              <em>is ready</em>
            </h1>

            <div className={styles.statsGrid}>
              <div className={styles.stat}>
                <span className={styles.statValue}>{totalTiles}</span>
                <span className={styles.statLabel}>tiles placed</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statValue}>{gridWidth}×{gridHeight}</span>
                <span className={styles.statLabel}>grid size</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statValue}>{seconds}s</span>
                <span className={styles.statLabel}>generated in</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statValue}>{datasetId}</span>
                <span className={styles.statLabel}>dataset used</span>
              </div>
            </div>

            <button className={styles.downloadBtn} onClick={handleDownload}>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M9 2v10M5 8l4 4 4-4M3 14h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Download PNG
            </button>

            <button className={styles.resetBtn} onClick={onReset}>
              Create a new mosaic
            </button>

            <div className={styles.shareHint}>
              <p>Share your mosaic</p>
              <p className={styles.shareSubtext}>
                High-resolution PNG — perfect for printing or sharing
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}