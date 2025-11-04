/**
 * AI BARTENDER DRINK COUNTER - Visual Mockup
 * 
 * This shows how the drink counter component would look in the dashboard.
 * This is a VISUALIZATION ONLY - not integrated into the actual codebase.
 * 
 * The component would be added to LiveOverview.jsx and would receive
 * data from the WebSocket updates, just like the existing metrics.
 */

// ===== EXAMPLE: How the component would look =====

import React from 'react'
import { Wine, TrendingUp, BarChart2, Clock } from 'lucide-react'

export function BartenderCounter({ drinkData }) {
  const {
    drinks_this_hour = 0,
    hourly_rate = 0,
    peak_hour = null,
    total_today = 0,
    last_detection = null
  } = drinkData || {}

  return (
    <div className="space-y-6">
      {/* Main Drink Counter Cards - Would appear in the grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        
        {/* Drinks This Hour Card */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <div className="text-amber-500">
              <Wine className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-semibold">Drinks This Hour</h3>
          </div>
          <div className="text-3xl font-bold">
            {drinks_this_hour} <span className="text-xl text-gray-400">drinks</span>
          </div>
          {hourly_rate > 0 && (
            <div className="text-sm text-gray-400 mt-2">
              Avg: {(60 / hourly_rate).toFixed(1)} min/drink
            </div>
          )}
        </div>

        {/* Hourly Rate Card */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <div className="text-green-500">
              <TrendingUp className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-semibold">Hourly Rate</h3>
          </div>
          <div className="text-3xl font-bold">
            {hourly_rate.toFixed(0)} <span className="text-xl text-gray-400">drinks/hour</span>
          </div>
          <div className="text-sm text-green-400 mt-2">
            Projected: {hourly_rate * 24} drinks/day
          </div>
        </div>

        {/* Peak Hour Card */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <div className="text-purple-500">
              <BarChart2 className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-semibold">Peak Hour</h3>
          </div>
          {peak_hour ? (
            <>
              <div className="text-2xl font-bold">
                {peak_hour.hour}
              </div>
              <div className="text-xl text-gray-400 mt-1">
                {peak_hour.count} drinks
              </div>
            </>
          ) : (
            <div className="text-gray-400">No data yet</div>
          )}
        </div>
      </div>

      {/* Detailed Drink Counter Section */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-xl font-semibold mb-4 flex items-center space-x-2">
          <Wine className="w-6 h-6 text-amber-500" />
          <span>AI Bartender Counter</span>
        </h3>

        {/* Summary Stats */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <div className="text-sm text-gray-400">Current Hour</div>
            <div className="text-2xl font-bold">{drinks_this_hour} drinks</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Total Today</div>
            <div className="text-2xl font-bold">{total_today} drinks</div>
          </div>
        </div>

        {/* Hour Progress Bar */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">Hour Progress</span>
            <span className="text-sm text-gray-400">
              {new Date().getMinutes()} / 60 min
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-3">
            <div
              className="bg-amber-500 h-3 rounded-full transition-all duration-500"
              style={{ width: `${(new Date().getMinutes() / 60) * 100}%` }}
            />
          </div>
        </div>

        {/* Recent Detections */}
        <div>
          <h4 className="text-sm font-semibold text-gray-400 mb-3">Recent Detections</h4>
          <div className="space-y-2">
            {last_detection ? (
              <div className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <Clock className="w-4 h-4 text-gray-400" />
                  <span className="text-sm">
                    {new Date(last_detection.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <span className="text-sm font-medium">
                  {last_detection.type || 'Drink'} detected
                  {last_detection.confidence && (
                    <span className="text-gray-400 ml-2">
                      ({Math.round(last_detection.confidence * 100)}%)
                    </span>
                  )}
                </span>
              </div>
            ) : (
              <div className="text-gray-400 text-sm">No recent detections</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ===== EXAMPLE: How it would be integrated into LiveOverview.jsx =====

/*
In LiveOverview.jsx, you would add:

import { BartenderCounter } from './BartenderCounter'

// In the component:
const { drinks_this_hour, hourly_rate, ... } = sensorData

// In the return statement, add the component:
<BartenderCounter drinkData={sensorData} />

*/

// ===== EXAMPLE: WebSocket data structure =====

/*
The sensorData object would include:

{
  occupancy: 15,
  temperature_f: 72.5,
  // ... existing fields ...
  drinks_this_hour: 47,
  hourly_rate: 28,
  total_today: 312,
  peak_hour: {
    hour: "21:00",
    count: 62
  },
  last_detection: {
    timestamp: "2024-01-15T14:34:22Z",
    type: "cocktail",
    confidence: 0.92
  }
}
*/
