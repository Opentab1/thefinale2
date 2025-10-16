import React, { useEffect, useState } from 'react';
import LiveOverview from './LiveOverview';

function useHub() {
  const [auto, setAuto] = useState<{ hvac: boolean; lighting: boolean; tv: boolean; music: boolean }>({ hvac: true, lighting: true, tv: true, music: true });
  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'auto_state') setAuto(msg.data);
      } catch {}
    };
    return () => ws.close();
  }, []);

  async function toggle(system: keyof typeof auto) {
    const next = !auto[system];
    setAuto((prev) => ({ ...prev, [system]: next }));
    try {
      await fetch('/api/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system, auto: next })
      });
    } catch {}
  }

  return { auto, toggle };
}

function Nav({ tab, setTab }: { tab: string; setTab: (t: string) => void }) {
  const tabs = ['Overview', 'Analytics', 'Smart Integrations', 'System Health', 'Settings'];
  return (
    <nav className="flex gap-2 text-sm flex-wrap">
      {tabs.map((t) => (
        <button 
          key={t} 
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            tab === t 
              ? 'bg-blue-600 text-white' 
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`} 
          onClick={() => setTab(t)}
        >
          {t}
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const [tab, setTab] = useState('Overview');
  const { auto, toggle } = useHub();
  
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="px-6 py-4 border-b border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="text-2xl font-bold bg-gradient-to-r from-blue-500 to-purple-500 bg-clip-text text-transparent">
              Pulse
            </div>
            <div className="text-xs px-2 py-1 bg-green-600/20 text-green-400 rounded-full flex items-center gap-1">
              <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
              Live
            </div>
          </div>
          <div className="text-sm text-gray-400">
            {new Date().toLocaleString()}
          </div>
        </div>
        <Nav tab={tab} setTab={setTab} />
      </header>
      
      <main className="p-6">
        {tab === 'Overview' && <LiveOverview />}
        
        {tab === 'Analytics' && (
          <div className="space-y-4">
            <h1 className="text-2xl font-bold">Analytics</h1>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center text-gray-400">
              <div className="text-4xl mb-3">📊</div>
              <div>Historical analytics and trends will appear here</div>
              <div className="text-sm mt-2">Occupancy patterns, temperature trends, peak hours, etc.</div>
            </div>
          </div>
        )}
        
        {tab === 'Smart Integrations' && (
          <div className="space-y-4">
            <h1 className="text-2xl font-bold">Smart Integrations</h1>
            <div className="grid md:grid-cols-2 gap-4">
              <Panel title="HVAC" active={auto.hvac} onToggle={() => toggle('hvac')} icon="🌡️" />
              <Panel title="Lighting" active={auto.lighting} onToggle={() => toggle('lighting')} icon="💡" />
              <Panel title="TV" active={auto.tv} onToggle={() => toggle('tv')} icon="📺" />
              <Panel title="Music" active={auto.music} onToggle={() => toggle('music')} icon="🎵" />
            </div>
          </div>
        )}
        
        {tab === 'System Health' && (
          <div className="space-y-4">
            <h1 className="text-2xl font-bold">System Health</h1>
            <div className="grid md:grid-cols-3 gap-4">
              <HealthCard title="CPU" status="good" value="45%" />
              <HealthCard title="Memory" status="good" value="62%" />
              <HealthCard title="Storage" status="warning" value="78%" />
              <HealthCard title="Temperature" status="good" value="52°C" />
              <HealthCard title="Uptime" status="good" value="3d 12h" />
              <HealthCard title="Network" status="good" value="Connected" />
            </div>
          </div>
        )}
        
        {tab === 'Settings' && (
          <div className="space-y-4">
            <h1 className="text-2xl font-bold">Settings</h1>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="font-semibold mb-4">System Configuration</h2>
              <div className="space-y-3 text-sm text-gray-400">
                <div>• Venue settings</div>
                <div>• Integration credentials</div>
                <div>• Automation rules</div>
                <div>• Alert thresholds</div>
                <div className="pt-3 text-xs">Settings management coming soon</div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function Panel({ title, active, onToggle, icon }: { title: string; active: boolean; onToggle: () => void; icon: string }) {
  return (
    <div className="border border-gray-800 rounded-lg p-6 bg-gray-900">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <div className="font-medium text-lg">{title}</div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-3 py-1 rounded-full ${active ? 'bg-green-600/20 text-green-400' : 'bg-yellow-600/20 text-yellow-300'}`}>
            {active ? 'Auto' : 'Manual'}
          </span>
          <button 
            className="text-xs px-3 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors" 
            onClick={onToggle}
          >
            {active ? 'Switch to Manual' : 'Switch to Auto'}
          </button>
        </div>
      </div>
      <div className="text-sm text-gray-400">
        Automation {active ? 'enabled' : 'disabled'} - controls will adjust based on venue conditions
      </div>
    </div>
  );
}

function HealthCard({ title, status, value }: { title: string; status: string; value: string }) {
  const statusColors = {
    good: 'border-green-700/50 bg-green-600/10',
    warning: 'border-yellow-700/50 bg-yellow-600/10',
    error: 'border-red-700/50 bg-red-600/10'
  };
  
  return (
    <div className={`border rounded-lg p-4 ${statusColors[status as keyof typeof statusColors]}`}>
      <div className="text-sm text-gray-400 mb-1">{title}</div>
      <div className="text-2xl font-bold">{value}</div>
      <div className={`text-xs mt-2 ${status === 'good' ? 'text-green-400' : status === 'warning' ? 'text-yellow-400' : 'text-red-400'}`}>
        {status === 'good' ? '✓ Normal' : status === 'warning' ? '⚠ Warning' : '✗ Error'}
      </div>
    </div>
  );
}
