import React, { useState } from 'react';
import QuizTab from './components/QuizTab';
import ExplanationTab from './components/ExplanationTab';
import ReportView from './components/ReportView';

const TABS = ['Quiz', 'Explanation', 'Report'];

export default function App() {
  const [activeTab, setActiveTab] = useState('Quiz');

  return (
    <div className="app">
      <header className="app-header">
        <h1>APP_NAME</h1>
        <nav className="tab-nav">
          {TABS.map(tab => (
            <button
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>
      </header>
      <main className="app-main">
        {activeTab === 'Quiz' && <QuizTab />}
        {activeTab === 'Explanation' && <ExplanationTab />}
        {activeTab === 'Report' && <ReportView />}
      </main>
    </div>
  );
}
