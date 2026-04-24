const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DATA_DIR = path.join(__dirname, 'data');
const DB_PATH = path.join(DATA_DIR, 'quiz.db');
let db;

function getDb() {
  if (!db) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    initSchema();
  }
  return db;
}

function initSchema() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS questions (
      id          INTEGER PRIMARY KEY,
      text        TEXT NOT NULL,
      option_a    TEXT NOT NULL,
      option_b    TEXT NOT NULL,
      option_c    TEXT NOT NULL,
      option_d    TEXT NOT NULL,
      correct     TEXT NOT NULL,
      explanation TEXT NOT NULL,
      diagram     TEXT
    );

    CREATE TABLE IF NOT EXISTS attempts (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      question_id INTEGER NOT NULL REFERENCES questions(id),
      selected    TEXT NOT NULL,
      correct     TEXT NOT NULL,
      is_correct  INTEGER NOT NULL,
      timestamp   TEXT NOT NULL
    );
  `);
}

function seed() {
  const db = getDb();

  const upsert = db.prepare(`
    INSERT INTO questions (id, text, option_a, option_b, option_c, option_d, correct, explanation, diagram)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      text=excluded.text, option_a=excluded.option_a, option_b=excluded.option_b,
      option_c=excluded.option_c, option_d=excluded.option_d, correct=excluded.correct,
      explanation=excluded.explanation, diagram=excluded.diagram
  `);

  const questions = [
    // Add your questions here:
    // [id, text, option_a, option_b, option_c, option_d, correct, explanation, diagram_json_or_null]
  ];

  for (const q of questions) {
    upsert.run(...q);
  }
}

module.exports = { getDb, seed };
