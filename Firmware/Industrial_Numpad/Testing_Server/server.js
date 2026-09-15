const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;
const DATA_FILE = path.join(__dirname, 'missions.json');

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ---------- Helpers ----------
function loadMissions() {
  if (!fs.existsSync(DATA_FILE)) return [];
  try {
    const raw = fs.readFileSync(DATA_FILE, 'utf8');
    return JSON.parse(raw);
  } catch (err) {
    console.error('Failed to read missions.json:', err);
    return [];
  }
}

function saveMissions(missions) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(missions, null, 2));
}

// ---------- Routes ----------

// ESP32 posts here when 'D' stores a completed task
app.post('/api/missions', (req, res) => {
  const { task, description, timestamp } = req.body;

  if (!task) {
    return res.status(400).json({ error: 'Missing required field: task' });
  }

  const missions = loadMissions();
  const newMission = {
    id: missions.length > 0 ? missions[missions.length - 1].id + 1 : 1,
    task,
    description: description || '',
    device_timestamp: timestamp || null,   // millis() from ESP32, not real time
    received_at: new Date().toISOString()  // real server time
  };

  missions.push(newMission);
  saveMissions(missions);

  console.log('Stored mission:', newMission);
  res.status(201).json({ success: true, mission: newMission });
});

// Browser / dashboard fetches all stored missions
app.get('/api/missions', (req, res) => {
  const missions = loadMissions();
  res.json(missions);
});

// Optional: clear all data (handy for testing)
app.delete('/api/missions', (req, res) => {
  saveMissions([]);
  res.json({ success: true, message: 'All missions cleared' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Mission server running at http://0.0.0.0:${PORT}`);
  console.log(`View dashboard in browser at http://<this-computer-IP>:${PORT}`);
});
