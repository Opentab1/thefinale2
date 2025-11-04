import React, { useEffect, useState } from 'react'
import { Users, TrendingUp, Clock, Activity, RefreshCw } from 'lucide-react'
import axios from 'axios'

const API_URL = window.location.origin

export default function BartenderDashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [snapshotUrl, setSnapshotUrl] = useState('')
  const [selectedBartender, setSelectedBartender] = useState(null)

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 5000) // Update every 5 seconds
    
    // Update camera snapshot
    const makeUrl = () => `/api/bartender/snapshot?ts=${Date.now()}`
    setSnapshotUrl(makeUrl())
    const snapshotInterval = setInterval(() => setSnapshotUrl(makeUrl()), 3000)
    
    return () => {
      clearInterval(interval)
      clearInterval(snapshotInterval)
    }
  }, [])

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/bartender/stats`)
      setStats(response.data)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching bartender stats:', error)
      setLoading(false)
    }
  }

  const recordDrink = async (bartenderId) => {
    try {
      await axios.post(`${API_URL}/api/bartender/drink`, {
        bartender_id: bartenderId,
        drink_type: 'manual'
      })
      fetchStats() // Refresh stats
    } catch (error) {
      console.error('Error recording drink:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    )
  }

  const activeBartenders = stats?.bartenders?.filter(b => b.is_active) || []
  const inactiveBartenders = stats?.bartenders?.filter(b => !b.is_active) || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">🍸 Bartender Analytics</h2>
          <p className="text-gray-400 mt-1">
            🔒 Anonymous tracking - No biometric data stored
          </p>
        </div>
        <button
          onClick={fetchStats}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg flex items-center space-x-2 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          icon={<Activity className="w-8 h-8" />}
          title="Total Drinks Today"
          value={stats?.total_drinks_today || 0}
          unit="drinks"
          color="blue"
        />
        <MetricCard
          icon={<Users className="w-8 h-8" />}
          title="Active Bartenders"
          value={stats?.active_bartenders || 0}
          unit="working"
          color="green"
        />
        <MetricCard
          icon={<TrendingUp className="w-8 h-8" />}
          title="Tracked Staff"
          value={stats?.tracked_bartenders || 0}
          unit="total"
          color="purple"
        />
      </div>

      {/* Live Camera Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 flex items-center space-x-2">
            <Activity className="w-5 h-5 text-blue-500" />
            <span>Live Bar Camera</span>
          </h3>
          <div className="aspect-video w-full bg-black/40 rounded-lg overflow-hidden flex items-center justify-center">
            {snapshotUrl ? (
              <img
                src={snapshotUrl}
                alt="Bar camera"
                className="w-full h-full object-cover"
                onError={(e) => { e.currentTarget.style.display = 'none' }}
                onLoad={(e) => { e.currentTarget.style.display = 'block' }}
              />
            ) : (
              <span className="text-gray-400 text-sm">Camera initializing...</span>
            )}
          </div>
          <div className="mt-3 text-xs text-gray-400 space-y-1">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-sm"></div>
              <span>Green box = Tracked bartender with ID</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-yellow-500 rounded-sm"></div>
              <span>Yellow box = Person in bar zone</span>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">🔒 Privacy Mode Active</h3>
          <div className="space-y-3 text-sm">
            <div className="flex items-start space-x-2">
              <span className="text-green-500">✓</span>
              <span>No face recognition used</span>
            </div>
            <div className="flex items-start space-x-2">
              <span className="text-green-500">✓</span>
              <span>No biometric data stored</span>
            </div>
            <div className="flex items-start space-x-2">
              <span className="text-green-500">✓</span>
              <span>Anonymous IDs only (tracked by clothing/position)</span>
            </div>
            <div className="flex items-start space-x-2">
              <span className="text-green-500">✓</span>
              <span>IDs reset daily</span>
            </div>
          </div>

          <div className="mt-6 p-4 bg-blue-900/30 border border-blue-700 rounded-lg">
            <p className="text-sm text-blue-300">
              <strong>How it works:</strong> AI locks onto each bartender based on their appearance 
              (clothing colors, position) and assigns them a unique anonymous ID for the shift.
            </p>
          </div>
        </div>
      </div>

      {/* Active Bartenders */}
      {activeBartenders.length > 0 && (
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-xl font-semibold mb-4 flex items-center space-x-2">
            <span>🟢</span>
            <span>Active Bartenders</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeBartenders.map((bartender) => (
              <BartenderCard
                key={bartender.id}
                bartender={bartender}
                onRecordDrink={recordDrink}
                isActive={true}
              />
            ))}
          </div>
        </div>
      )}

      {/* Inactive Bartenders */}
      {inactiveBartenders.length > 0 && (
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-xl font-semibold mb-4 flex items-center space-x-2">
            <span>⚪</span>
            <span>Inactive Bartenders (Not Currently Detected)</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {inactiveBartenders.map((bartender) => (
              <BartenderCard
                key={bartender.id}
                bartender={bartender}
                onRecordDrink={recordDrink}
                isActive={false}
              />
            ))}
          </div>
        </div>
      )}

      {/* No Bartenders Detected */}
      {(!activeBartenders || activeBartenders.length === 0) && 
       (!inactiveBartenders || inactiveBartenders.length === 0) && (
        <div className="bg-gray-800 rounded-xl p-12 border border-gray-700 text-center">
          <Users className="w-16 h-16 mx-auto text-gray-600 mb-4" />
          <h3 className="text-xl font-semibold mb-2">No Bartenders Detected Yet</h3>
          <p className="text-gray-400">
            The AI will automatically detect and track bartenders when they appear in the bar zone.
          </p>
        </div>
      )}
    </div>
  )
}

function MetricCard({ icon, title, value, unit, color }) {
  const colorClasses = {
    blue: 'text-blue-500',
    green: 'text-green-500',
    purple: 'text-purple-500',
    red: 'text-red-500'
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

function BartenderCard({ bartender, onRecordDrink, isActive }) {
  const statusColor = isActive ? 'border-green-500' : 'border-gray-600'
  const statusDot = isActive ? 'bg-green-500' : 'bg-gray-500'

  return (
    <div className={`bg-gray-900 rounded-lg p-4 border-2 ${statusColor} transition-all`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full ${statusDot}`}></div>
          <h4 className="font-bold text-lg">{bartender.anonymous_id}</h4>
        </div>
        <span className="text-xs text-gray-500">
          ID: #{bartender.id}
        </span>
      </div>

      <div className="space-y-2 text-sm mb-4">
        <div className="flex items-center justify-between">
          <span className="text-gray-400">Drinks Today:</span>
          <span className="font-semibold text-xl">{bartender.drinks_today}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-gray-400">Rate:</span>
          <span className="font-semibold">{bartender.drinks_per_hour}/hr</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-gray-400">Status:</span>
          <span className={isActive ? 'text-green-500' : 'text-gray-500'}>
            {isActive ? 'Active' : 'Inactive'}
          </span>
        </div>
      </div>

      <button
        onClick={() => onRecordDrink(bartender.id)}
        className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={!isActive}
      >
        + Record Drink
      </button>
    </div>
  )
}
