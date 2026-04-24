<!-- id: cb511a84 -->
last updated: 2025-04-18 14:44:30

# Notes & Journal Management System

A lightweight, Git‑backed note‑taking and journaling system using Bash scripts and a Neovim helper plugin.  
All notes live under a “vault” directory with automated ID injection, JSON mapping, backlinking, visit‑tracking, and logging.

---

## Requirements

### Homebrew

• marksman  
• luarocks  
• jq  
• fzf (for `nfzf`, interactive file selection)

### LuaRocks

• lua‑cjson

### Neovim Plugins

• wbthomason/packer.nvim  
• MeanderingProgrammer/render-markdown.nvim  
• dhruvasagar/vim-table-mode  
• nvim-treesitter/nvim-treesitter  
• ibhagwan/fzf-lua  
• echasnovski/mini.nvim (optional)  
• tpope/vim-repeat

---

## Environment Variables

    export NOTES_PATH=~/projects/notes  
    export NOTES_FOLDERS_PATH=~/projects/notes/folders  
    export NOTES_CURRENT_FILE=~/projects/notes/current  
    export NOTES_RESULTS_FILE=~/projects/notes/results.txt  
    export NOTES_LUA=~/projects/notes/nvim-lua  
    export PATH="$NOTES_PATH/bin_:$PATH"

---

## Directory Layout

    .  
    ├── bin_  
    │   ├── ncurrent  
    │   ├── nnote  
    │   ├── nlist  
    │   ├── nfzf        # new: fuzzy finder launcher  
    │   ├── sync-map.sh  
    │   ├── resync_with_backlinks.sh  
    │   └── ...  
    ├── current  
    ├── folders  
    │   ├── c_programming  
    │   │   ├── 2025-04-06.md  
    │   │   ├── dirent.md  
    │   │   └── some_new_note_about_c_programming.md  
    │   ├── journal  
    │   │   ├── 2025-04-07.md  
    │   │   ├── day2.md  
    │   │   └── ...  
    │   └── ...  
    ├── .note_map.json  
    └── .note_map.log

---

## Features

1. **Automatic ID Injection**  
   • On note creation or first save, a unique 8‑hex ID is injected as `<!-- id: xxxxxxxx -->` at the top.  
   • Malformed or nested IDs are detected and corrected during resync.

2. **JSON Map File**  
   • `.note_map.json` stores `{ id: { path, title, last_visited? } }`.  
   • Pretty‑printed via `python3 -m json.tool` if available, or compact otherwise.  
   • Updated on every note save, folder rename, or move.

3. **Visit Tracking**  
   • Each time you open a note via `nnote_open.sh` (or `nfzf`), its `last_visited` timestamp is recorded in the map.  
   • Allows you to see recently worked‑on notes at a glance.

4. **Logging**  
   • All operations logged to `.note_map.log` with timestamps.  
   • Includes plugin loads, map updates, ID injections, resync passes, backlink injections, etc.

5. **Backlink Injection**  
   • `resync_with_backlinks.sh` rebuilds the map, fixes IDs, scans `[[id|Title]]` links, and injects a “#### Backlinks:” section listing all incoming links.  
   • Backlinks formatted as ` - [[SRC_ID|SRC_TITLE]]`.

6. **Neovim Plugin (`nvim-notes-macros.lua`)**  
   • `:InsertLink` to search notes via fzf‑lua and insert `[[id|Title]]`.  
   • `:InsertIDs` to batch‑inject missing IDs.  
   • `:GoToLinkedNote` jumps to an outgoing link under cursor.  
   • Autocmd on `BufWritePost` for `.md` under vault: updates map and injects missing IDs.  
   • Autocmd on `BufWritePre` updates a `last updated:` timestamp.  
   • Keybindings: `<leader>ln` for InsertLink, `<leader>gf` for GoToLinkedNote.

