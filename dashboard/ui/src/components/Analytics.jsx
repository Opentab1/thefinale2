import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const API_URL = window.location.origin

export default function Analytics() {
  const [occupancyData, setOccupancyData] = useState([])
  const [environmentData, setEnvironmentData] = useState([])
  const [timeRange, setTimeRange] = useState(24)
  
  useEffect(() => {
    fetchData()
  }, [timeRange])
  
  const fetchData = async () => {
    try {
      const [occupancy, environment] = await Promise.all([
        axios.get(`${API_URL}/api/occupancy/history?hours=${timeRange}`),
        axios.get(`${API_URL}/api/environment/trends?hours=${timeRange}`)
      ])
      
      setOccupancyData(occupancy.data)
      setEnvironmentData(environment.data)
    } catch (error) {
      console.error('Error fetching analytics:', error)
    }
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Analytics</h2>
        
        <div className="flex space-x-2">
          {[24, 48, 168].map((hours) => (
            <button
              key={hours}
              onClick={() => setTimeRange(hours)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                timeRange === hours
                  ? 'bg-pulse-blue text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {hours === 168 ? '7 Days' : `${hours}h`}
            </button>
          ))}
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Occupancy Trend">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={occupancyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis 
                dataKey="hour" 
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF' }}
              />
              <YAxis stroke="#9CA3AF" tick={{ fill: '#9CA3AF' }} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="avg_count" 
                stroke="#3B82F6" 
                name="Average Occupancy"
                strokeWidth={2}
              />
              <Line 
                type="monotone" 
                dataKey="max_count" 
                stroke="#EF4444" 
                name="Peak Occupancy"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
        
        <ChartCard title="Temperature Trend">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={environmentData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis 
                dataKey="hour" 
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF' }}
              />
              <YAxis stroke="#9CA3AF" tick={{ fill: '#9CA3AF' }} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="avg_temp" 
                stroke="#EF4444" 
                name="Temperature (°F)"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
        
        <ChartCard title="Humidity Trend">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={environmentData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis 
                dataKey="hour" 
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF' }}
              />
              <YAxis stroke="#9CA3AF" tick={{ fill: '#9CA3AF' }} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="avg_humidity" 
                stroke="#3B82F6" 
                name="Humidity (%)"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
        
        <ChartCard title="Noise Level Trend">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={environmentData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis 
                dataKey="hour" 
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF' }}
              />
              <YAxis stroke="#9CA3AF" tick={{ fill: '#9CA3AF' }} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="avg_noise" 
                stroke="#A855F7" 
                name="Noise Level (dB)"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}

function ChartCard({ title, children }) {
  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      {children}
    </div>
  )
}
