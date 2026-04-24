export async function fetchQuestions() {
  const res = await fetch('/api/questions');
  if (!res.ok) throw new Error('Failed to load questions');
  return res.json();
}

export async function submitAttempt(question_id, selected) {
  const res = await fetch('/api/attempts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id, selected })
  });
  if (!res.ok) throw new Error('Failed to submit attempt');
  return res.json();
}

export async function fetchAttempts() {
  const res = await fetch('/api/attempts');
  if (!res.ok) throw new Error('Failed to load attempts');
  return res.json();
}

export async function clearAttempts() {
  const res = await fetch('/api/attempts', { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to clear attempts');
  return res.json();
}
