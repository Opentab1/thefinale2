const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const path = require('path');
const http = require('http');
const { createProxyMiddleware } = require('http-proxy-middleware');
const { WebSocketServer, WebSocket } = require('ws');

const app = express();
app.use(cors());
app.use(express.json());
app.use(morgan('tiny'));

const HUB_URL = process.env.HUB_URL || 'http://127.0.0.1:7000';

// API proxy -> FastAPI hub
app.use('/api', createProxyMiddleware({
  target: HUB_URL,
  changeOrigin: true,
  pathRewrite: { '^/api': '' },
  ws: false,
}));

// Serve built UI
const staticDir = path.resolve(__dirname, '../ui/dist');
app.use(express.static(staticDir));
app.get('*', (req, res) => {
  res.sendFile(path.join(staticDir, 'index.html'));
});

// WebSocket relay /ws -> hub /ws
const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: '/ws' });

wss.on('connection', (client) => {
  const hubWsUrl = HUB_URL.replace('http', 'ws') + '/ws';
  const upstream = new WebSocket(hubWsUrl);
  const closeBoth = () => {
    try { client.close(); } catch {}
    try { upstream.close(); } catch {}
  };
  upstream.on('open', () => {
    client.on('message', (data) => {
      try { upstream.send(data); } catch {}
    });
  });
  upstream.on('message', (data) => {
    try { client.send(data); } catch {}
  });
  upstream.on('close', closeBoth);
  upstream.on('error', closeBoth);
  client.on('close', closeBoth);
  client.on('error', closeBoth);
});

const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
  console.log(`Dashboard listening on :${PORT}`);
});
