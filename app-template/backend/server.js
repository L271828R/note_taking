const express = require('express');
const cors = require('cors');
const path = require('path');
const { seed } = require('./db');

const app = express();
const PORT = 3000; // <-- change this per app

app.use(cors());
app.use(express.json());

// API routes
app.use('/api/questions', require('./routes/questions'));
app.use('/api/attempts', require('./routes/attempts'));

// Serve built frontend
const DIST = path.join(__dirname, '..', 'frontend', 'dist');
app.use(express.static(DIST));
app.get('*', (req, res) => {
  res.sendFile(path.join(DIST, 'index.html'));
});

seed();

app.listen(PORT, () => {
  console.log(`App running at http://localhost:${PORT}`);
});
