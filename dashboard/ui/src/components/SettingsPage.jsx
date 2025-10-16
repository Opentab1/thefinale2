import React, { useState } from 'react'
import { Save, RefreshCw } from 'lucide-react'

export default function SettingsPage() {
  const [venueName, setVenueName] = useState('Pulse Venue')
  const [timezone, setTimezone] = useState('America/Chicago')
  
  const handleSave = () => {
    // In a real implementation, this would save to the backend
    alert('Settings saved!')
  }
  
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Settings</h2>
      
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
