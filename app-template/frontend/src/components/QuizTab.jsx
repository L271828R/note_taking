import React, { useEffect, useState } from 'react';
import QuestionCard from './QuestionCard';
import Feedback from './Feedback';
import { fetchQuestions, submitAttempt } from '../api';

export default function QuizTab() {
  const [questions, setQuestions] = useState([]);
  const [qIndex, setQIndex] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchQuestions()
      .then(setQuestions)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(selected) {
    const q = questions[qIndex];
    try {
      const res = await submitAttempt(q.id, selected);
      setResult({ ...res, selected });
    } catch (e) {
      setError(e.message);
    }
  }

  function handleNext() {
    setResult(null);
    setQIndex(i => (i + 1) % questions.length);
  }

  if (loading) return <div className="status-msg">Loading questions…</div>;
  if (error) return <div className="status-msg error">{error}</div>;
  if (questions.length === 0) return <div className="status-msg">No questions found.</div>;

  const question = questions[qIndex];

  return (
    <div className="quiz-tab">
      <div className="question-section">
        <div className="q-counter">Question {qIndex + 1} of {questions.length}</div>
        <QuestionCard
          question={question}
          onSubmit={handleSubmit}
          answered={!!result}
        />
        {result && (
          <Feedback
            isCorrect={result.is_correct}
            correct={result.correct}
            explanation={result.explanation}
            selected={result.selected}
            onNext={handleNext}
          />
        )}
      </div>
    </div>
  );
}
