"""
Shared tips library for the notes CLI app.
Prints a random tip if tips are enabled in .config/settings.ini
"""

import configparser
import os
import random
from pathlib import Path

TIPS = [
    "💡 nl -tag <tag>          Filter notes by hashtag (e.g. nl -tag python)",
    "💡 nl -tags               List all tags with counts in the current folder",
    "💡 nl -delete <N>         Move note #N to /tmp/notes/delete (soft delete)",
    "💡 nl -rename <N> <name>  Rename note #N to a new filename",
    "💡 nl -rename <N> -style date  Prefix note #N with today's date",
    "💡 nl -move <N> <folder>  Move note #N into a subfolder (partial match ok)",
    "💡 nl -move <N> ..        Move note #N up one folder level",
    "💡 nc                     List subfolders in current folder",
    "💡 nc <N>                 Enter subfolder #N",
    "💡 nc ..                  Go up one folder level",
    "💡 nc root                Jump back to the vault root",
    "💡 nc -new <name>         Create a new subfolder under current",
    "💡 nc -rename <N> <name>  Rename subfolder #N",
    "💡 nc -move <N> -to <M>   Move subfolder #N into subfolder #M",
    "💡 nc -move <N> -to up    Move subfolder #N up one level",
    "💡 nc -pwd                Print the current folder path",
    "💡 no <N>                 Open note #N in your editor (or run app #N)",
    "💡 nn <name>              Create or open a note by name",
    "💡 ns                     Fuzzy-find notes across the vault",
    "💡 nc -claude             Open Claude with the full app context loaded",
]


def _tips_enabled() -> bool:
    config_path = Path(os.getenv("NOTES_PATH", "")) / ".config" / "settings.ini"
    if not config_path.exists():
        return True  # default on if no config found
    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    return cfg.getboolean("tips", "enabled", fallback=True)


def print_tip() -> None:
    if _tips_enabled():
        print(random.choice(TIPS))
