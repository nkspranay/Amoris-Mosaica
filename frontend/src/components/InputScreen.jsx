import { useState, useEffect, useRef } from 'react'
import styles from './InputScreen.module.css'
import { apiUrl } from '../config.js'

const QUALITY_LABELS = {
  1: { label: 'Draft',  desc: 'Fast preview' },
  2: { label: 'Fine',   desc: 'Balanced quality' },
  3: { label: 'Master', desc: 'Maximum detail' },
}

export default function InputScreen({ onSubmit }) {
  const [datasets,    setDatasets]    = useState([])
  const [inputMode,   setInputMode]   = useState('upload')
  const [file,        setFile]        = useState(null)
  const [preview,     setPreview]     = useState(null)
  const [prompt,      setPrompt]      = useState('')
  const [datasetId,   setDatasetId]   = useState('nature')
  const [quality,     setQuality]     = useState(2)
  const [dragging,    setDragging]    = useState(false)
  const [error,       setError]       = useState('')
  const fileInputRef = useRef()

  useEffect(() => {
    fetch(apiUrl('/api/datasets'))
      .then(r => r.json())
      .then(data => {
        setDatasets(data)
        if (data.length > 0) setDatasetId(data[0].id)
      })
      .catch(() => setError('Could not load datasets. Is the server running?'))
  }, [])

  function handleFile(f) {
    if (!f) return
    if (!f.type.startsWith('image/')) {
      setError('Please upload an image file.')
      return
    }
    setError('')
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  function handleSubmit() {
    setError('')
    if (inputMode === 'upload' && !file) {
      setError('Please upload a target image.')
      return
    }
    if (inputMode === 'prompt' && !prompt.trim()) {
      setError('Please enter a text prompt.')
      return
    }
    const sessionId = crypto.randomUUID()
    onSubmit({ inputMode, file, prompt, datasetId, quality, sessionId })
  }

  return (
    <div className={styles.screen}>
      <header className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoGrid}>▦</span>
          <span>Amoris Mosaica</span>
        </div>
        <p className={styles.tagline}>"Built from fragments. Made with love."</p>
      </header>

      <main className={styles.main}>
        <section className={styles.inputZone}>
          <div className={styles.modeToggle}>
            <button
              className={`${styles.modeBtn} ${inputMode === 'upload' ? styles.modeBtnActive : ''}`}
              onClick={() => setInputMode('upload')}
            >
              Upload Image
            </button>
            <button
              className={`${styles.modeBtn} ${inputMode === 'prompt' ? styles.modeBtnActive : ''}`}
              onClick={() => setInputMode('prompt')}
            >
              Text Prompt
            </button>
          </div>

          {inputMode === 'upload' ? (
            <div
              className={`${styles.dropZone} ${dragging ? styles.dropZoneDragging : ''} ${preview ? styles.dropZoneHasFile : ''}`}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={e => handleFile(e.target.files[0])}
              />
              {preview ? (
                <div className={styles.previewWrapper}>
                  <img src={preview} alt="Preview" className={styles.previewImg} />
                  <div className={styles.previewOverlay}>
                    <span>Click to change</span>
                  </div>
                </div>
              ) : (
                <div className={styles.dropPlaceholder}>
                  <div className={styles.dropIcon}>
                    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                      <rect x="4" y="4" width="14" height="14" rx="2" fill="currentColor" opacity="0.3"/>
                      <rect x="22" y="4" width="14" height="14" rx="2" fill="currentColor" opacity="0.6"/>
                      <rect x="4" y="22" width="14" height="14" rx="2" fill="currentColor" opacity="0.6"/>
                      <rect x="22" y="22" width="14" height="14" rx="2" fill="currentColor" opacity="1"/>
                    </svg>
                  </div>
                  <p className={styles.dropText}>Drop your image here</p>
                  <p className={styles.dropSubtext}>or click to browse — JPG, PNG, WEBP up to 50MB</p>
                </div>
              )}
            </div>
          ) : (
            <div className={styles.promptZone}>
              <div className={styles.promptWrapper}>
                <input
                  className={styles.promptInput}
                  type="text"
                  placeholder="e.g. Mount Fuji at dawn, Starry night sky, The Eiffel Tower..."
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                />
                <span className={styles.promptIcon}>⌕</span>
              </div>
              <p className={styles.promptHint}>
                We'll find the perfect image for your prompt automatically
              </p>
            </div>
          )}

          {error && <p className={styles.error}>{error}</p>}

          <button
            className={styles.generateBtn}
            onClick={handleSubmit}
            disabled={datasets.length === 0}
          >
            <span>Generate Mosaic</span>
            <span className={styles.generateArrow}>→</span>
          </button>
        </section>

        <section className={styles.optionsZone}>
          <div className={styles.optionGroup}>
            <h3 className={styles.optionLabel}>Tile Dataset</h3>
            <div className={styles.datasetGrid}>
              {datasets.map(ds => (
                <button
                  key={ds.id}
                  className={`${styles.datasetCard} ${datasetId === ds.id ? styles.datasetCardActive : ''}`}
                  onClick={() => setDatasetId(ds.id)}
                >
                  <span className={styles.datasetIcon}>{datasetEmoji(ds.id)}</span>
                  <span className={styles.datasetName}>{ds.name}</span>
                  <span className={styles.datasetCount}>{ds.tile_count.toLocaleString()} tiles</span>
                  <span className={`${styles.datasetBadge} ${styles[`badge_${ds.quality}`]}`}>
                    {ds.quality}
                  </span>
                </button>
              ))}
              <button
                className={`${styles.datasetCard} ${styles.datasetCardCustom} ${datasetId === 'custom' ? styles.datasetCardActive : ''}`}
                onClick={() => setDatasetId('custom')}
              >
                <span className={styles.datasetIcon}>📁</span>
                <span className={styles.datasetName}>Custom</span>
                <span className={styles.datasetCount}>Your images</span>
              </button>
            </div>
          </div>

          <div className={styles.optionGroup}>
            <h3 className={styles.optionLabel}>
              Quality — <span className={styles.amber}>{QUALITY_LABELS[quality].label}</span>
            </h3>
            <p className={styles.optionDesc}>{QUALITY_LABELS[quality].desc}</p>
            <div className={styles.sliderTrack}>
              {[1, 2, 3].map(q => (
                <button
                  key={q}
                  className={`${styles.sliderStop} ${quality === q ? styles.sliderStopActive : ''}`}
                  onClick={() => setQuality(q)}
                >
                  <span className={styles.sliderDot} />
                  <span className={styles.sliderStopLabel}>{QUALITY_LABELS[q].label}</span>
                </button>
              ))}
              <div
                className={styles.sliderFill}
                style={{ width: `${((quality - 1) / 2) * 100}%` }}
              />
            </div>
          </div>

          <div className={styles.infoBox}>
            <p className={styles.infoTitle}>How it works</p>
            <ol className={styles.infoList}>
              <li>Your image is split into a grid of tiny cells</li>
              <li>Each cell is matched to the closest tile by color</li>
              <li>Thousands of photos are assembled into your mosaic</li>
            </ol>
          </div>
        </section>
      </main>
    </div>
  )
}

function datasetEmoji(id) {
  return { nature: '🌿', artworks: '🎨', space: '🌌' }[id] || '📁'
}