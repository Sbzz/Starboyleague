import express from 'express';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import { Fotmob } from '@max-xoo/fotmob'; // JS wrapper for unofficial FotMob API

const app = express();
app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use(rateLimit({ windowMs: 60 * 1000, max: 60 })); // simple abuse control

const fotmob = new Fotmob();
const PORT = process.env.PORT || 3000;

// Normalize a FotMob player stat object -> our minimal fantasy fields
function toFantasyStat(name, fm) {
  // Many wrappers expose recent season aggregates under different keys.
  // The fields below are defensive; adjust if the wrapper changes its shape.
  const minutes = fm?.stats?.minutes || fm?.games?.minutes || 0;
  const goalsTotal = fm?.stats?.goals || fm?.goals?.total || 0;
  const pens = fm?.stats?.penaltiesScored || fm?.penalty?.scored || 0;
  const assists = fm?.stats?.assists || fm?.goals?.assists || 0;
  const yellow = fm?.stats?.yellow || fm?.cards?.yellow || 0;
  const red = fm?.stats?.red || fm?.cards?.red || 0;
  return { name, nonPenaltyGoals: Math.max(0, goalsTotal - pens), penaltyGoals: pens || 0, assists: assists || 0, minutes, yellowCards: yellow || 0, redCards: red || 0, motm: false };
}

// POST /api/fotmob/player-stats-batch { players: ["Erling Haaland", ...], season?: 2025 }
app.post('/api/fotmob/player-stats-batch', async (req, res) => {
  try {
    const players = Array.isArray(req.body.players) ? req.body.players : [];
    if (!players.length) return res.status(400).json({ error: 'players array required' });

    const out = {};
    // Fetch sequentially to be gentle with FotMob. You can parallelize with Promise.allSettled if needed.
    for (const name of players) {
      try {
        // 1) Search for player by name
        const results = await fotmob.search(name);
        const best = (results?.players && results.players[0]) || null;
        if (!best?.id) { out[name] = toFantasyStat(name, null); continue; }
        // 2) Get player data (season aggregates are typically present)
        const pdata = await fotmob.player(best.id);
        // Try to pick the 2025/26 season aggregates if available
        const seasonAgg = pdata?.stats?.seasons?.find?.(s => String(s.season).includes('2025')) || pdata?.stats;
        out[name] = toFantasyStat(name, seasonAgg || pdata);
      } catch (e) {
        console.error('FotMob fetch failed for', name, e.message);
        out[name] = toFantasyStat(name, null);
      }
    }

    res.json(out);
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'server_error' });
  }
});

app.listen(PORT, () => console.log(`API listening on http://localhost:${PORT}`));
```

Package.json (ESM) – save as package.json
```json
{
  "name": "fantasy-fotmob-api",
  "type": "module",
  "private": true,
  "scripts": {
    "dev": "node server.js"
  },
  "dependencies": {
    "@max-xoo/fotmob": "^2.4.1",
    "cors": "^2.8.5",
    "express": "^4.19.2",
    "express-rate-limit": "^7.1.5"
  }
}