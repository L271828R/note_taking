import React, { useState, useEffect } from 'react';

const OPTION_KEYS = ['a', 'b', 'c', 'd'];

export default function QuestionCard({ question, onSubmit, answered }) {
  const [selected, setSelected] = useState(null);

  useEffect(() => { setSelected(null); }, [question.id]);

  function handleSubmit(e) {
    e.preventDefault();
    if (!selected || answered) return;
    onSubmit(selected);
  }

  return (
    <form className="question-card" onSubmit={handleSubmit}>
      <p className="question-text">{question.text}</p>
      <div className="options">
        {OPTION_KEYS.map(key => (
          <label
            key={key}
            className={`option-label ${selected === key ? 'selected' : ''} ${answered ? 'disabled' : ''}`}
          >
            <input
              type="radio"
              name="answer"
              value={key}
              checked={selected === key}
              onChange={() => !answered && setSelected(key)}
              disabled={answered}
            />
            <span className="option-letter">{key.toUpperCase()})</span>
            <span>{question[`option_${key}`]}</span>
          </label>
        ))}
      </div>
      {!answered && (
        <button type="submit" className="submit-btn" disabled={!selected}>
          Submit Answer
        </button>
      )}
    </form>
  );
}
