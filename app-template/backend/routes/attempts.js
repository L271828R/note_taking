const express = require('express');
const { getDb } = require('../db');
const router = express.Router();

router.post('/', (req, res) => {
  const { question_id, selected } = req.body;
  if (!question_id || !selected) {
    return res.status(400).json({ error: 'question_id and selected are required' });
  }

  const db = getDb();
  const question = db.prepare('SELECT * FROM questions WHERE id = ?').get(question_id);
  if (!question) return res.status(404).json({ error: 'Question not found' });

  const is_correct = selected === question.correct ? 1 : 0;
  const timestamp = new Date().toISOString();

  db.prepare(
    'INSERT INTO attempts (question_id, selected, correct, is_correct, timestamp) VALUES (?, ?, ?, ?, ?)'
  ).run(question_id, selected, question.correct, is_correct, timestamp);

  res.json({
    is_correct: is_correct === 1,
    correct: question.correct,
    explanation: question.explanation
  });
});

router.get('/', (req, res) => {
  const rows = getDb().prepare(`
    SELECT a.id, a.question_id, q.text as question_text,
           a.selected, a.correct, a.is_correct, a.timestamp
    FROM attempts a
    JOIN questions q ON q.id = a.question_id
    ORDER BY a.timestamp DESC
  `).all();
  res.json(rows);
});

router.delete('/', (req, res) => {
  getDb().prepare('DELETE FROM attempts').run();
  res.json({ ok: true });
});

module.exports = router;
