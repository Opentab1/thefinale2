import React, { useEffect, useState } from 'react';

interface LiveData {
  people_count: number;
  temperature: number;
  humidity: number;
  decibels: number;
  light_level?: number;
  song: {
    title: string;
    artist: string;
    detected: boolean;
  };
  integrations: {
    nest_connected: boolean;
    hue_connected: boolean;
    spotify_connected: boolean;
  };
  camera_active: boolean;
}

export default function LiveOverview() {
  const [data, setData] = useState<LiveData>({
    people_count: 0,
    temperature: 72,
    humidity: 45,
    decibels: 0,
    light_level: 0,
    song: { title: 'No song detected', artist: '', detected: false },
    integrations: { nest_connected: false, hue_connected: false, spotify_connected: false },
    camera_active: false
  });

  useEffect(() => {
    // Connect to WebSocket for real-time updates
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'live_data') {
          setData(prev => ({ ...prev, ...msg.data }));
        }
      } catch (e) {
        console.error('WebSocket parse error:', e);
      }
    };

    // Also poll REST API every 2 seconds as fallback
    const interval = setInterval(async () => {
      try {
        const response = await fetch('/api/live');
        if (response.ok) {
          const liveData = await response.json();
          setData(prev => ({ ...prev, ...liveData }));
        }
      } catch (e) {
        console.error('API fetch error:', e);
      }
    }, 2000);

    return () => {
      ws.close();
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Live Analytics</h1>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-gray-400">Live</span>
        </div>
      </div>

      {/* Top Stats Grid */}
      <div className="grid md:grid-cols-5 gap-4">
        <StatCard
          title="People In Venue"
          value={data.people_count}
          unit=""
          icon="👥"
          color="blue"
        />
        <StatCard
          title="Temperature"
          value={data.temperature}
          unit="°F"
          icon="🌡️"
          color="orange"
        />
        <StatCard
          title="Humidity"
          value={data.humidity}
          unit="%"
          icon="💧"
          color="cyan"
        />
        <StatCard
          title="Sound Level"
          value={data.decibels}
          unit="dB"
          icon="🔊"
          color={data.decibels > 85 ? 'red' : 'green'}
        />
        <StatCard
          title="Light Level"
          value={Math.round(Number(data.light_level || 0))}
          unit=" lux"
          icon="💡"
          color="cyan"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Song Detection */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">🎵</span>
            <h2 className="text-lg font-semibold">Now Playing</h2>
          </div>
          {data.song.detected ? (
            <div className="space-y-2">
              <div className="text-xl font-medium text-white">{data.song.title}</div>
              <div className="text-sm text-gray-400">{data.song.artist}</div>
              <div className="flex items-center gap-2 mt-3">
                <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-xs text-green-400">Detected via microphone</span>
              </div>
            </div>
          ) : (
            <div className="text-gray-500 py-4">
              <div className="text-sm">No song currently detected</div>
              <div className="text-xs mt-1">Listening...</div>
            </div>
          )}
        </div>

        {/* Decibel Meter */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">📊</span>
            <h2 className="text-lg font-semibold">Sound Meter</h2>
          </div>
          <div className="space-y-4">
            <div className="flex items-end justify-center h-32">
              {Array.from({ length: 20 }).map((_, i) => {
                const threshold = (i + 1) * 5;
                const isActive = data.decibels >= threshold;
                const color = threshold > 85 ? 'bg-red-500' : threshold > 70 ? 'bg-yellow-500' : 'bg-green-500';
                return (
                  <div
                    key={i}
                    className={`w-3 mx-0.5 transition-all duration-200 ${
                      isActive ? color : 'bg-gray-700'
                    }`}
                    style={{ height: `${threshold}%` }}
                  ></div>
                );
              })}
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold">{data.decibels}</div>
              <div className="text-sm text-gray-400">Decibels</div>
            </div>
          </div>
        </div>

        {/* Camera Feed */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">📹</span>
            <h2 className="text-lg font-semibold">Live Camera</h2>
            {data.camera_active && (
              <span className="ml-auto text-xs px-2 py-1 bg-green-600/20 text-green-400 rounded">
                Active
              </span>
            )}
          </div>
          <div className="aspect-video bg-gray-950 rounded-lg overflow-hidden relative">
            {data.camera_active ? (
              <img
                src="/api/camera/stream"
                alt="Live camera feed"
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-gray-600">
                <div className="text-center">
                  <div className="text-4xl mb-2">📷</div>
                  <div className="text-sm">Camera offline</div>
                </div>
              </div>
            )}
            {data.camera_active && data.people_count > 0 && (
              <div className="absolute top-2 right-2 bg-black/70 px-3 py-1 rounded text-sm">
                {data.people_count} {data.people_count === 1 ? 'person' : 'people'} detected
              </div>
            )}
          </div>
        </div>

        {/* Connected Integrations */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">🔌</span>
            <h2 className="text-lg font-semibold">Connected Integrations</h2>
          </div>
          <div className="space-y-3">
            <IntegrationStatus
              name="Google Nest"
              connected={data.integrations.nest_connected}
              icon="🌡️"
            />
            <IntegrationStatus
              name="Philips Hue"
              connected={data.integrations.hue_connected}
              icon="💡"
            />
            <IntegrationStatus
              name="Spotify"
              connected={data.integrations.spotify_connected}
              icon="🎵"
            />
          </div>
          <div className="mt-4 pt-4 border-t border-gray-800">
            <div className="text-xs text-gray-500">
              {Object.values(data.integrations).filter(Boolean).length} of 3 integrations active
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: number;
  unit: string;
  icon: string;
  color: string;
}

function StatCard({ title, value, unit, icon, color }: StatCardProps) {
  const colors = {
    blue: 'from-blue-600/20 to-blue-900/20 border-blue-700/50',
    orange: 'from-orange-600/20 to-orange-900/20 border-orange-700/50',
    cyan: 'from-cyan-600/20 to-cyan-900/20 border-cyan-700/50',
    green: 'from-green-600/20 to-green-900/20 border-green-700/50',
    red: 'from-red-600/20 to-red-900/20 border-red-700/50'
  };

  return (
    <div className={`bg-gradient-to-br ${colors[color as keyof typeof colors]} border rounded-lg p-4`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        <div className="text-sm text-gray-400">{title}</div>
      </div>
      <div className="text-3xl font-bold">
        {value}{unit}
      </div>
    </div>
  );
}

interface IntegrationStatusProps {
  name: string;
  connected: boolean;
  icon: string;
}

function IntegrationStatus({ name, connected, icon }: IntegrationStatusProps) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
      <div className="flex items-center gap-3">
        <span className="text-xl">{icon}</span>
        <span className="text-sm font-medium">{name}</span>
      </div>
      <div className={`flex items-center gap-2 text-xs ${connected ? 'text-green-400' : 'text-gray-500'}`}>
        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-600'}`}></div>
        {connected ? 'Connected' : 'Offline'}
      </div>
    </div>
  );
}
