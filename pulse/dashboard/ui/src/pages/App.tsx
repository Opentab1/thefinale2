import React, { useEffect, useMemo, useState } from 'react';

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
    <nav className="flex gap-3 text-sm">
      {tabs.map((t) => (
        <button key={t} className={`px-3 py-2 rounded ${tab === t ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-300'}`} onClick={() => setTab(t)}>
          {t}
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const [tab, setTab] = useState('Smart Integrations');
  const { auto, toggle } = useHub();
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <div className="font-semibold">Pulse</div>
        <Nav tab={tab} setTab={setTab} />
        <div className="text-sm opacity-75">Status: Online</div>
      </header>
      <main className="p-6">
        {tab === 'Smart Integrations' && (
          <div className="grid md:grid-cols-2 gap-4">
            <Panel title="HVAC" active={auto.hvac} onToggle={() => toggle('hvac')} />
            <Panel title="Lighting" active={auto.lighting} onToggle={() => toggle('lighting')} />
            <Panel title="TV" active={auto.tv} onToggle={() => toggle('tv')} />
            <Panel title="Music" active={auto.music} onToggle={() => toggle('music')} />
          </div>
        )}
        {tab !== 'Smart Integrations' && (
          <div className="text-sm opacity-75">This tab will be implemented next.</div>
        )}
      </main>
    </div>
  );
}

function Panel({ title, active, onToggle }: { title: string; active: boolean; onToggle: () => void }) {
  return (
    <div className="border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <div className="font-medium">{title}</div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-1 rounded ${active ? 'bg-green-600/20 text-green-400' : 'bg-yellow-600/20 text-yellow-300'}`}>{active ? 'Auto' : 'Manual'}</span>
          <button className="text-xs px-2 py-1 rounded bg-gray-700" onClick={onToggle}>{active ? 'Switch to Manual' : 'Switch to Auto'}</button>
        </div>
      </div>
      <div className="mt-4 text-sm opacity-75">Controls coming next…</div>
    </div>
  );
}
