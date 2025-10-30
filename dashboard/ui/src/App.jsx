import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import { Activity, BarChart2, Settings, Zap, AlertCircle, LogOut, MapPin } from 'lucide-react'
import io from 'socket.io-client'
import axios from 'axios'
import { Amplify } from 'aws-amplify'
import { getCurrentUser, signOut } from 'aws-amplify/auth'
import { awsConfig } from './aws-config'
import { useIoTData } from './hooks/useIoTData'

// Components
import Login from './components/Login'
import LiveOverview from './components/LiveOverview'
import Analytics from './components/Analytics'
import Controls from './components/Controls'
import SystemHealth from './components/SystemHealth'
import SettingsPage from './components/SettingsPage'

// Configure AWS Amplify
Amplify.configure(awsConfig)

const API_URL = window.location.origin

function App() {
  const [authenticated, setAuthenticated] = useState(false)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [user, setUser] = useState(null)
  const [socket, setSocket] = useState(null)
  const [connected, setConnected] = useState(false)
  const [sensorData, setSensorData] = useState({})
  // AWS IoT Core live data (Cognito-authenticated, if identity pool configured)
  const { iotData, iotConnected } = useIoTData()

  const [systemStatus, setSystemStatus] = useState({})
  const [safeMode, setSafeMode] = useState(false)
  const [currentLocation, setCurrentLocation] = useState(
    localStorage.getItem('pulse_location') || 'Main Location'
  )

  // Check authentication status
  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const currentUser = await getCurrentUser()
      setUser(currentUser)
      setAuthenticated(true)
    } catch (err) {
      setAuthenticated(false)
    } finally {
      setCheckingAuth(false)
    }
  }

  const handleSignOut = async () => {
    try {
      await signOut()
      setAuthenticated(false)
      setUser(null)
    } catch (err) {
      console.error('Error signing out:', err)
    }
  }

  const handleLocationChange = (location) => {
    setCurrentLocation(location)
    localStorage.setItem('pulse_location', location)
  }

  // Show login if not authenticated
  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-16 h-16 text-blue-500 animate-pulse mx-auto mb-4" />
          <div className="text-xl text-gray-400">Loading...</div>
        </div>
      </div>
    )
  }

  if (!authenticated) {
    return <Login onAuthSuccess={() => setAuthenticated(true)} />
  }

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

  // When IoT data arrives, prefer it over socket data
  const displayData = iotConnected ? iotData : sensorData

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
                <div className="flex items-center space-x-2 px-3 py-1 bg-gray-700 rounded-lg">
                  <MapPin className="w-4 h-4 text-blue-400" />
                  <span className="text-sm">{currentLocation}</span>
                </div>
                
                <div className="flex items-center space-x-2">
                  <div className={`w-2 h-2 rounded-full ${(iotConnected || connected) ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-sm">{(iotConnected || connected) ? 'Connected' : 'Disconnected'}</span>
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

                <button
                  onClick={handleSignOut}
                  className="px-4 py-2 rounded-lg font-medium bg-gray-700 hover:bg-gray-600 transition-colors flex items-center space-x-2"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
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
            <Route path="/" element={<LiveOverview sensorData={displayData} />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/controls" element={<Controls />} />
            <Route path="/health" element={<SystemHealth systemStatus={systemStatus} />} />
            <Route path="/settings" element={
              <SettingsPage 
                currentLocation={currentLocation}
                onLocationChange={handleLocationChange}
              />
            } />
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
