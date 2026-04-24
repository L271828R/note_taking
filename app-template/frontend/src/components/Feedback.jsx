import React from 'react';

export default function Feedback({ isCorrect, correct, explanation, onNext }) {
  return (
    <div className={`feedback ${isCorrect ? 'correct' : 'incorrect'}`}>
      <div className="feedback-header">
        {isCorrect ? '✓ Correct!' : `✗ Incorrect — the right answer is ${correct.toUpperCase()}`}
      </div>
      <p className="feedback-explanation">{explanation}</p>
      <button className="next-btn" onClick={onNext}>
        Next Question
      </button>
    </div>
  );
}