7. **Command‑Line Tools**

   **ncurrent**  
   • Manages “current” folder pointer.  
   • Navigate (`-cd`, `-up`), list folders with file counts, create, rename, move.  
   • Updates JSON map when moving or renaming folders.

   **nnote**  
   • Creates or opens a note in the current folder.  
   • Copies from a default template and auto‑injects an ID if missing.

   **nlist**  
   • Lists `.md` files in current folder, annotating with title and timestamp.  
   • Saves output to `$NOTES_RESULTS_FILE`.

   **nfzf**  
   • Launches an interactive `fzf` over all notes under `$NOTES_FOLDERS_PATH`.  
   • Displays paths relative to the vault root.  
   • Opens the selected note in Neovim.

   **sync-map.sh**  
   • Rebuilds `.note_map.json` from scratch.  
   • Fixes malformed IDs.  
   • Pretty‑prints and sorts map.

   **resync_with_backlinks.sh**  
   • Extends sync‑map: also builds backlink index and injects backlinks into notes.  
   • Logs every step and reports which files were updated.

---

## Linking Documents

### Overview

This system uses wiki‑style links to connect notes together, similar to Obsidian or Roam Research.
Links use the format `[[id|Title]]` where `id` is an 8‑character hexadecimal identifier and `Title` is the note's title.

### Link Format

    [[8177407c|Trees are a popular data structure in algorithms]]
    [[14ba882b|Today I created a nice little note taking app.]]

### How to Link Documents (Step‑by‑Step)

#### Method 1: Using Neovim (Recommended)

1. **Open a note in Neovim**
   ```bash
   nnote my_note.md
   ```

2. **Insert a link interactively**
   - Position your cursor where you want to insert the link
   - Press `<leader>ln` (if your `<leader>` is spacebar, press `Space` then `ln`)
   - Choose a search mode:
     - Press `c` or `Enter` for **content search** (searches inside note text)
     - Press `f` for **filename search** (searches by file paths)
     - Press `t` for **titles search** (searches note titles)

3. **Select the target note**
   - Type to fuzzy‑search through your notes
   - Use arrow keys or `Ctrl‑j`/`Ctrl‑k` to navigate
   - Press `Enter` to select

4. **The link is inserted automatically**
   ```markdown
   [[8177407c|Trees are a popular data structure in algorithms]]
   ```

5. **Save the file**
   ```
   :w
   ```
   The `.note_map.json` updates automatically via Neovim hooks.

#### Method 2: Manual Linking

1. **Find the target note's ID**
   - Open the target note and look at the top:
     ```markdown
     <!-- id: 8177407c -->
     ```

2. **Copy the title from the same note**
   ```markdown
   # Title: Trees are a popular data structure in algorithms
   ```

3. **Insert the link manually**
   ```markdown
   [[8177407c|Trees are a popular data structure in algorithms]]
   ```

### Following Links

#### In Neovim

1. **Position cursor on any link**
   ```markdown
   [[8177407c|Trees are a popular data structure in algorithms]]
            ↑ cursor here
   ```

2. **Press `<leader>gf`** (e.g., `Space` then `gf` if spacebar is your leader key)
   - The target note opens in Neovim
   - If multiple links exist in the same file, you'll see a menu to choose from

#### From Command Line

1. **Look up the note ID in `.note_map.json`**
   ```bash
   cat .note_map.json | jq '.["8177407c"]'
   ```
   Output:
   ```json
   {
     "path": "folders/ideas/2025-04-17-7da88e.md",
     "title": "Trees are a popular data structure in algorithms"
   }
   ```

2. **Open the note**
   ```bash
   nvim folders/ideas/2025-04-17-7da88e.md
   ```

### Backlinks (Automatic Bi‑directional Links)

Backlinks show you which notes link **to** the current note (the reverse direction).

#### Generating Backlinks

Run the backlink sync script:
```bash
resync_with_backlinks.sh
```

This will:
1. Scan all `[[id|Title]]` links across all notes
2. Build an index of incoming links
3. Inject a "#### Backlinks:" section at the bottom of each note

#### Example

**Note A** (`folders/journal/2025-04-06.md`):
```markdown
<!-- id: 14ba882b -->

# Title: Today I created a nice little note taking app.

I think I like this. The reason is nvim is rendering syntax highlighting...

#### Backlinks:
 - [[ac08ea6d|Fire in the kitchen]]
 - [[56de8df0|Spend day improving this note app]]
```

