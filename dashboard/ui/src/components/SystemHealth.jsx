import React from 'react'
import { CheckCircle, XCircle, AlertTriangle, Cpu, HardDrive, Thermometer } from 'lucide-react'

export default function SystemHealth({ systemStatus }) {
  const { modules = {}, controllers = {}, system = {} } = systemStatus
  
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">System Health</h2>
      
      {/* System Resources */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4">System Resources</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ResourceMeter
            icon={<Cpu className="w-5 h-5" />}
            label="CPU Usage"
            value={system.cpu_usage || 0}
            unit="%"
            color="blue"
          />
          <ResourceMeter
            icon={<HardDrive className="w-5 h-5" />}
            label="Memory Usage"
            value={system.memory_usage || 0}
            unit="%"
            color="green"
          />
          <ResourceMeter
            icon={<Thermometer className="w-5 h-5" />}
            label="CPU Temperature"
            value={system.cpu_temperature || 0}
            unit="°C"
            color="red"
          />
        </div>
      </div>
      
      {/* Sensor Modules */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4">Sensor Modules</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <ModuleStatus name="Camera" enabled={modules.camera} />
          <ModuleStatus name="Microphone" enabled={modules.mic} />
          <ModuleStatus name="BME280 Sensor" enabled={modules.bme280} />
          <ModuleStatus name="Light Sensor" enabled={modules.light_sensor} />
          <ModuleStatus name="Pan-Tilt HAT" enabled={modules.pan_tilt} />
        </div>
      </div>
      
      {/* Smart Integrations */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4">Smart Integrations</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <ModuleStatus name="HVAC" enabled={controllers.hvac} />
          <ModuleStatus name="Lighting" enabled={controllers.lighting} />
          <ModuleStatus name="TV" enabled={controllers.tv} />
          <ModuleStatus name="Music" enabled={controllers.music} />
        </div>
      </div>
    </div>
  )
}

function ResourceMeter({ icon, label, value, unit, color }) {
  const colorClasses = {
    blue: 'text-blue-500',
    green: 'text-green-500',
    red: 'text-red-500'
  }
  
  const getBarColor = (value) => {
    if (value > 80) return 'bg-red-500'
    if (value > 60) return 'bg-yellow-500'
    return 'bg-green-500'
  }
  
  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-2">
        <div className={colorClasses[color]}>{icon}</div>
        <span className="text-sm font-medium">{label}</span>
      </div>
      <div className="text-2xl font-bold mb-2">
        {value.toFixed(1)}{unit}
      </div>
      <div className="w-full bg-gray-700 rounded-full h-2">
        <div 
          className={`h-2 rounded-full transition-all duration-500 ${getBarColor(value)}`}
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
    </div>
  )
}

function ModuleStatus({ name, enabled }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 flex items-center justify-between">
      <span className="font-medium">{name}</span>
      {enabled ? (
        <CheckCircle className="w-5 h-5 text-green-500" />
      ) : (
        <XCircle className="w-5 h-5 text-gray-500" />
      )}
    </div>
  )
}
