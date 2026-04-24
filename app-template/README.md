# APP_NAME

> One-line description of what this app does.

## Stack

- **Backend**: Node.js + Express + better-sqlite3
- **Frontend**: React + Vite (built and served from backend)
- **Port**: 3000 (change in `run.sh` and `backend/server.js`)

## Run

```bash
./run.sh
```

Then open http://localhost:3000

## Structure

```
app-name/
├── run.sh              # entry point — installs deps, builds, starts server
├── README.md
├── backend/
│   ├── server.js       # Express server, serves API + built frontend
│   ├── db.js           # SQLite setup, schema, seed data
│   ├── package.json
│   ├── routes/
│   │   ├── questions.js
│   │   └── attempts.js
│   └── data/           # quiz.db lives here (git-ignored)
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        ├── components/
        │   ├── QuizTab.jsx
        │   ├── QuestionCard.jsx
        │   ├── Feedback.jsx
        │   ├── ReportView.jsx
        │   └── ExplanationTab.jsx
        └── styles/
            └── index.css
```

## Adding questions

Edit `backend/db.js` — add entries to the `questions` array inside `seed()`.

Each question:
```js
[
  id,          // integer, unique
  text,        // question body (supports \n)
  option_a,
  option_b,
  option_c,
  option_d,
  correct,     // 'a' | 'b' | 'c' | 'd'
  explanation, // shown after answering
  diagram      // JSON string or null
]
```
