#!/usr/bin/env python3
"""
Note Graph Visualizer - Web server to visualize note relationships
Similar to Obsidian's graph view
Enhanced with text search and tag filtering
"""

import json
import os
import re
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

# Add python_scripts to path for imports
NOTES_PATH = os.getenv("NOTES_PATH", os.path.expanduser("~/projects/notes"))
sys.path.insert(0, os.path.join(NOTES_PATH, "python_scripts"))

from note_tags import TagManager

# Configuration
FOLDERS_PATH = os.getenv("NOTES_FOLDERS_PATH", os.path.join(NOTES_PATH, "folders"))
MAP_FILE = os.path.join(NOTES_PATH, ".note_map.json")
PORT = 8080


def load_note_map():
    """Load the note map JSON file"""
    if not os.path.exists(MAP_FILE):
        return {}
    with open(MAP_FILE, 'r') as f:
        return json.load(f)


def extract_links_from_file(filepath):
    """Extract all [[id|title]] or [[id]] links from a markdown file"""
    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

    # Match [[id|title]] or [[id]]
    link_pattern = r'\[\[([0-9a-f]+)(?:\|[^\]]+)?\]\]'
    links = re.findall(link_pattern, content)
    return links


def extract_note_id(filepath):
    """Extract the ID from a note file"""
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read first few lines to find ID
            for _ in range(5):
                line = f.readline()
                if not line:
                    break
                # Match <!-- id: xxxxxxxx -->
                match = re.search(r'<!--\s*id:\s*([0-9a-f]+)\s*-->', line)
                if match:
                    return match.group(1)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

    return None


def get_all_tags():
    """Get all tags across all notes with counts"""
    note_map = load_note_map()
    tag_counts = {}

    # Scan all notes in the map
    for note_id, info in note_map.items():
        path = info.get('path', '')
        full_path = os.path.join(NOTES_PATH, path)

        if os.path.exists(full_path):
            tags = extract_tags_from_file(full_path)
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort by count descending, then by tag name
    sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
    return [{'tag': tag, 'count': count} for tag, count in sorted_tags]


