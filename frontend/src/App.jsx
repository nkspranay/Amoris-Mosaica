import { useState } from 'react'
import InputScreen   from './components/InputScreen.jsx'
import ProcessScreen from './components/ProcessScreen.jsx'
import ResultScreen  from './components/ResultScreen.jsx'

// App states: "input" → "processing" → "result"
export default function App() {
  const [screen, setScreen] = useState('input')
  const [jobConfig, setJobConfig] = useState(null)   // Passed from input → process
  const [result,    setResult]    = useState(null)   // Passed from process → result

  function handleSubmit(config) {
    setJobConfig(config)
    setScreen('processing')
  }

  function handleComplete(resultData) {
    setResult(resultData)
    setScreen('result')
  }

  function handleReset() {
    setJobConfig(null)
    setResult(null)
    setScreen('input')
  }

  return (
    <>
      {screen === 'input'      && <InputScreen   onSubmit={handleSubmit} />}
      {screen === 'processing' && <ProcessScreen config={jobConfig} onComplete={handleComplete} onError={handleReset} />}
      {screen === 'result'     && <ResultScreen  result={result} onReset={handleReset} />}
    </>
  )
}