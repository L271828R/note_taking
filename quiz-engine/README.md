# quiz-engine

Central quiz engines used by all topic quiz apps. Never edit these for
topic-specific reasons — improvements here benefit every quiz app at once.

## Files

| File | Purpose |
|------|---------|
| `react-quiz.html` | Browser quiz (React, no build step). Reads `questions.json` via HTTP. |
| `flappy-quiz.py`  | Pygame Flappy-Bird quiz. Reads `questions.json` from disk. |

## questions.json format

Each quiz app keeps its own `questions.json`. The engines accept:

```json
{
  "title": "My Topic",
  "questions": [
    {
      "topic": "Sub-topic label (optional)",
      "q": "Question text",
      "opts": ["Option A", "Option B", "Option C", "Option D"],
      "a": 0,
      "exp": "Explanation shown after answering (optional)"
    }
  ]
}
```

A plain array `[{ ... }, ...]` is also accepted (title defaults to "Quiz").

## Running directly

```bash
# React (served via the app's run.sh, which handles the HTTP shim)

# Pygame
python3 flappy-quiz.py --bank /path/to/questions.json
python3 flappy-quiz.py --bank /path/to/questions.json --title "Override Title"
```

## Creating a new quiz app

Use `/quiz-app` in Claude Code — it reads the current notes folder,
generates a `questions.json` from the note content, and scaffolds the app.

Or copy the template manually:
```
/Users/luisrueda/projects/notes/templates/quiz-app/apps/quiz-app/
```
