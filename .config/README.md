# Notes App — Context for Claude

This is a personal knowledge management CLI app modelled after Obsidian, but
operated entirely from the terminal. Notes are Markdown files. The app also
supports runnable **Apps** (mini web or CLI tools) that live alongside notes.

---

## How the app works

### Vault location

All notes and folders live under:

```
$NOTES_FOLDERS_PATH   →   /Users/luisrueda/Dropbox/notes/folders/
```

### Working directory — the `current` file

**This is the most important concept.**

The app tracks a "current folder" in a plain-text file:

```
$NOTES_CURRENT_FILE   →   /Users/luisrueda/projects/notes/current
```

This file contains a single relative path, e.g.:

```
3_resources/QA_Career/ISQB/2-level-boundary
```

Every command (`nl`, `no`, `nn`, `nc`) operates on:

```
$NOTES_FOLDERS_PATH / <contents of current file>
```

It works like a shell's `$PWD`, but persisted in a file so it survives
across terminal sessions. It is **not** the shell's working directory.

**Rule for Claude: any file, note, or app you create must be placed inside
the folder that `current` points to, not wherever the shell happens to be.**

To read the current working folder at any time:

```bash
nc -pwd
# or
cat $NOTES_CURRENT_FILE
```

---

## CLI commands

| Alias | Script | What it does |
|-------|--------|--------------|
| `nl`  | `nlist` | List notes and apps in the current folder |
| `no`  | `nopen` | Open note or run app by number from `nl` output |
| `nn`  | `nnote` | Create or open a note |
| `nc`  | `ncurrent` | Navigate folders (like `cd` for the notes vault) |
| `ns`  | `nfzf` | Fuzzy-find notes |
| `nl2` | `nlist2` | Interactive curses note selector |

### nc navigation

```bash
nc              # list subfolders of current folder
nc 3            # enter subfolder #3
nc -cd <name>   # enter subfolder by name
nc ..           # go up one level
nc root         # go back to vault root
nc -pwd         # print current folder path
nc -new <name>  # create a new subfolder
nc -claude      # print this README (context for Claude)
```

---

## Apps

Apps are runnable tools (web apps, CLI utilities, etc.) that live inside an
`apps/` subfolder within any notes folder.

### Structure

```
<current folder>/
├── apps/
│   └── <app-name>/
│       ├── run.sh       ← required: entry point
│       └── ...          ← app source files
└── some-note.md
```

### Rules

- Every app **must** have a `run.sh` at its root.
- `run.sh` must self-locate using `ROOT="$(cd "$(dirname "$0")" && pwd)"` so
  it works regardless of where it is called from.
- `nl` lists apps in a dedicated `🚀 Apps` section, numbered alongside notes.
- `no <N>` runs the app if entry N is an app; opens nvim if it is a note.
- The `apps/` folder is **not** shown as a subfolder in `nl` — it is treated
  as an application container, not a note folder.
- App names are derived from the folder name: `bva-quiz` → `BVA Quiz`.

### Creating an app

When asked to create an app:

1. Read `current` to find the working folder.
2. Create the app under `$NOTES_FOLDERS_PATH/<current>/apps/<app-name>/`.
3. Always include a `run.sh` entry point.
4. Always include a `README.md`.
5. Use a self-contained tech stack (the app must start with `./run.sh`).

### Example

```
current → 3_resources/QA_Career/ISQB/2-level-boundary

App lives at:
  /Users/luisrueda/Dropbox/notes/folders/
    3_resources/QA_Career/ISQB/2-level-boundary/
      apps/
        bva-quiz/
          run.sh
          README.md
          backend/
          frontend/
```

---

## Notes structure

Each Markdown note may contain:

- `<!-- id: <8-char hex> -->` — unique ID injected at creation (first line)
- `# Title: <title>` — title shown in `nl` listings
- `#tag` inline hashtags — used for `nl -tag <tag>` filtering

Notes are created from a template at:
```
/Users/luisrueda/projects/notes/templates/default.md
```

---

## File locations reference

| Purpose | Path |
|---------|------|
| Vault root | `$NOTES_FOLDERS_PATH` → `/Users/luisrueda/Dropbox/notes/folders/` |
| Current folder pointer | `$NOTES_CURRENT_FILE` → `/Users/luisrueda/projects/notes/current` |
| Listing output (for `no`) | `$NOTES_RESULTS_FILE` → `/Users/luisrueda/projects/notes/results.txt` |
| Note ID map | `$NOTES_PATH/.note_map.json` |
| CLI scripts | `/Users/luisrueda/projects/notes/bin_/` |
| Python scripts | `/Users/luisrueda/projects/notes/python_scripts/` |
| This file | `/Users/luisrueda/projects/notes/.config/README.md` |
