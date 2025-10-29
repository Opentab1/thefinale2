import React, { useState } from 'react'
import { Save, RefreshCw, Plus, Trash2, MapPin, ExternalLink, Globe } from 'lucide-react'

export default function SettingsPage({ currentLocation, onLocationChange }) {
  const [venueName, setVenueName] = useState('Pulse Venue')
  const [timezone, setTimezone] = useState('America/Chicago')
  const [locations, setLocations] = useState(() => {
    const saved = localStorage.getItem('pulse_locations')
    return saved ? JSON.parse(saved) : [
      { id: 1, name: 'Main Location', address: '123 Main St', active: true },
      { id: 2, name: 'Second Location', address: '456 Oak Ave', active: false }
    ]
  })
  const [newLocationName, setNewLocationName] = useState('')
  const [newLocationAddress, setNewLocationAddress] = useState('')
  
  const handleSave = () => {
    localStorage.setItem('pulse_locations', JSON.stringify(locations))
    alert('Settings saved!')
  }

  const addLocation = () => {
    if (!newLocationName.trim()) return
    
    const newLocation = {
      id: Date.now(),
      name: newLocationName,
      address: newLocationAddress,
      active: false
    }
    
    const updatedLocations = [...locations, newLocation]
    setLocations(updatedLocations)
    localStorage.setItem('pulse_locations', JSON.stringify(updatedLocations))
    
    setNewLocationName('')
    setNewLocationAddress('')
  }

  const removeLocation = (id) => {
    const updatedLocations = locations.filter(loc => loc.id !== id)
    setLocations(updatedLocations)
    localStorage.setItem('pulse_locations', JSON.stringify(updatedLocations))
  }

  const selectLocation = (locationName) => {
    onLocationChange(locationName)
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Settings</h2>
        
        {/* GoDaddy Button */}
        <a
          href="https://www.godaddy.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 rounded-lg font-medium transition-all shadow-lg hover:shadow-xl"
        >
          <Globe className="w-5 h-5" />
          <span>Manage Domain on GoDaddy</span>
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>
      
      {/* Venue Settings */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4">Venue Information</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Venue Name</label>
            <input
              type="text"
              value={venueName}
              onChange={(e) => setVenueName(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-pulse-blue"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Timezone</label>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-pulse-blue"
            >
              <option value="America/Chicago">Central Time (Chicago)</option>
              <option value="America/New_York">Eastern Time (New York)</option>
              <option value="America/Los_Angeles">Pacific Time (Los Angeles)</option>
              <option value="America/Denver">Mountain Time (Denver)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Multi-Location Management */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4 flex items-center">
          <MapPin className="w-6 h-6 mr-2 text-blue-500" />
          Location Management
        </h3>
        
        {/* Current Locations */}
        <div className="space-y-3 mb-6">
          {locations.map(location => (
            <div
              key={location.id}
              className={`p-4 rounded-lg border-2 transition-all ${
                currentLocation === location.name
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-gray-700 bg-gray-900/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h4 className="font-medium">{location.name}</h4>
                    {currentLocation === location.name && (
                      <span className="px-2 py-1 bg-blue-600 text-xs rounded-full">Active</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-400 mt-1">{location.address}</p>
                </div>
                
                <div className="flex items-center space-x-2">
                  {currentLocation !== location.name && (
                    <button
                      onClick={() => selectLocation(location.name)}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
                    >
                      Switch to this location
                    </button>
                  )}
                  
                  {locations.length > 1 && (
                    <button
                      onClick={() => removeLocation(location.id)}
                      className="p-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
                      title="Remove location"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add New Location */}
        <div className="border-t border-gray-700 pt-4">
          <h4 className="font-medium mb-3">Add New Location</h4>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Location name"
              value={newLocationName}
              onChange={(e) => setNewLocationName(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500"
            />
            <input
              type="text"
              placeholder="Address (optional)"
              value={newLocationAddress}
              onChange={(e) => setNewLocationAddress(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            onClick={addLocation}
            className="mt-3 flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Add Location</span>
          </button>
        </div>
      </div>

      {/* AWS IoT Configuration */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4">AWS IoT Configuration</h3>
        
        <div className="space-y-4">
          <div className="bg-gray-900/50 border border-gray-700 rounded-lg p-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-gray-400 mb-1">Region</div>
                <div className="font-mono">us-east-2</div>
              </div>
              <div>
                <div className="text-gray-400 mb-1">Status</div>
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-green-400">Connected</span>
                </div>
              </div>
              <div className="col-span-2">
                <div className="text-gray-400 mb-1">Endpoint</div>
                <div className="font-mono text-xs">wss://iot.us-east-2.amazonaws.com/mqtt</div>
              </div>
              <div className="col-span-2">
                <div className="text-gray-400 mb-1">RPi Data Topics</div>
                <div className="space-y-1 text-xs font-mono">
                  <div>• pulse/sensors/{currentLocation.toLowerCase().replace(/\s+/g, '-')}</div>
                  <div>• pulse/controls/{currentLocation.toLowerCase().replace(/\s+/g, '-')}</div>
                  <div>• pulse/status/{currentLocation.toLowerCase().replace(/\s+/g, '-')}</div>
                </div>
              </div>
            </div>
          </div>
          
          <div className="text-sm text-gray-400">
            <p>✓ Real-time data streaming from Raspberry Pi 5</p>
            <p>✓ Secure MQTT over WebSocket connection</p>
            <p>✓ Automatic reconnection and failover</p>
          </div>
        </div>
      </div>
      
      {/* Automation Policies */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4">Automation Policies</h3>
        
        <div className="space-y-6">
          <PolicySection
            title="HVAC Limits"
            fields={[
              { label: 'Minimum Temperature (°F)', value: 67, min: 60, max: 80 },
              { label: 'Maximum Temperature (°F)', value: 75, min: 60, max: 80 }
            ]}
          />
          
          <PolicySection
            title="Lighting Limits"
            fields={[
              { label: 'Minimum Brightness (%)', value: 20, min: 0, max: 100 },
              { label: 'Maximum Brightness (%)', value: 85, min: 0, max: 100 }
            ]}
          />
          
          <PolicySection
            title="Music Limits"
            fields={[
              { label: 'Minimum Volume (%)', value: 25, min: 0, max: 100 },
              { label: 'Maximum Volume (%)', value: 70, min: 0, max: 100 }
            ]}
          />
        </div>
      </div>
      
      {/* Actions */}
      <div className="flex space-x-4">
        <button
          onClick={handleSave}
          className="flex items-center space-x-2 px-6 py-3 bg-pulse-blue hover:bg-blue-600 rounded-lg font-medium transition-colors"
        >
          <Save className="w-5 h-5" />
          <span>Save Settings</span>
        </button>
        
        <button
          className="flex items-center space-x-2 px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-medium transition-colors"
        >
          <RefreshCw className="w-5 h-5" />
          <span>Reset to Defaults</span>
        </button>
      </div>
    </div>
  )
}

function PolicySection({ title, fields }) {
  return (
    <div>
      <h4 className="font-semibold mb-3">{title}</h4>
      <div className="space-y-3">
        {fields.map((field, index) => (
          <div key={index}>
            <label className="block text-sm text-gray-400 mb-1">{field.label}</label>
            <input
              type="number"
              defaultValue={field.value}
              min={field.min}
              max={field.max}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-pulse-blue"
            />
          </div>
        ))}
      </div>
    </div>
  )
}
