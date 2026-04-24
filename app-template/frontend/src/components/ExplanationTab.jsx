import React from 'react';

export default function ExplanationTab() {
  return (
    <div className="explanation-tab">
      <h2>Topic Name</h2>

      <section>
        <h3>What is it?</h3>
        <p>
          Replace this with a clear explanation of the topic being tested.
        </p>
      </section>

      <section>
        <h3>Key Rules</h3>
        <div className="key-rule">
          Highlight the most important rule or concept here.
        </div>
      </section>
    </div>
  );
}
