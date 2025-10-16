import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Thermometer, Lightbulb, Tv, Music, Power, PlayCircle, PauseCircle, SkipForward } from 'lucide-react'

const API_URL = window.location.origin

export default function Controls() {
  const [hvacStatus, setHvacStatus] = useState({})
  const [lightingStatus, setLightingStatus] = useState({})
  const [musicStatus, setMusicStatus] = useState({})
  
  useEffect(() => {
    fetchAllStatus()
    const interval = setInterval(fetchAllStatus, 10000)
    return () => clearInterval(interval)
  }, [])
  
  const fetchAllStatus = async () => {
    try {
      const [hvac, lighting, music] = await Promise.all([
        axios.get(`${API_URL}/api/hvac/status`).catch(() => ({ data: {} })),
        axios.get(`${API_URL}/api/lighting/status`).catch(() => ({ data: {} })),
        axios.get(`${API_URL}/api/music/status`).catch(() => ({ data: {} }))
      ])
      
      setHvacStatus(hvac.data)
      setLightingStatus(lighting.data)
      setMusicStatus(music.data)
    } catch (error) {
      console.error('Error fetching status:', error)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Smart Controls</h2>
        <button
          onClick={fetchAllStatus}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg"
        >
          Refresh All
        </button>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <HVACPanel status={hvacStatus} onUpdate={fetchAllStatus} />
        <LightingPanel status={lightingStatus} onUpdate={fetchAllStatus} />
        <MusicPanel status={musicStatus} onUpdate={fetchAllStatus} />
        <TVPanel onUpdate={fetchAllStatus} />
      </div>
    </div>
  )
}

function HVACPanel({ status, onUpdate }) {
  const [mode, setMode] = useState('OFF')
  const [setpoint, setSetpoint] = useState(70)
  const [autoMode, setAutoMode] = useState(true)
  
  useEffect(() => {
    if (status.mode) setMode(status.mode)
    if (status.cool_setpoint_f) setSetpoint(Math.round(status.cool_setpoint_f))
    if (typeof status.auto_mode === 'boolean') setAutoMode(status.auto_mode)
  }, [status])
  
  const handleModeChange = async (newMode) => {
    try {
      await axios.post(`${API_URL}/api/hvac/mode`, { mode: newMode })
      setMode(newMode)
      onUpdate()
    } catch (error) {
      console.error('Error setting mode:', error)
    }
  }
  
  const handleSetpointChange = async (delta) => {
    const newSetpoint = setpoint + delta
    try {
      await axios.post(`${API_URL}/api/hvac/temperature`, { 
        cool_f: newSetpoint,
        heat_f: newSetpoint - 2
      })
      setSetpoint(newSetpoint)
      onUpdate()
    } catch (error) {
      console.error('Error setting temperature:', error)
    }
  }
  
  const handleAutoToggle = async () => {
    try {
      await axios.post(`${API_URL}/api/hvac/auto`, { enabled: !autoMode })
      setAutoMode(!autoMode)
      onUpdate()
    } catch (error) {
      console.error('Error toggling auto mode:', error)
    }
  }
  
  return (
    <ControlPanel
      icon={<Thermometer className="w-6 h-6" />}
      title="HVAC Control"
      color="red"
      autoMode={autoMode}
      onAutoToggle={handleAutoToggle}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">Current</span>
          <span className="text-2xl font-bold">
            {status.current_temperature_f?.toFixed(1) || '-'}°F
          </span>
        </div>
        
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">Setpoint</span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleSetpointChange(-1)}
              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded"
              disabled={autoMode}
            >
              -
            </button>
            <span className="text-xl font-bold w-16 text-center">{setpoint}°F</span>
            <button
              onClick={() => handleSetpointChange(1)}
              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded"
              disabled={autoMode}
            >
              +
            </button>
          </div>
        </div>
        
        <div className="grid grid-cols-4 gap-2">
          {['OFF', 'HEAT', 'COOL', 'HEATCOOL'].map((m) => (
            <button
              key={m}
              onClick={() => handleModeChange(m)}
              disabled={autoMode}
              className={`py-2 rounded text-sm font-medium transition-colors ${
                mode === m
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              } ${autoMode ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {m}
            </button>
          ))}
        </div>
        
        <div className="text-sm text-gray-400">
          Status: <span className="text-white">{status.hvac_status || 'OFF'}</span>
        </div>
      </div>
    </ControlPanel>
  )
}

function LightingPanel({ status, onUpdate }) {
  const [brightness, setBrightness] = useState(50)
  const [autoMode, setAutoMode] = useState(true)
  
  useEffect(() => {
    if (typeof status.auto_mode === 'boolean') setAutoMode(status.auto_mode)
  }, [status])
  
  const handleBrightnessChange = async (value) => {
    setBrightness(value)
  }
  
  const handleBrightnessSet = async () => {
    try {
      await axios.post(`${API_URL}/api/lighting/brightness`, {
        light_id: 1,
        brightness_pct: brightness
      })
      onUpdate()
    } catch (error) {
      console.error('Error setting brightness:', error)
    }
  }
  
  const handleSceneChange = async (scene) => {
    try {
      await axios.post(`${API_URL}/api/lighting/scene`, { scene })
      onUpdate()
    } catch (error) {
      console.error('Error setting scene:', error)
    }
  }
  
  const handleAutoToggle = async () => {
    try {
      await axios.post(`${API_URL}/api/lighting/auto`, { enabled: !autoMode })
      setAutoMode(!autoMode)
      onUpdate()
    } catch (error) {
      console.error('Error toggling auto mode:', error)
    }
  }
  
  return (
    <ControlPanel
      icon={<Lightbulb className="w-6 h-6" />}
      title="Lighting Control"
      color="yellow"
      autoMode={autoMode}
      onAutoToggle={handleAutoToggle}
    >
      <div className="space-y-4">
        <div>
          <label className="text-sm text-gray-400 mb-2 block">Brightness: {brightness}%</label>
          <input
            type="range"
            min="0"
            max="100"
            value={brightness}
            onChange={(e) => handleBrightnessChange(parseInt(e.target.value))}
            onMouseUp={handleBrightnessSet}
            onTouchEnd={handleBrightnessSet}
            disabled={autoMode}
            className="w-full"
          />
        </div>
        
        <div className="grid grid-cols-2 gap-2">
          {['Energize', 'Relax', 'Reading', 'Evening'].map((scene) => (
            <button
              key={scene}
              onClick={() => handleSceneChange(scene.toLowerCase())}
              disabled={autoMode}
              className={`py-2 rounded text-sm font-medium bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors ${
                autoMode ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {scene}
            </button>
          ))}
        </div>
        
        <div className="text-sm text-gray-400">
          Lights: <span className="text-white">
            {Object.keys(status.lights || {}).length} connected
          </span>
        </div>
      </div>
    </ControlPanel>
  )
}

function MusicPanel({ status, onUpdate }) {
  const [volume, setVolume] = useState(50)
  const [autoMode, setAutoMode] = useState(true)
  
  useEffect(() => {
    if (status.volume_percent) setVolume(status.volume_percent)
    if (typeof status.auto_mode === 'boolean') setAutoMode(status.auto_mode)
  }, [status])
  
  const handlePlay = async () => {
    try {
      await axios.post(`${API_URL}/api/music/play`)
      onUpdate()
    } catch (error) {
      console.error('Error playing music:', error)
    }
  }
  
  const handlePause = async () => {
    try {
      await axios.post(`${API_URL}/api/music/pause`)
      onUpdate()
    } catch (error) {
      console.error('Error pausing music:', error)
    }
  }
  
  const handleNext = async () => {
    try {
      await axios.post(`${API_URL}/api/music/next`)
      onUpdate()
    } catch (error) {
      console.error('Error skipping track:', error)
    }
  }
  
  const handleVolumeSet = async () => {
    try {
      await axios.post(`${API_URL}/api/music/volume`, { volume })
      onUpdate()
    } catch (error) {
      console.error('Error setting volume:', error)
    }
  }
  
  const handleAutoToggle = async () => {
    try {
      await axios.post(`${API_URL}/api/music/auto`, { enabled: !autoMode })
      setAutoMode(!autoMode)
      onUpdate()
    } catch (error) {
      console.error('Error toggling auto mode:', error)
    }
  }
  
  return (
    <ControlPanel
      icon={<Music className="w-6 h-6" />}
      title="Music Control"
      color="green"
      autoMode={autoMode}
      onAutoToggle={handleAutoToggle}
    >
      <div className="space-y-4">
        <div className="bg-gray-900 rounded-lg p-3">
          <p className="font-medium truncate">{status.track || 'No track playing'}</p>
          <p className="text-sm text-gray-400 truncate">{status.artist || ''}</p>
        </div>
        
        <div className="flex items-center justify-center space-x-4">
          <button
            onClick={status.is_playing ? handlePause : handlePlay}
            disabled={autoMode}
            className={`p-3 bg-green-600 hover:bg-green-700 rounded-full transition-colors ${
              autoMode ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {status.is_playing ? <PauseCircle className="w-6 h-6" /> : <PlayCircle className="w-6 h-6" />}
          </button>
          <button
            onClick={handleNext}
            disabled={autoMode}
            className={`p-3 bg-gray-700 hover:bg-gray-600 rounded-full transition-colors ${
              autoMode ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <SkipForward className="w-6 h-6" />
          </button>
        </div>
        
        <div>
          <label className="text-sm text-gray-400 mb-2 block">Volume: {volume}%</label>
          <input
            type="range"
            min="0"
            max="100"
            value={volume}
            onChange={(e) => setVolume(parseInt(e.target.value))}
            onMouseUp={handleVolumeSet}
            onTouchEnd={handleVolumeSet}
            disabled={autoMode}
            className="w-full"
          />
        </div>
      </div>
    </ControlPanel>
  )
}

function TVPanel({ onUpdate }) {
  const [autoMode, setAutoMode] = useState(true)
  
  const handlePower = async (action) => {
    try {
      await axios.post(`${API_URL}/api/tv/power`, { action })
      onUpdate()
    } catch (error) {
      console.error('Error controlling TV:', error)
    }
  }
  
  return (
    <ControlPanel
      icon={<Tv className="w-6 h-6" />}
      title="TV Control"
      color="blue"
      autoMode={autoMode}
      onAutoToggle={() => setAutoMode(!autoMode)}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => handlePower('on')}
            disabled={autoMode}
            className={`py-3 bg-green-600 hover:bg-green-700 rounded-lg font-medium transition-colors ${
              autoMode ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <Power className="w-5 h-5 mx-auto" />
            <span className="text-sm">Power On</span>
          </button>
          <button
            onClick={() => handlePower('off')}
            disabled={autoMode}
            className={`py-3 bg-red-600 hover:bg-red-700 rounded-lg font-medium transition-colors ${
              autoMode ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <Power className="w-5 h-5 mx-auto" />
            <span className="text-sm">Power Off</span>
          </button>
        </div>
        
        <div className="text-sm text-gray-400 text-center">
          CEC-enabled devices will respond
        </div>
      </div>
    </ControlPanel>
  )
}

function ControlPanel({ icon, title, color, autoMode, onAutoToggle, children }) {
  const colorClasses = {
    red: 'text-red-500',
    yellow: 'text-yellow-500',
    green: 'text-green-500',
    blue: 'text-blue-500'
  }
  
  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className={colorClasses[color]}>{icon}</div>
          <h3 className="text-lg font-semibold">{title}</h3>
        </div>
        
        <button
          onClick={onAutoToggle}
          className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
            autoMode
              ? 'bg-green-600 text-white'
              : 'bg-gray-700 text-gray-300'
          }`}
        >
          {autoMode ? 'AUTO' : 'MANUAL'}
        </button>
      </div>
      
      {children}
    </div>
  )
}
