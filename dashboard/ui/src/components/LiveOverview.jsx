import React, { useEffect, useState } from 'react'
import { Users, Music, Volume2, Thermometer, Droplet, Sun, Cloud } from 'lucide-react'

export default function LiveOverview({ sensorData }) {
  const [snapshotUrl, setSnapshotUrl] = useState('')
  useEffect(() => {
    const makeUrl = () => `/api/camera/snapshot?ts=${Date.now()}`
    setSnapshotUrl(makeUrl())
    const interval = setInterval(() => setSnapshotUrl(makeUrl()), 3000)
    return () => clearInterval(interval)
  }, [])
  const {
    occupancy = 0,
    entries = 0,
    exits = 0,
    temperature_f = 0,
    humidity = 0,
    light_level = 0,
    noise_db = 0,
    current_song = {}
  } = sensorData

  

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Live Overview</h2>
      
      {/* Main Metrics + Live Camera */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <MetricCard
          icon={<Users className="w-8 h-8" />}
          title="Occupancy"
          value={occupancy}
          unit="people"
          color="blue"
        />
        <MetricCard
          icon={<Users className="w-8 h-8" />}
          title="Entries"
          value={entries}
          unit="people"
          color="green"
        />
        <MetricCard
          icon={<Users className="w-8 h-8" />}
          title="Exits"
          value={exits}
          unit="people"
          color="red"
        />
        
        <MetricCard
          icon={<Thermometer className="w-8 h-8" />}
          title="Temperature"
          value={temperature_f?.toFixed(1) || '-'}
          unit="°F"
          color="red"
        />
        
        <MetricCard
          icon={<Droplet className="w-8 h-8" />}
          title="Humidity"
          value={humidity?.toFixed(1) || '-'}
          unit="%"
          color="blue"
        />
        
        <MetricCard
          icon={<Sun className="w-8 h-8" />}
          title="Light Level"
          value={light_level?.toFixed(0) || '-'}
          unit="lux"
          color="yellow"
        />
        
        <MetricCard
          icon={<Volume2 className="w-8 h-8" />}
          title="Noise Level"
          value={noise_db?.toFixed(1) || '-'}
          unit="dB"
          color="purple"
        />
        
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <Music className="w-8 h-8 text-green-500" />
            <h3 className="text-lg font-semibold">Now Playing</h3>
          </div>
          <div className="space-y-1">
            <p className="font-medium">{current_song?.title || 'No song detected'}</p>
            <p className="text-sm text-gray-400">{current_song?.artist || ''}</p>
          </div>
        </div>

        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3">Live Camera</h3>
          <div className="aspect-video w-full bg-black/40 rounded-lg overflow-hidden flex items-center justify-center">
            {snapshotUrl ? (
              <img
                src={snapshotUrl}
                alt="Live camera"
                className="w-full h-full object-cover"
                onError={(e) => { e.currentTarget.style.display = 'none' }}
                onLoad={(e) => { e.currentTarget.style.display = 'block' }}
              />
            ) : (
              <span className="text-gray-400 text-sm">No camera snapshot available</span>
            )}
          </div>
        </div>
      </div>

      {/* Comfort Index */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4">Comfort Index</h3>
        <ComfortMeter 
          temperature={temperature_f}
          humidity={humidity}
          noise={noise_db}
          light={light_level}
        />
      </div>

      {/* Live Meters */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Noise Meter</h3>
          <NoiseMeter db={noise_db} />
        </div>

        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Light Meter</h3>
          <LuxMeter lux={light_level} />
        </div>
      </div>
    </div>
  )
}

function MetricCard({ icon, title, value, unit, color }) {
  const colorClasses = {
    blue: 'text-blue-500',
    red: 'text-red-500',
    yellow: 'text-yellow-500',
    green: 'text-green-500',
    purple: 'text-purple-500'
  }

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <div className="flex items-center space-x-3 mb-4">
        <div className={colorClasses[color]}>{icon}</div>
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      <div className="text-3xl font-bold">
        {value} <span className="text-xl text-gray-400">{unit}</span>
      </div>
    </div>
  )
}

function NoiseMeter({ db }) {
  const minDb = 0
  const maxDb = 100 // UI scale; calculation clamps internally
  const value = Math.max(minDb, Math.min(maxDb, Number(db || 0)))
  const pct = Math.round((value / maxDb) * 100)

  const getColor = (v) => {
    if (v < 50) return 'bg-green-500'
    if (v < 70) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl font-bold">{value.toFixed(1)} dB</span>
        <span className="text-gray-400">0 – {maxDb} dB</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-4">
        <div
          className={`h-4 rounded-full transition-all duration-500 ${getColor(value)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-2">
        <span>Quiet</span>
        <span>Conversation</span>
        <span>Loud</span>
      </div>
    </div>
  )
}

function LuxMeter({ lux }) {
  const minLux = 0
  const maxLux = 1000 // UI scale
  const value = Math.max(minLux, Math.min(maxLux, Number(lux || 0)))
  const pct = Math.round((value / maxLux) * 100)

  const getColor = (v) => {
    if (v < 150) return 'bg-blue-500'
    if (v < 500) return 'bg-green-500'
    return 'bg-yellow-500'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl font-bold">{value.toFixed(0)} lux</span>
        <span className="text-gray-400">0 – {maxLux} lux</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-4">
        <div
          className={`h-4 rounded-full transition-all duration-500 ${getColor(value)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-2">
        <span>Dark</span>
        <span>Moderate</span>
        <span>Bright</span>
      </div>
    </div>
  )
}

function ComfortMeter({ temperature, humidity, noise, light }) {
  // Simple comfort score calculation (0-100)
  let score = 50 // Base score
  
  // Temperature (68-72°F is ideal)
  if (temperature >= 68 && temperature <= 72) {
    score += 20
  } else if (temperature >= 65 && temperature <= 75) {
    score += 10
  }
  
  // Humidity (40-60% is ideal)
  if (humidity >= 40 && humidity <= 60) {
    score += 15
  } else if (humidity >= 30 && humidity <= 70) {
    score += 5
  }
  
  // Noise (50-70 dB is acceptable)
  if (noise >= 50 && noise <= 70) {
    score += 10
  } else if (noise < 50 || noise > 80) {
    score -= 10
  }
  
  // Light (200-500 lux is good)
  if (light >= 200 && light <= 500) {
    score += 5
  }
  
  score = Math.max(0, Math.min(100, score))
  
  const getColor = (score) => {
    if (score >= 80) return 'bg-green-500'
    if (score >= 60) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-2xl font-bold">{score.toFixed(0)}/100</span>
        <span className="text-gray-400">
          {score >= 80 ? 'Excellent' : score >= 60 ? 'Good' : 'Needs Improvement'}
        </span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-4">
        <div 
          className={`h-4 rounded-full transition-all duration-500 ${getColor(score)}`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  )
}
