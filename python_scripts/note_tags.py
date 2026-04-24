#!/usr/bin/env python3
"""
note_tags.py - Shared tag extraction and indexing for notes

Provides tag support for nlist and nlist2:
- Extract hashtags from markdown files
- Build and cache tag index with mtime-based invalidation
- Query tags efficiently
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


class TagManager:
    """Manages tag extraction and indexing for markdown notes"""

    def __init__(self, notes_dir: Path, cache_file: Optional[Path] = None):
        self.notes_dir = notes_dir
        self.cache_file = cache_file or (notes_dir.parent / '.note_tags_cache.json')

    def extract_tags_from_content(self, content: str) -> Set[str]:
        """
        Extract hashtags from markdown content.

        Rules:
        - Must start with # followed immediately by word characters (no space)
        - Not a heading (headings have space after #)
        - Ignore code blocks, inline code, and markdown link targets
        - Returns lowercase tag names without the #

        Examples:
        - "# Heading" -> not a tag (has space)
        - "#food" -> tag: "food"
        - "#food/italian" -> tag: "food/italian" (nested)
        - "some text #recipe and #cooking" -> tags: "recipe", "cooking"
        """
        tags = set()

        # Pre-filter content to avoid false positives
        # - Strip fenced code blocks and inline code
        # - Strip markdown link targets so anchors like (#heading) aren't treated as tags
        content = re.sub(r"```[\s\S]*?```", "", content)
        content = re.sub(r"~~~[\s\S]*?~~~", "", content)
        content = re.sub(r"`[^`]*`", "", content)
        content = re.sub(r"\]\([^)]*\)", "]", content)

        # Then remove lines that are headings (# followed by space)
        lines = content.split('\n')
        non_heading_lines = []
        for line in lines:
            # Skip lines that are markdown headings
            if not re.match(r'^\s*#+\s', line):
                non_heading_lines.append(line)

        filtered_content = '\n'.join(non_heading_lines)

        # Now extract hashtags: # followed immediately by word chars
        # Support nested tags with slashes: #food/italian
        pattern = r'#([\w]+(?:/[\w]+)*)'
        matches = re.findall(pattern, filtered_content)

        # Normalize to lowercase
        tags = {tag.lower() for tag in matches}

        return tags

    def extract_tags_from_file(self, filepath: Path) -> Set[str]:
        """Extract all tags from a markdown file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.extract_tags_from_content(content)
        except Exception:
            return set()

    def get_all_md_files(self) -> List[Path]:
        """Get all .md files in the notes directory"""
        # Search recursively so tags in subfolders are included
        return [f for f in self.notes_dir.rglob('*.md') if f.is_file()]

    def build_tag_index(self, files: Optional[List[Path]] = None) -> Tuple[Dict[str, List[str]], Dict[str, float]]:
        """
        Build complete tag index from scratch.

        Returns:
            (tag_index, file_mtimes)
            tag_index: {tag: [filename1, filename2, ...]}
            file_mtimes: {filename: mtime}
        """
        if files is None:
            files = self.get_all_md_files()

        tag_index = {}
        file_mtimes = {}

        for filepath in files:
            filename = filepath.name
            mtime = filepath.stat().st_mtime
            file_mtimes[filename] = mtime

            tags = self.extract_tags_from_file(filepath)

            for tag in tags:
                if tag not in tag_index:
                    tag_index[tag] = []
                tag_index[tag].append(filename)

        return tag_index, file_mtimes

    def load_cache(self) -> Optional[Dict]:
        """Load tag cache from disk"""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def save_cache(self, tag_index: Dict[str, List[str]], file_mtimes: Dict[str, float]) -> None:
        """Save tag cache to disk"""
        cache = {
            'tag_index': tag_index,
            'file_mtimes': file_mtimes
        }

        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            # Cache save failure is non-fatal
            pass

    def get_tag_index(self) -> Dict[str, List[str]]:
        """
        Get tag index, using cache if valid or rebuilding if needed.

        Uses mtime-based cache invalidation:
        - Loads cache if it exists
        - Checks each file's mtime against cached mtime
        - Only re-scans files that changed
        - Rebuilds completely if cache missing

        Returns:
            {tag: [filename1, filename2, ...]}
        """
        cache = self.load_cache()
        current_files = {f.name: f for f in self.get_all_md_files()}

        if cache is None:
            # No cache - build from scratch
            tag_index, file_mtimes = self.build_tag_index(list(current_files.values()))
            self.save_cache(tag_index, file_mtimes)
            return tag_index

        # Have cache - check for changes
        tag_index = cache.get('tag_index', {})
        cached_mtimes = cache.get('file_mtimes', {})
        needs_update = False

        # Check for modified or new files
        files_to_rescan = []
        for filename, filepath in current_files.items():
            current_mtime = filepath.stat().st_mtime
            cached_mtime = cached_mtimes.get(filename)

            if cached_mtime is None or current_mtime != cached_mtime:
                # File is new or modified
                files_to_rescan.append(filepath)
                needs_update = True

        # Check for deleted files
        for cached_filename in list(cached_mtimes.keys()):
            if cached_filename not in current_files:
                # File was deleted - remove from index
                for tag in list(tag_index.keys()):
                    if cached_filename in tag_index[tag]:
                        tag_index[tag].remove(cached_filename)
                        # Remove tag if no files left
                        if not tag_index[tag]:
                            del tag_index[tag]
                del cached_mtimes[cached_filename]
                needs_update = True

        # Re-scan modified/new files
        if files_to_rescan:
            for filepath in files_to_rescan:
                filename = filepath.name
                mtime = filepath.stat().st_mtime

                # Remove old entries for this file from all tags
                for tag in list(tag_index.keys()):
                    if filename in tag_index[tag]:
                        tag_index[tag].remove(filename)
                        if not tag_index[tag]:
                            del tag_index[tag]

                # Add new entries
                tags = self.extract_tags_from_file(filepath)
                for tag in tags:
                    if tag not in tag_index:
                        tag_index[tag] = []
                    tag_index[tag].append(filename)

                # Update mtime
                cached_mtimes[filename] = mtime

        # Save updated cache if anything changed
        if needs_update:
            self.save_cache(tag_index, cached_mtimes)

        return tag_index

    def get_all_tags_with_counts(self) -> List[Tuple[str, int]]:
        """
        Get all tags with their file counts, sorted by count (descending).

        Returns:
            [(tag, count), ...]
        """
        tag_index = self.get_tag_index()
        tags_with_counts = [(tag, len(files)) for tag, files in tag_index.items()]
        # Sort by count (descending), then by tag name
        tags_with_counts.sort(key=lambda x: (-x[1], x[0]))
        return tags_with_counts

    def get_files_by_tags(self, tags: List[str], match_all: bool = False) -> Set[str]:
        """
        Get files that match the given tags.

        Args:
            tags: List of tag names to search for
            match_all: If True, return files with ALL tags (AND logic)
                      If False, return files with ANY tag (OR logic)

        Returns:
            Set of filenames
        """
        tag_index = self.get_tag_index()

        # Normalize tags to lowercase
        tags = [t.lower() for t in tags]

        if not tags:
            return set()

        if match_all:
            # AND logic - files must have all tags
            result = None
            for tag in tags:
                files = set(tag_index.get(tag, []))
                if result is None:
                    result = files
                else:
                    result = result.intersection(files)
            return result or set()
        else:
            # OR logic - files with any tag
            result = set()
            for tag in tags:
                result.update(tag_index.get(tag, []))
            return result