def extract_tags_from_file(filepath):
    """Extract Obsidian-style inline hashtags from a markdown file.

    Rules:
    - Only count inline hashtags like #tag or #parent/child
    - Ignore markdown headings (e.g., "# Title")
    - Ignore fenced code blocks and inline code to avoid capturing things like #include
    - Do NOT parse custom "# Tags:" sections
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Strip fenced code blocks and inline code
        content = re.sub(r"```[\s\S]*?```", "", content)
        content = re.sub(r"~~~[\s\S]*?~~~", "", content)
        content = re.sub(r"`[^`]*`", "", content)
        # Strip markdown link targets so anchors like (#heading) aren't treated as tags
        content = re.sub(r"\]\([^)]*\)", "]", content)

        # Exclude heading lines (# followed by space)
        lines = content.split('\n')
        non_heading_lines = [line for line in lines if not re.match(r'^\s*#+\s', line)]
        filtered_content = '\n'.join(non_heading_lines)

        tags = set()
        hashtag_pattern = r'#([\w]+(?:/[\w]+)*)'
        for m in re.findall(hashtag_pattern, filtered_content):
            tags.add(m.lower())

        return list(tags)
    except Exception:
        return []


def _tokenize_search(query: str):
    """Split query into tokens; support quoted phrases. Returns list of lowercased tokens."""
    tokens = []
    buf = ''
    in_quote = False
    for ch in query:
        if ch == '"':
            in_quote = not in_quote
            if not in_quote and buf:
                tokens.append(buf.strip().lower())
                buf = ''
        elif ch.isspace() and not in_quote:
            if buf:
                tokens.append(buf.strip().lower())
                buf = ''
        else:
            buf += ch
    if buf:
        tokens.append(buf.strip().lower())
    # Normalize tokens: drop leading '#' so users can search tags with #tag
    norm = []
    for t in tokens:
        if t.startswith('#'):
            t = t[1:]
        norm.append(t)
    return norm


def search_notes(query):
    """Search for notes by title, content, and tags using AND semantics across tokens.

    Supports quoted phrases: e.g., "machine learning" africa
    """
    note_map = load_note_map()
    results = []
    tokens = _tokenize_search(query)

    if not tokens:
        return list(note_map.keys())

    for note_id, info in note_map.items():
        title = info.get('title', 'Untitled')
        path = info.get('path', '')
        full_path = os.path.join(NOTES_PATH, path)

        haystack = title.lower()
        content = ''
        file_tags = []

        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                content = ''
            file_tags = extract_tags_from_file(full_path)

        # Combine searchable text: title + content + tags (space separated)
        combined = ' '.join([haystack, content.lower(), ' '.join(file_tags)])

        # All tokens must appear (AND)
        if all(tok in combined for tok in tokens):
            results.append(note_id)

    return results


def build_graph_data(search_query=None, filter_tags=None):
    """
    Build nodes and edges for the graph visualization

    Args:
        search_query: Text to search for in notes
        filter_tags: List of tags to filter by (OR logic)
    """
    note_map = load_note_map()

    nodes = []
    edges = []
    node_ids = set()

    # Determine which notes to include
    filtered_note_ids = None

    # Apply search filter
    if search_query:
        filtered_note_ids = set(search_notes(search_query))

    # Apply tag filter
    if filter_tags:
        # Scan all notes to find ones with matching tags
        tag_filtered_ids = set()
        filter_tags_lower = [t.lower() for t in filter_tags]

        for note_id, info in note_map.items():
            path = info.get('path', '')
            full_path = os.path.join(NOTES_PATH, path)

            if os.path.exists(full_path):
                note_tags = extract_tags_from_file(full_path)
                # Check if any of the filter tags match (OR logic)
                if any(tag in filter_tags_lower for tag in note_tags):
                    tag_filtered_ids.add(note_id)

        if filtered_note_ids is None:
            filtered_note_ids = tag_filtered_ids
        else:
            # Intersection of search and tag results
            filtered_note_ids = filtered_note_ids.intersection(tag_filtered_ids)

    # Build nodes from the map
    for note_id, info in note_map.items():
        # Skip if filtered out
        if filtered_note_ids is not None and note_id not in filtered_note_ids:
            continue

        title = info.get('title', 'Untitled')
        path = info.get('path', '')
        full_path = os.path.join(NOTES_PATH, path)

        # Extract tags for this note
        tags = []
        if os.path.exists(full_path):
            tags = extract_tags_from_file(full_path)

        nodes.append({
            'id': note_id,
            'label': title,
            'path': path,
            'title': title,  # For tooltip
            'tags': tags
        })
        node_ids.add(note_id)

    # Build edges by scanning files for links
    for note_id, info in note_map.items():
        # Skip if source node not in filtered set
        if note_id not in node_ids:
            continue

        path = info.get('path', '')
        full_path = os.path.join(NOTES_PATH, path)

        # Extract links from this note
        linked_ids = extract_links_from_file(full_path)

        for linked_id in linked_ids:
            # Only create edge if both nodes exist in filtered set
            if linked_id in node_ids and linked_id != note_id:
                edges.append({
                    'from': note_id,
                    'to': linked_id
                })

    return {'nodes': nodes, 'edges': edges}


def get_note_content(note_id):
    """Get the content of a note by its ID"""
    note_map = load_note_map()

    if note_id not in note_map:
        return None

    path = note_map[note_id].get('path', '')
    full_path = os.path.join(NOTES_PATH, path)

    if not os.path.exists(full_path):
        return None

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        title = note_map[note_id].get('title', 'Untitled')
        return {
            'id': note_id,
            'title': title,
            'path': path,
            'content': content
        }
    except Exception as e:
        print(f"Error reading note {note_id}: {e}")
        return None


class GraphRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the graph server"""

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        if path == '/':
            # Serve the main HTML page
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_html_page().encode())

        elif path == '/api/graph':
            # Serve graph data as JSON with optional filtering
            search_query = query_params.get('search', [None])[0]
            if search_query:
                search_query = unquote(search_query)

            filter_tags = query_params.get('tags', [None])[0]
            if filter_tags:
                filter_tags = [unquote(tag.strip()) for tag in filter_tags.split(',')]

            # Debug log
            print(f"/api/graph search={search_query!r} tags={filter_tags}")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            graph_data = build_graph_data(search_query, filter_tags)
            try:
                print(f" -> returning nodes={len(graph_data.get('nodes', []))} edges={len(graph_data.get('edges', []))}")
            except Exception:
                pass
            self.wfile.write(json.dumps(graph_data).encode())

        elif path == '/api/tags':
            # Serve all tags with counts
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            tags = get_all_tags()
            try:
                print(f"/api/tags -> {len(tags)} tags")
            except Exception:
                pass
            self.wfile.write(json.dumps(tags).encode())

        elif path.startswith('/api/note/'):
            # Serve individual note content
            note_id = path.split('/')[-1]
            note_data = get_note_content(note_id)

            if note_data:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(note_data).encode())
            else:
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Note not found')

        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not found')

    def log_message(self, format, *args):
        """Log requests to stdout"""
        print(f"{self.address_string()} - {format % args}")

    def get_html_page(self):
        """Generate the HTML page with vis.js graph visualization"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Note Graph Viewer</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #1e1e1e;
            color: #d4d4d4;
            overflow: hidden;
        }

        #container {
            display: flex;
            height: 100vh;
        }

        #left-panel {
            width: 300px;
            background: #252526;
            border-right: 1px solid #3c3c3c;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        #search-section {
            padding: 20px;
            border-bottom: 1px solid #3c3c3c;
        }

        #search-input {
            width: 100%;
            padding: 10px;
            background: #3c3c3c;
            border: 1px solid #4c4c4c;
            border-radius: 4px;
            color: #d4d4d4;
            font-size: 14px;
        }

        #search-input:focus {
            outline: none;
            border-color: #569cd6;
        }

        #search-input::placeholder {
            color: #858585;
        }

        #tags-section {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }

        #tags-header {
            font-size: 14px;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        #clear-tags {
            background: transparent;
            border: none;
            color: #569cd6;
            cursor: pointer;
            font-size: 12px;
            padding: 4px 8px;
        }

        #clear-tags:hover {
            color: #4ec9b0;
        }

        .tag-item {
            padding: 8px 12px;
            margin-bottom: 6px;
            background: #2d2d30;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s;
        }

        .tag-item:hover {
            background: #3c3c3c;
        }

        .tag-item.selected {
            background: #264f78;
            border-left: 3px solid #569cd6;
        }

        .tag-name {
            color: #4ec9b0;
            font-size: 13px;
        }

        .tag-count {
            color: #858585;
            font-size: 12px;
        }

        #graph {
            flex: 1;
            background: #1e1e1e;
            position: relative;
        }

        #graph-canvas {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }

        #sidebar {
            width: 400px;
            background: #252526;
            border-left: 1px solid #3c3c3c;
            display: none;
            flex-direction: column;
            overflow: hidden;
        }

        #sidebar.visible {
            display: flex;
        }

        #sidebar-header {
            padding: 20px;
            border-bottom: 1px solid #3c3c3c;
            background: #2d2d30;
        }

        #sidebar-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 5px;
            color: #ffffff;
        }

        #sidebar-path {
            font-size: 12px;
            color: #858585;
        }

        #sidebar-content {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            line-height: 1.6;
        }

        #sidebar-content pre {
            background: #1e1e1e;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }

        #close-sidebar {
            position: absolute;
            top: 20px;
            right: 20px;
            background: transparent;
            border: none;
            color: #858585;
            font-size: 24px;
            cursor: pointer;
            padding: 5px 10px;
        }

        #close-sidebar:hover {
            color: #ffffff;
        }

        #stats {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(45, 45, 48, 0.9);
            padding: 15px 20px;
            border-radius: 6px;
            font-size: 13px;
            border: 1px solid #3c3c3c;
        }

        #stats div {
            margin: 5px 0;
        }

        .stat-label {
            color: #858585;
        }

        .stat-value {
            color: #4ec9b0;
            font-weight: 600;
        }

        #loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 18px;
            color: #858585;
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 10px;
        }

        ::-webkit-scrollbar-track {
            background: #1e1e1e;
        }

        ::-webkit-scrollbar-thumb {
            background: #3c3c3c;
            border-radius: 5px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #4c4c4c;
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="left-panel">
            <div id="search-section">
                <input type="text" id="search-input" placeholder="Search notes..." />
            </div>
            <div id="tags-section">
                <div id="tags-header">
                    <span>Tags</span>
                    <button id="clear-tags" style="display: none;">Clear</button>
                </div>
                <div id="tags-list">
                    <div style="color: #858585; font-size: 12px;">Loading tags...</div>
                </div>
            </div>
        </div>
        <div id="graph">
            <div id="graph-canvas"></div>
            <div id="loading">Loading graph...</div>
            <div id="stats" style="display: none;">
                <div><span class="stat-label">Notes:</span> <span class="stat-value" id="node-count">0</span></div>
                <div><span class="stat-label">Links:</span> <span class="stat-value" id="edge-count">0</span></div>
            </div>
        </div>
        <div id="sidebar">
            <button id="close-sidebar">&times;</button>
            <div id="sidebar-header">
                <div id="sidebar-title"></div>
                <div id="sidebar-path"></div>
            </div>
            <div id="sidebar-content"></div>
        </div>
    </div>

    <script type="text/javascript">
        let network = null;
        let selectedTags = new Set();
        let searchQuery = '';
        let searchTimeout = null;

        // Load tags
        function loadTags() {
            fetch('/api/tags')
                .then(response => response.json())
                .then(tags => {
                    const tagsList = document.getElementById('tags-list');
                    tagsList.innerHTML = '';

                    if (tags.length === 0) {
                        tagsList.innerHTML = '<div style="color: #858585; font-size: 12px;">No tags found</div>';
                        return;
                    }

                    tags.forEach(tagInfo => {
                        const tagItem = document.createElement('div');
                        tagItem.className = 'tag-item';
                        tagItem.innerHTML = `
                            <span class="tag-name">#${tagInfo.tag}</span>
                            <span class="tag-count">${tagInfo.count}</span>
                        `;
                        tagItem.onclick = () => toggleTag(tagInfo.tag, tagItem);
                        tagsList.appendChild(tagItem);
                    });
                })
                .catch(error => {
                    console.error('Error loading tags:', error);
                });
        }

        // Toggle tag selection
        function toggleTag(tag, element) {
            if (selectedTags.has(tag)) {
                selectedTags.delete(tag);
                element.classList.remove('selected');
            } else {
                selectedTags.add(tag);
                element.classList.add('selected');
            }

            // Show/hide clear button
            document.getElementById('clear-tags').style.display =
                selectedTags.size > 0 ? 'block' : 'none';

            loadGraph();
        }

        // Clear all tag selections
        document.getElementById('clear-tags').addEventListener('click', () => {
            selectedTags.clear();
            document.querySelectorAll('.tag-item').forEach(item => {
                item.classList.remove('selected');
            });
            document.getElementById('clear-tags').style.display = 'none';
            loadGraph();
        });

        // Search input handler with debounce
        document.getElementById('search-input').addEventListener('input', (e) => {
            searchQuery = e.target.value.trim();

            // Debounce search
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                loadGraph();
            }, 300);
        });

        // Fetch and render the graph
        function loadGraph() {
            const params = new URLSearchParams();

            if (searchQuery) {
                params.append('search', searchQuery);
            }

            if (selectedTags.size > 0) {
                params.append('tags', Array.from(selectedTags).join(','));
            }

            const url = '/api/graph' + (params.toString() ? '?' + params.toString() : '');

            document.getElementById('loading').style.display = 'block';
            document.getElementById('stats').style.display = 'none';

            fetch(url)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('stats').style.display = 'block';

                    // Update stats
                    document.getElementById('node-count').textContent = data.nodes.length;
                    document.getElementById('edge-count').textContent = data.edges.length;

                    // Create a network
                    const container = document.getElementById('graph-canvas');
                    // Clear previous network DOM to avoid overlaying graphs
                    container.innerHTML = '';

                    const graphData = {
                        nodes: new vis.DataSet(data.nodes.map(node => ({
                            id: node.id,
                            label: node.label,
                            title: node.title + (node.tags.length > 0 ? '\\n\\nTags: ' + node.tags.map(t => '#' + t).join(', ') : ''),
                            path: node.path,
                            tags: node.tags,
                            shape: 'dot',
                            size: 15,
                            font: {
                                size: 14,
                                color: '#d4d4d4'
                            },
                            color: {
                                background: '#4ec9b0',
                                border: '#569cd6',
                                highlight: {
                                    background: '#569cd6',
                                    border: '#4ec9b0'
                                }
                            }
                        }))),
                        edges: new vis.DataSet(data.edges.map(edge => ({
                            from: edge.from,
                            to: edge.to,
                            arrows: 'to',
                            color: {
                                color: '#3c3c3c',
                                highlight: '#569cd6'
                            },
                            smooth: {
                                type: 'continuous'
                            }
                        })))
                    };

                    const options = {
                        physics: {
                            stabilization: {
                                iterations: 200
                            },
                            barnesHut: {
                                gravitationalConstant: -8000,
                                centralGravity: 0.3,
                                springLength: 95,
                                springConstant: 0.04,
                                damping: 0.09
                            }
                        },
                        interaction: {
                            hover: true,
                            tooltipDelay: 100,
                            navigationButtons: true,
                            keyboard: true
                        }
                    };

                    network = new vis.Network(container, graphData, options);

                    // Handle node clicks
                    network.on('click', function(params) {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            showNoteDetails(nodeId);
                        } else {
                            hideSidebar();
                        }
                    });

                    // Handle double-click to open in editor
                    network.on('doubleClick', function(params) {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            const node = graphData.nodes.get(nodeId);
                            alert('To open in nvim, run:\\nnnote ' + node.path);
                        }
                    });
                })
                .catch(error => {
                    console.error('Error loading graph:', error);
                    document.getElementById('loading').textContent = 'Error loading graph';
                });
        }

        // Initial load
        loadTags();
        loadGraph();

        function showNoteDetails(noteId) {
            fetch('/api/note/' + noteId)
                .then(response => response.json())
                .then(note => {
                    document.getElementById('sidebar-title').textContent = note.title;
                    document.getElementById('sidebar-path').textContent = note.path;

                    // Convert markdown content to basic HTML
                    const contentHtml = escapeHtml(note.content)
                        .replace(/\\n/g, '<br>')
                        .replace(/\\[\\[([0-9a-f]+)(?:\\|([^\\]]+))?\\]\\]/g,
                            '<span style="color: #4ec9b0;">&#91;&#91;$2&#93;&#93;</span>');

                    document.getElementById('sidebar-content').innerHTML = '<pre>' + contentHtml + '</pre>';
                    document.getElementById('sidebar').classList.add('visible');
                })
                .catch(error => {
                    console.error('Error loading note:', error);
                });
        }

        function hideSidebar() {
            document.getElementById('sidebar').classList.remove('visible');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        document.getElementById('close-sidebar').addEventListener('click', hideSidebar);
    </script>
</body>
</html>
"""


def main():
    """Start the web server"""
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, GraphRequestHandler)

    print(f"Note Graph Server starting...")
    print(f"Notes path: {NOTES_PATH}")
    print(f"Map file: {MAP_FILE}")
    print(f"\nServer running at: http://localhost:{PORT}")
    print(f"Press Ctrl+C to stop\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    main()
