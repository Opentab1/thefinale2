import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import { Activity, BarChart2, Settings, Zap, AlertCircle } from 'lucide-react'
import io from 'socket.io-client'
import axios from 'axios'

// Components
import LiveOverview from './components/LiveOverview'
import Analytics from './components/Analytics'
import Controls from './components/Controls'
import SystemHealth from './components/SystemHealth'
import SettingsPage from './components/SettingsPage'

const API_URL = window.location.origin

function App() {
  const [socket, setSocket] = useState(null)
  const [connected, setConnected] = useState(false)
  const [sensorData, setSensorData] = useState({})
  const [systemStatus, setSystemStatus] = useState({})
  const [safeMode, setSafeMode] = useState(false)

  useEffect(() => {
    // Connect to WebSocket
    const newSocket = io(API_URL)
    
    newSocket.on('connect', () => {
      console.log('Connected to Pulse Hub')
      setConnected(true)
    })
    
    newSocket.on('disconnect', () => {
      console.log('Disconnected from Pulse Hub')
      setConnected(false)
    })
    
    newSocket.on('sensor_update', (data) => {
      setSensorData(data)
    })
    
    setSocket(newSocket)
    
    // Fetch initial system status
    fetchSystemStatus()
    
    // Poll system status every 30 seconds
    const interval = setInterval(fetchSystemStatus, 30000)
    
    return () => {
      newSocket.close()
      clearInterval(interval)
    }
  }, [])

  const fetchSystemStatus = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/status`)
      setSystemStatus(response.data)
    } catch (error) {
      console.error('Error fetching system status:', error)
    }
  }

  const toggleSafeMode = async () => {
    // In safe mode, disable all automation
    const newSafeMode = !safeMode
    setSafeMode(newSafeMode)
    
    if (newSafeMode) {
      // Disable all auto modes
      try {
        await axios.post(`${API_URL}/api/hvac/auto`, { enabled: false })
        await axios.post(`${API_URL}/api/lighting/auto`, { enabled: false })
        await axios.post(`${API_URL}/api/music/auto`, { enabled: false })
      } catch (error) {
        console.error('Error enabling safe mode:', error)
      }
    } else {
      // Re-enable auto modes
      try {
        await axios.post(`${API_URL}/api/hvac/auto`, { enabled: true })
        await axios.post(`${API_URL}/api/lighting/auto`, { enabled: true })
        await axios.post(`${API_URL}/api/music/auto`, { enabled: true })
      } catch (error) {
        console.error('Error disabling safe mode:', error)
      }
    }
  }

  return (
    <Router>
      <div className="min-h-screen bg-gray-900">
        {/* Top Bar */}
        <header className="bg-gray-800 border-b border-gray-700 sticky top-0 z-50">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <Activity className="w-8 h-8 text-pulse-blue" />
                <h1 className="text-2xl font-bold">Pulse 1.0</h1>
                <span className="text-sm text-gray-400">
                  {new Date().toLocaleTimeString()}
                </span>
              </div>
              
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-sm">{connected ? 'Connected' : 'Disconnected'}</span>
                </div>
                
                <button
                  onClick={toggleSafeMode}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    safeMode 
                      ? 'bg-red-600 hover:bg-red-700' 
                      : 'bg-gray-700 hover:bg-gray-600'
                  }`}
                >
                  {safeMode ? 'Safe Mode: ON' : 'Safe Mode: OFF'}
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Navigation */}
        <nav className="bg-gray-800 border-b border-gray-700">
          <div className="container mx-auto px-4">
            <div className="flex space-x-1">
              <NavLink to="/" icon={<Activity />} label="Live" />
              <NavLink to="/analytics" icon={<BarChart2 />} label="Analytics" />
              <NavLink to="/controls" icon={<Zap />} label="Controls" />
              <NavLink to="/health" icon={<AlertCircle />} label="Health" />
              <NavLink to="/settings" icon={<Settings />} label="Settings" />
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="container mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<LiveOverview sensorData={sensorData} />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/controls" element={<Controls />} />
            <Route path="/health" element={<SystemHealth systemStatus={systemStatus} />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

function NavLink({ to, icon, label }) {
  return (
    <Link
      to={to}
      className="flex items-center space-x-2 px-4 py-3 text-gray-300 hover:text-white hover:bg-gray-700 transition-colors"
    >
      {icon}
      <span>{label}</span>
    </Link>
  )
}

export default App
