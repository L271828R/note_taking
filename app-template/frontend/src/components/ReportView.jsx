import React, { useEffect, useState } from 'react';
import { fetchAttempts, clearAttempts } from '../api';

const fmt = ts =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'short',
    timeStyle: 'short'
  }).format(new Date(ts));

export default function ReportView() {
  const [attempts, setAttempts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  function load() {
    setLoading(true);
    fetchAttempts()
      .then(setAttempts)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleClear() {
    if (!confirm('Clear all attempt history?')) return;
    await clearAttempts();
    load();
  }

  if (loading) return <div className="status-msg">Loading report…</div>;
  if (error) return <div className="status-msg error">{error}</div>;

  const total = attempts.length;
  const correct = attempts.filter(a => a.is_correct).length;
  const pct = total ? Math.round((correct / total) * 100) : 0;

  return (
    <div className="report-view">
      <div className="report-header">
        <h2>Attempt History</h2>
        <div className="report-actions">
          <button className="refresh-btn" onClick={load}>Refresh</button>
          {total > 0 && (
            <button className="clear-btn" onClick={handleClear}>Clear History</button>
          )}
        </div>
      </div>

      {total === 0 ? (
        <p className="status-msg">No attempts yet. Go to the Quiz tab to start!</p>
      ) : (
        <>
          <div className="summary-bar">
            <span>{total} attempt{total !== 1 ? 's' : ''}</span>
            <span className="summary-sep">·</span>
            <span className="correct-count">{correct} correct</span>
            <span className="summary-sep">·</span>
            <span className={`pct ${pct >= 70 ? 'pass' : 'fail'}`}>{pct}%</span>
          </div>

          <div className="table-wrap">
            <table className="attempts-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Question</th>
                  <th>Selected</th>
                  <th>Correct</th>
                  <th>Result</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((a, i) => (
                  <tr key={a.id} className={a.is_correct ? 'row-correct' : 'row-incorrect'}>
                    <td>{total - i}</td>
                    <td className="q-text-cell">{a.question_text.split('\n')[0]}</td>
                    <td className="center">{a.selected.toUpperCase()}</td>
                    <td className="center">{a.correct.toUpperCase()}</td>
                    <td className="center">
                      <span className={`badge ${a.is_correct ? 'badge-pass' : 'badge-fail'}`}>
                        {a.is_correct ? 'Pass' : 'Fail'}
                      </span>
                    </td>
                    <td className="time-cell">{fmt(a.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