This means:
- Two other notes link to this note
- One is titled "Fire in the kitchen" with ID `ac08ea6d`
- The other is titled "Spend day improving this note app" with ID `56de8df0`

### Complete Linking Workflow Example

**Scenario:** You're writing a note about algorithms and want to reference your note about binary trees.

1. **Open your current note**
   ```bash
   nnote algorithms_overview.md
   ```

2. **Write some content**
   ```markdown
   ## Tree‑based Algorithms

   Many efficient algorithms rely on tree structures.
   ```

3. **Add a link to your binary trees note**
   - Press `<leader>ln`
   - Press `c` for content search
   - Type "binary tree"
   - Select the note from results
   - Link appears: `[[b6bee5f7|Trees with more than one branch]]`

4. **Save and continue**
   ```
   :w
   ```

5. **Later, regenerate backlinks**
   ```bash
   resync_with_backlinks.sh
   ```

6. **Check the binary trees note**
   - It now has a backlink to `algorithms_overview.md`
   - You can see all notes that reference binary trees

### Search Mode Details

| Mode | Key | Searches | Best For |
|------|-----|----------|----------|
| **Content** | `c` | Full text inside notes | Finding notes by their content |
| **Filename** | `f` | File paths | Finding notes by file location |
| **Titles** | `t` | Note titles only | Finding notes by their `# Title:` line |

### Tips

- Use **content search** (`c`) when you remember what the note talks about
- Use **filename search** (`f`) when you remember the file name or folder
- Use **titles search** (`t`) when you remember the note's title
- Run `resync_with_backlinks.sh` periodically to keep backlinks up‑to‑date
- Backlinks are injected at file save automatically via Neovim hooks for the map, but the "#### Backlinks:" section requires manual sync

### Troubleshooting: New Notes Not Appearing in Title Search

**Problem:** You created a new note but it doesn't show up when searching by titles (`<leader>ln` → `t`).

**Cause:** This usually happens due to **duplicate IDs**. If multiple notes share the same ID, the map (`.note_map.json`) only keeps one entry, so the other notes won't appear in title searches.

**Solution:**

1. **Fix duplicate IDs:**
   ```bash
   python3 reseed-dups.py
   ```
   This script:
   - Finds all notes with duplicate IDs
   - Assigns new unique IDs to duplicates
   - Creates backups (`.bak` files) before making changes
   - Generates a report in `duplicate_id_changes.json`

2. **Rebuild the map:**
   ```bash
   python3 sync-map.py
   ```

3. **Verify the fix:**
   ```bash
   cat .note_map.json | python3 -m json.tool | grep -i "your note title"
   ```

**Why duplicates happen:**
- Copying notes manually
- Copying from templates that already have IDs
- File system operations outside of the `nnote` command

**Prevention:**
- Always use `nnote filename.md` to create new notes (auto-generates unique IDs)
- Avoid manually copying the `<!-- id: xxxxxxxx -->` line when creating notes from templates

---

## Usage Examples

1. **Switch Current Folder**
   - ncurrent
   - ncurrent 3

2. **Create/Open Note**
   - nnote meeting_notes.md

3. **List Notes**
   - nlist

4. **Fuzzy‑Find & Open**
   - nfzf

5. **Inject Missing IDs**
   - nvim --headless -c 'lua require("nvim-notes-macros").insert_ids()' +q

6. **Resync Map & Backlinks**
   - sync-map.sh
   - resync_with_backlinks.sh

---

## Sample ncurrent Output

> ncurrent

    current > journal  
    --------------------------  
    1. c_programming (2)       6. todo (1)  
    2. cli-apps (2)            7. tokens (1)  
    3. contacts (0)            8. trading (1)  
    4. journal (5)             9. work (4)  
    5. markdown-examples (1)   10. work-history (1)

---

## Sample Backlinks Injection

A note containing:

    [[14ba882b|Today I created a nice little note taking app.]]

will receive at its bottom:

#### Backlinks:
 - [[971109ef|original xxx]]

---

Enjoy a seamless, script‑driven note‑taking workflow with automatic linking, visit‑tracking, and history tracking!
