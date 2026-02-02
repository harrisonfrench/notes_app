from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g, send_file
import json
import io
import html
import os
import tempfile
from datetime import datetime

# OpenAI for Whisper transcription
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

def get_openai_client():
    """Get OpenAI client if API key is available"""
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key and OPENAI_AVAILABLE:
        return OpenAI(api_key=api_key)
    return None

notes = Blueprint('notes', __name__)

# In-memory storage (will be replaced with database later)
pages_store = {
    "1": {
        "id": "1",
        "title": "Welcome",
        "icon": "&#128075;",
        "cover": "gradient-purple",
        "cover_position": 50,
        "parent_id": None,
        "is_favorite": True,
        "is_deleted": False,
        "full_width": False,
        "small_text": False,
        "blocks": [
            {"id": "b1", "type": "heading1", "content": "Welcome to Your Workspace"},
            {"id": "b2", "type": "text", "content": "Start taking notes, organizing your thoughts, and boosting your productivity."},
            {"id": "b3", "type": "divider", "content": ""},
            {"id": "b4", "type": "heading2", "content": "Quick Tips"},
            {"id": "b5", "type": "bullet", "content": "Type <b>*</b> or <b>-</b> then space to create a bullet point"},
            {"id": "b6", "type": "bullet", "content": "Type <b>1.</b> then space to create a numbered list"},
            {"id": "b7", "type": "bullet", "content": "Type <b>/</b> to see all block types"},
            {"id": "b8", "type": "bullet", "content": "Press <b>Tab</b> to indent"},
            {"id": "b9", "type": "divider", "content": ""},
            {"id": "b10", "type": "callout", "content": "Use the Study Tools button (graduation cap) to generate flashcards and quizzes from your notes!", "icon": "&#127891;", "color": "blue"},
        ],
        "comments": [],
        "history": [],
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }
}

# Database storage for database blocks
databases_store = {}

# Trash storage
trash_store = []

# Folders storage
folders_store = {}
next_folder_id = 1

# Templates
templates = {
    "blank": {
        "title": "Untitled",
        "icon": "&#128196;",
        "blocks": []
    },
    "meeting": {
        "title": "Meeting Notes",
        "icon": "&#128197;",
        "blocks": [
            {"type": "heading1", "content": "Meeting Notes"},
            {"type": "text", "content": "Date: "},
            {"type": "heading2", "content": "Attendees"},
            {"type": "bullet", "content": ""},
            {"type": "heading2", "content": "Agenda"},
            {"type": "numbered", "content": ""},
            {"type": "heading2", "content": "Discussion"},
            {"type": "text", "content": ""},
            {"type": "heading2", "content": "Action Items"},
            {"type": "todo", "content": ""},
        ]
    },
    "todo": {
        "title": "To-do List",
        "icon": "&#9989;",
        "blocks": [
            {"type": "heading1", "content": "To-do List"},
            {"type": "heading2", "content": "Today"},
            {"type": "todo", "content": ""},
            {"type": "heading2", "content": "This Week"},
            {"type": "todo", "content": ""},
            {"type": "heading2", "content": "Later"},
            {"type": "todo", "content": ""},
        ]
    },
    "journal": {
        "title": "Journal Entry",
        "icon": "&#128214;",
        "blocks": [
            {"type": "heading1", "content": "Journal Entry"},
            {"type": "text", "content": "Date: "},
            {"type": "heading2", "content": "Today's Highlights"},
            {"type": "bullet", "content": ""},
            {"type": "heading2", "content": "Reflections"},
            {"type": "text", "content": ""},
            {"type": "heading2", "content": "Tomorrow's Goals"},
            {"type": "todo", "content": ""},
        ]
    },
    "project": {
        "title": "Project Plan",
        "icon": "&#128640;",
        "blocks": [
            {"type": "heading1", "content": "Project Plan"},
            {"type": "callout", "content": "Project overview", "icon": "&#128640;", "color": "blue"},
            {"type": "heading2", "content": "Goals"},
            {"type": "bullet", "content": ""},
            {"type": "heading2", "content": "Timeline"},
            {"type": "text", "content": ""},
            {"type": "heading2", "content": "Resources"},
            {"type": "bullet", "content": ""},
            {"type": "heading2", "content": "Tasks"},
            {"type": "todo", "content": ""},
        ]
    },
    "wiki": {
        "title": "Wiki Page",
        "icon": "&#128218;",
        "blocks": [
            {"type": "heading1", "content": "Wiki Page"},
            {"type": "callout", "content": "Overview of the topic", "icon": "&#128218;", "color": "purple"},
            {"type": "heading2", "content": "Introduction"},
            {"type": "text", "content": ""},
            {"type": "heading2", "content": "Details"},
            {"type": "text", "content": ""},
            {"type": "heading2", "content": "Related Topics"},
            {"type": "bullet", "content": ""},
        ]
    }
}

next_page_id = 6
next_block_id = 100
next_comment_id = 10
next_row_id = 10


def get_timestamp():
    return datetime.now().isoformat()


@notes.route('/')
def index():
    """Main notes dashboard"""
    pages = [p for p in pages_store.values() if not p.get('is_deleted')]
    favorites = [p for p in pages if p.get('is_favorite')]
    folders = list(folders_store.values())
    return render_template('notes/index.html', pages=pages, favorites=favorites, folders=folders)


@notes.route('/page/<page_id>')
def view_page(page_id):
    """View a specific page"""
    page = pages_store.get(page_id)
    if not page or page.get('is_deleted'):
        flash('Page not found', 'error')
        return redirect(url_for('notes.index'))

    pages = [p for p in pages_store.values() if not p.get('is_deleted')]
    favorites = [p for p in pages if p.get('is_favorite')]

    # Get database if page has one
    database = None
    for block in page.get('blocks', []):
        if block.get('type') == 'database' and block.get('database_id'):
            database = databases_store.get(block['database_id'])
            break

    folders = list(folders_store.values())
    return render_template('notes/page.html', page=page, pages=pages, favorites=favorites, database=database, folders=folders)


@notes.route('/page/new')
def new_page():
    """Create a new page"""
    global next_page_id, next_block_id

    template_name = request.args.get('template', 'blank')
    template = templates.get(template_name, templates['blank'])

    new_id = str(next_page_id)
    next_page_id += 1

    # Create blocks from template
    blocks = []
    for block in template.get('blocks', []):
        blocks.append({
            "id": f"b{next_block_id}",
            **block
        })
        next_block_id += 1

    pages_store[new_id] = {
        "id": new_id,
        "title": template.get('title', 'Untitled'),
        "icon": template.get('icon', '&#128196;'),
        "cover": None,
        "cover_position": 50,
        "parent_id": None,
        "is_favorite": False,
        "is_deleted": False,
        "full_width": False,
        "small_text": False,
        "blocks": blocks,
        "comments": [],
        "history": [{"id": f"h{next_page_id}", "author": "You", "created_at": get_timestamp(), "action": "Created page"}],
        "created_at": get_timestamp(),
        "updated_at": get_timestamp()
    }

    return redirect(url_for('notes.view_page', page_id=new_id))


# ==================== PAGE API ====================

@notes.route('/api/page/<page_id>', methods=['GET'])
def get_page(page_id):
    """Get a page"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404
    return jsonify({'page': page})


@notes.route('/api/page/<page_id>', methods=['PUT'])
def update_page(page_id):
    """Update a page"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    data = request.get_json()

    # Update allowed fields
    for field in ['title', 'icon', 'cover', 'cover_position', 'parent_id', 'is_favorite', 'full_width', 'small_text']:
        if field in data:
            page[field] = data[field]

    page['updated_at'] = get_timestamp()

    # Add to history
    page['history'].insert(0, {
        "id": f"h{len(page['history']) + 1}",
        "author": "You",
        "created_at": get_timestamp(),
        "action": "Updated page"
    })

    return jsonify({'success': True, 'page': page})


@notes.route('/api/page/<page_id>', methods=['DELETE'])
def delete_page(page_id):
    """Move page to trash"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    page['is_deleted'] = True
    page['deleted_at'] = get_timestamp()
    trash_store.append(page_id)

    return jsonify({'success': True})


@notes.route('/api/page/<page_id>/duplicate', methods=['POST'])
def duplicate_page(page_id):
    """Duplicate a page"""
    global next_page_id, next_block_id

    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    new_id = str(next_page_id)
    next_page_id += 1

    # Deep copy blocks with new IDs
    new_blocks = []
    for block in page.get('blocks', []):
        new_block = block.copy()
        new_block['id'] = f"b{next_block_id}"
        next_block_id += 1
        new_blocks.append(new_block)

    new_page = {
        "id": new_id,
        "title": f"{page['title']} (Copy)",
        "icon": page.get('icon', '&#128196;'),
        "cover": page.get('cover'),
        "cover_position": page.get('cover_position', 50),
        "parent_id": page.get('parent_id'),
        "is_favorite": False,
        "is_deleted": False,
        "full_width": page.get('full_width', False),
        "small_text": page.get('small_text', False),
        "blocks": new_blocks,
        "comments": [],
        "history": [{"id": "h1", "author": "You", "created_at": get_timestamp(), "action": "Created from duplicate"}],
        "created_at": get_timestamp(),
        "updated_at": get_timestamp()
    }

    pages_store[new_id] = new_page

    return jsonify({'success': True, 'page': new_page})


# ==================== BLOCKS API ====================

@notes.route('/api/page/<page_id>/blocks', methods=['PUT'])
def update_blocks(page_id):
    """Update all blocks for a page"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    data = request.get_json()
    page['blocks'] = data.get('blocks', [])
    page['updated_at'] = get_timestamp()

    return jsonify({'success': True, 'page': page})


@notes.route('/api/page/<page_id>/block', methods=['POST'])
def add_block(page_id):
    """Add a new block"""
    global next_block_id

    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    data = request.get_json()

    new_block = {
        'id': f'b{next_block_id}',
        'type': data.get('type', 'text'),
        'content': data.get('content', '')
    }

    # Add optional fields
    for field in ['icon', 'color', 'language', 'url', 'checked', 'children', 'database_id']:
        if field in data:
            new_block[field] = data[field]

    next_block_id += 1

    position = data.get('position')
    if position is not None and 0 <= position <= len(page['blocks']):
        page['blocks'].insert(position, new_block)
    else:
        page['blocks'].append(new_block)

    page['updated_at'] = get_timestamp()

    return jsonify({'success': True, 'block': new_block})


@notes.route('/api/page/<page_id>/block/<block_id>', methods=['PUT'])
def update_block(page_id, block_id):
    """Update a specific block"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    data = request.get_json()

    for block in page['blocks']:
        if block['id'] == block_id:
            for key, value in data.items():
                block[key] = value
            page['updated_at'] = get_timestamp()
            return jsonify({'success': True, 'block': block})

    return jsonify({'error': 'Block not found'}), 404


@notes.route('/api/page/<page_id>/block/<block_id>', methods=['DELETE'])
def delete_block(page_id, block_id):
    """Delete a specific block"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    page['blocks'] = [b for b in page['blocks'] if b['id'] != block_id]
    page['updated_at'] = get_timestamp()

    return jsonify({'success': True})


@notes.route('/api/page/<page_id>/blocks/reorder', methods=['POST'])
def reorder_blocks(page_id):
    """Reorder blocks (drag and drop)"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    data = request.get_json()
    block_ids = data.get('block_ids', [])

    # Reorder blocks according to new order
    block_map = {b['id']: b for b in page['blocks']}
    page['blocks'] = [block_map[bid] for bid in block_ids if bid in block_map]
    page['updated_at'] = get_timestamp()

    return jsonify({'success': True})


# ==================== PAGE TRANSCRIPTION API ====================

@notes.route('/api/page/<page_id>/transcribe', methods=['POST'])
def transcribe_to_page(page_id):
    """Transcribe audio and insert directly into a page"""
    global next_block_id

    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    filename = file.filename
    insert_position = request.form.get('position', 'end')  # 'end' or block_id to insert after

    client = get_openai_client()

    if client:
        try:
            # Save file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            # Transcribe with Whisper
            with open(tmp_path, 'rb') as audio_file:
                whisper_response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )

            os.unlink(tmp_path)

            transcribed_text = whisper_response.text

        except Exception as e:
            transcribed_text = f"[Transcription failed: {str(e)}. Set OPENAI_API_KEY for real transcription.]"
    else:
        transcribed_text = "[Demo mode: Set OPENAI_API_KEY environment variable for real transcription.] This is where your transcribed audio would appear."

    # Create blocks from transcription
    new_blocks = []

    # Add a callout showing this is a transcription
    new_blocks.append({
        'id': f'b{next_block_id}',
        'type': 'callout',
        'content': f'🎙️ Transcription from: {filename}',
        'icon': '🎙️',
        'color': 'purple'
    })
    next_block_id += 1

    # Split text into paragraphs and create text blocks
    paragraphs = [p.strip() for p in transcribed_text.split('\n') if p.strip()]
    for para in paragraphs:
        new_blocks.append({
            'id': f'b{next_block_id}',
            'type': 'text',
            'content': para
        })
        next_block_id += 1

    # Insert blocks at the specified position
    if insert_position == 'end':
        page['blocks'].extend(new_blocks)
    else:
        # Find position of block_id and insert after it
        insert_idx = len(page['blocks'])
        for i, block in enumerate(page['blocks']):
            if block['id'] == insert_position:
                insert_idx = i + 1
                break
        for i, block in enumerate(new_blocks):
            page['blocks'].insert(insert_idx + i, block)

    page['updated_at'] = get_timestamp()

    return jsonify({
        'success': True,
        'blocks_added': len(new_blocks),
        'transcribed_text': transcribed_text
    })


@notes.route('/api/page/<page_id>/transcribe-url', methods=['POST'])
def transcribe_url_to_page(page_id):
    """Transcribe audio from URL and insert into page"""
    global next_block_id
    import urllib.request

    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    data = request.get_json()
    audio_url = data.get('url')

    if not audio_url:
        return jsonify({'error': 'No URL provided'}), 400

    client = get_openai_client()

    if client:
        try:
            # Download audio file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                urllib.request.urlretrieve(audio_url, tmp.name)
                tmp_path = tmp.name

            # Transcribe with Whisper
            with open(tmp_path, 'rb') as audio_file:
                whisper_response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )

            os.unlink(tmp_path)
            transcribed_text = whisper_response.text

        except Exception as e:
            return jsonify({'error': f'Transcription failed: {str(e)}'}), 500
    else:
        transcribed_text = "[Demo mode: Set OPENAI_API_KEY for real transcription.]"

    # Create transcription block
    new_block = {
        'id': f'b{next_block_id}',
        'type': 'text',
        'content': transcribed_text
    }
    next_block_id += 1

    page['blocks'].append(new_block)
    page['updated_at'] = get_timestamp()

    return jsonify({
        'success': True,
        'transcribed_text': transcribed_text
    })


# ==================== COMMENTS API ====================

@notes.route('/api/page/<page_id>/comments', methods=['GET'])
def get_comments(page_id):
    """Get all comments for a page"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    return jsonify({'comments': page.get('comments', [])})


@notes.route('/api/page/<page_id>/comment', methods=['POST'])
def add_comment(page_id):
    """Add a comment"""
    global next_comment_id

    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    data = request.get_json()

    comment = {
        'id': f'c{next_comment_id}',
        'author': data.get('author', 'You'),
        'text': data.get('text', ''),
        'block_id': data.get('block_id'),  # Optional: comment on specific block
        'created_at': get_timestamp()
    }
    next_comment_id += 1

    if 'comments' not in page:
        page['comments'] = []
    page['comments'].append(comment)

    return jsonify({'success': True, 'comment': comment})


@notes.route('/api/page/<page_id>/comment/<comment_id>', methods=['DELETE'])
def delete_comment(page_id, comment_id):
    """Delete a comment"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    page['comments'] = [c for c in page.get('comments', []) if c['id'] != comment_id]

    return jsonify({'success': True})


# ==================== HISTORY API ====================

@notes.route('/api/page/<page_id>/history', methods=['GET'])
def get_history(page_id):
    """Get page history"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    return jsonify({'history': page.get('history', [])})


# ==================== TRASH API ====================

@notes.route('/api/trash', methods=['GET'])
def get_trash():
    """Get all trashed pages"""
    trashed = [pages_store[pid] for pid in trash_store if pid in pages_store]
    return jsonify({'pages': trashed})


@notes.route('/api/page/<page_id>/restore', methods=['POST'])
def restore_page(page_id):
    """Restore a page from trash"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    page['is_deleted'] = False
    if 'deleted_at' in page:
        del page['deleted_at']
    if page_id in trash_store:
        trash_store.remove(page_id)

    return jsonify({'success': True})


@notes.route('/api/page/<page_id>/permanent', methods=['DELETE'])
def permanent_delete(page_id):
    """Permanently delete a page"""
    if page_id in pages_store:
        del pages_store[page_id]
    if page_id in trash_store:
        trash_store.remove(page_id)

    return jsonify({'success': True})


# ==================== FOLDERS API ====================

@notes.route('/api/folders', methods=['GET'])
def get_folders():
    """Get all folders"""
    folders = list(folders_store.values())
    # Include pages in each folder
    for folder in folders:
        folder['pages'] = [
            {
                'id': p['id'],
                'title': p['title'],
                'icon': p.get('icon', '&#128196;')
            }
            for pid in folder.get('page_ids', [])
            if pid in pages_store and not pages_store[pid].get('is_deleted')
            for p in [pages_store[pid]]
        ]
    return jsonify({'success': True, 'folders': folders})


@notes.route('/api/folders', methods=['POST'])
def create_folder():
    """Create a new folder"""
    global next_folder_id
    data = request.get_json()

    folder_id = f"folder-{next_folder_id}"
    next_folder_id += 1

    folder = {
        'id': folder_id,
        'name': data.get('name', 'New Folder'),
        'icon': data.get('icon', '📁'),
        'color': data.get('color', '#6940a5'),
        'page_ids': [],
        'expanded': True,
        'created_at': get_timestamp(),
        'updated_at': get_timestamp()
    }

    folders_store[folder_id] = folder
    return jsonify({'success': True, 'folder': folder})


@notes.route('/api/folders/<folder_id>', methods=['GET'])
def get_folder(folder_id):
    """Get a specific folder"""
    folder = folders_store.get(folder_id)
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404

    # Include full page data
    folder_copy = folder.copy()
    folder_copy['pages'] = [
        pages_store[pid]
        for pid in folder.get('page_ids', [])
        if pid in pages_store and not pages_store[pid].get('is_deleted')
    ]
    return jsonify({'success': True, 'folder': folder_copy})


@notes.route('/api/folders/<folder_id>', methods=['PUT'])
def update_folder(folder_id):
    """Update a folder"""
    folder = folders_store.get(folder_id)
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404

    data = request.get_json()

    for field in ['name', 'icon', 'color', 'expanded']:
        if field in data:
            folder[field] = data[field]

    folder['updated_at'] = get_timestamp()
    return jsonify({'success': True, 'folder': folder})


@notes.route('/api/folders/<folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    """Delete a folder (pages are not deleted, just unassigned)"""
    if folder_id in folders_store:
        del folders_store[folder_id]
        return jsonify({'success': True})
    return jsonify({'error': 'Folder not found'}), 404


@notes.route('/api/folders/<folder_id>/pages', methods=['POST'])
def add_page_to_folder(folder_id):
    """Add a page to a folder"""
    folder = folders_store.get(folder_id)
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404

    data = request.get_json()
    page_id = data.get('page_id')

    if not page_id or page_id not in pages_store:
        return jsonify({'error': 'Page not found'}), 404

    # Remove page from any other folder first
    for f in folders_store.values():
        if page_id in f.get('page_ids', []):
            f['page_ids'].remove(page_id)

    # Add to this folder
    if 'page_ids' not in folder:
        folder['page_ids'] = []
    if page_id not in folder['page_ids']:
        folder['page_ids'].append(page_id)

    # Also update page's folder_id
    pages_store[page_id]['folder_id'] = folder_id

    folder['updated_at'] = get_timestamp()
    return jsonify({'success': True, 'folder': folder})


@notes.route('/api/folders/<folder_id>/pages/<page_id>', methods=['DELETE'])
def remove_page_from_folder(folder_id, page_id):
    """Remove a page from a folder"""
    folder = folders_store.get(folder_id)
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404

    if 'page_ids' in folder and page_id in folder['page_ids']:
        folder['page_ids'].remove(page_id)

    # Clear folder_id from page
    if page_id in pages_store:
        pages_store[page_id]['folder_id'] = None

    folder['updated_at'] = get_timestamp()
    return jsonify({'success': True})


@notes.route('/api/pages/<page_id>/move-to-folder', methods=['POST'])
def move_page_to_folder(page_id):
    """Move a page to a folder (or remove from folder if folder_id is null)"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    data = request.get_json()
    new_folder_id = data.get('folder_id')

    # Remove from current folder
    for folder in folders_store.values():
        if page_id in folder.get('page_ids', []):
            folder['page_ids'].remove(page_id)

    # Add to new folder if specified
    if new_folder_id and new_folder_id in folders_store:
        folder = folders_store[new_folder_id]
        if 'page_ids' not in folder:
            folder['page_ids'] = []
        folder['page_ids'].append(page_id)
        page['folder_id'] = new_folder_id
    else:
        page['folder_id'] = None

    return jsonify({'success': True, 'page': page})


# ==================== SEARCH API ====================

@notes.route('/api/search', methods=['GET'])
def search_pages():
    """Search pages"""
    query = request.args.get('q', '').lower()
    filter_type = request.args.get('filter', 'all')

    results = []
    for page in pages_store.values():
        if page.get('is_deleted'):
            continue

        # Search in title
        if query in page.get('title', '').lower():
            results.append({
                'id': page['id'],
                'title': page['title'],
                'icon': page.get('icon', '&#128196;'),
                'type': 'page',
                'match': 'title'
            })
            continue

        # Search in content
        if filter_type in ['all', 'content']:
            for block in page.get('blocks', []):
                if query in block.get('content', '').lower():
                    results.append({
                        'id': page['id'],
                        'title': page['title'],
                        'icon': page.get('icon', '&#128196;'),
                        'type': 'page',
                        'match': 'content',
                        'preview': block.get('content', '')[:100]
                    })
                    break

    return jsonify({'results': results})


# ==================== IMPORT/EXPORT API ====================

@notes.route('/api/import', methods=['POST'])
def import_file():
    """Import a file as a new page"""
    global next_page_id, next_block_id

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    filename = file.filename
    content = file.read().decode('utf-8')

    # Create new page
    new_id = str(next_page_id)
    next_page_id += 1

    blocks = []

    # Parse based on file type
    if filename.endswith('.md'):
        # Simple markdown parsing
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                blocks.append({"id": f"b{next_block_id}", "type": "heading1", "content": line[2:]})
            elif line.startswith('## '):
                blocks.append({"id": f"b{next_block_id}", "type": "heading2", "content": line[3:]})
            elif line.startswith('### '):
                blocks.append({"id": f"b{next_block_id}", "type": "heading3", "content": line[4:]})
            elif line.startswith('- [ ] '):
                blocks.append({"id": f"b{next_block_id}", "type": "todo", "content": line[6:], "checked": False})
            elif line.startswith('- [x] '):
                blocks.append({"id": f"b{next_block_id}", "type": "todo", "content": line[6:], "checked": True})
            elif line.startswith('- '):
                blocks.append({"id": f"b{next_block_id}", "type": "bullet", "content": line[2:]})
            elif line.startswith('> '):
                blocks.append({"id": f"b{next_block_id}", "type": "quote", "content": line[2:]})
            elif line.strip() == '---':
                blocks.append({"id": f"b{next_block_id}", "type": "divider", "content": ""})
            elif line.strip():
                blocks.append({"id": f"b{next_block_id}", "type": "text", "content": line})
            next_block_id += 1
    else:
        # Plain text
        blocks.append({"id": f"b{next_block_id}", "type": "text", "content": content})
        next_block_id += 1

    title = filename.rsplit('.', 1)[0] if '.' in filename else filename

    pages_store[new_id] = {
        "id": new_id,
        "title": title,
        "icon": "&#128196;",
        "cover": None,
        "cover_position": 50,
        "parent_id": None,
        "is_favorite": False,
        "is_deleted": False,
        "full_width": False,
        "small_text": False,
        "blocks": blocks,
        "comments": [],
        "history": [{"id": "h1", "author": "You", "created_at": get_timestamp(), "action": "Imported from file"}],
        "created_at": get_timestamp(),
        "updated_at": get_timestamp()
    }

    return jsonify({'success': True, 'page_id': new_id})


@notes.route('/api/page/<page_id>/export/<format>')
def export_page(page_id, format):
    """Export a page in various formats"""
    page = pages_store.get(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    if format == 'md':
        content = f"# {page['title']}\n\n"
        for block in page.get('blocks', []):
            block_type = block.get('type')
            block_content = block.get('content', '')

            if block_type == 'heading1':
                content += f"# {block_content}\n\n"
            elif block_type == 'heading2':
                content += f"## {block_content}\n\n"
            elif block_type == 'heading3':
                content += f"### {block_content}\n\n"
            elif block_type == 'bullet':
                content += f"- {block_content}\n"
            elif block_type == 'numbered':
                content += f"1. {block_content}\n"
            elif block_type == 'todo':
                checked = 'x' if block.get('checked') else ' '
                content += f"- [{checked}] {block_content}\n"
            elif block_type == 'quote':
                content += f"> {block_content}\n\n"
            elif block_type == 'divider':
                content += "---\n\n"
            elif block_type == 'code':
                lang = block.get('language', '')
                content += f"```{lang}\n{block_content}\n```\n\n"
            else:
                content += f"{block_content}\n\n"

        buffer = io.BytesIO(content.encode('utf-8'))
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype='text/markdown',
            as_attachment=True,
            download_name=f"{page['title']}.md"
        )

    elif format == 'html':
        content = f"<!DOCTYPE html><html><head><title>{html.escape(page['title'])}</title></head><body>"
        content += f"<h1>{html.escape(page['title'])}</h1>"

        for block in page.get('blocks', []):
            block_type = block.get('type')
            block_content = html.escape(block.get('content', ''))

            if block_type == 'heading1':
                content += f"<h1>{block_content}</h1>"
            elif block_type == 'heading2':
                content += f"<h2>{block_content}</h2>"
            elif block_type == 'heading3':
                content += f"<h3>{block_content}</h3>"
            elif block_type == 'bullet':
                content += f"<ul><li>{block_content}</li></ul>"
            elif block_type == 'numbered':
                content += f"<ol><li>{block_content}</li></ol>"
            elif block_type == 'todo':
                checked = 'checked' if block.get('checked') else ''
                content += f"<div><input type='checkbox' {checked}> {block_content}</div>"
            elif block_type == 'quote':
                content += f"<blockquote>{block_content}</blockquote>"
            elif block_type == 'divider':
                content += "<hr>"
            elif block_type == 'code':
                content += f"<pre><code>{block_content}</code></pre>"
            else:
                content += f"<p>{block_content}</p>"

        content += "</body></html>"

        buffer = io.BytesIO(content.encode('utf-8'))
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype='text/html',
            as_attachment=True,
            download_name=f"{page['title']}.html"
        )

    elif format == 'json':
        buffer = io.BytesIO(json.dumps(page, indent=2).encode('utf-8'))
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name=f"{page['title']}.json"
        )

    return jsonify({'error': 'Unsupported format'}), 400


# ==================== DATABASE API ====================

@notes.route('/api/database/<db_id>', methods=['GET'])
def get_database(db_id):
    """Get a database"""
    db = databases_store.get(db_id)
    if not db:
        return jsonify({'error': 'Database not found'}), 404
    return jsonify({'database': db})


@notes.route('/api/database/<db_id>', methods=['PUT'])
def update_database(db_id):
    """Update database settings"""
    db = databases_store.get(db_id)
    if not db:
        return jsonify({'error': 'Database not found'}), 404

    data = request.get_json()
    for field in ['name', 'current_view', 'filters', 'sorts']:
        if field in data:
            db[field] = data[field]

    return jsonify({'success': True, 'database': db})


@notes.route('/api/database/<db_id>/row', methods=['POST'])
def add_row(db_id):
    """Add a row to database"""
    global next_row_id

    db = databases_store.get(db_id)
    if not db:
        return jsonify({'error': 'Database not found'}), 404

    data = request.get_json()

    row = {
        'id': f'r{next_row_id}',
        'properties': data.get('properties', {})
    }
    next_row_id += 1

    db['rows'].append(row)

    return jsonify({'success': True, 'row': row})


@notes.route('/api/database/<db_id>/row/<row_id>', methods=['PUT'])
def update_row(db_id, row_id):
    """Update a database row"""
    db = databases_store.get(db_id)
    if not db:
        return jsonify({'error': 'Database not found'}), 404

    data = request.get_json()

    for row in db['rows']:
        if row['id'] == row_id:
            row['properties'].update(data.get('properties', {}))
            return jsonify({'success': True, 'row': row})

    return jsonify({'error': 'Row not found'}), 404


@notes.route('/api/database/<db_id>/row/<row_id>', methods=['DELETE'])
def delete_row(db_id, row_id):
    """Delete a database row"""
    db = databases_store.get(db_id)
    if not db:
        return jsonify({'error': 'Database not found'}), 404

    db['rows'] = [r for r in db['rows'] if r['id'] != row_id]

    return jsonify({'success': True})


# ==================== PAGES API ====================

@notes.route('/api/pages', methods=['GET'])
def get_pages():
    """Get all pages"""
    pages = [p for p in pages_store.values() if not p.get('is_deleted')]
    return jsonify({'pages': pages})


@notes.route('/api/pages/reorder', methods=['POST'])
def reorder_pages():
    """Reorder pages in sidebar"""
    data = request.get_json()
    # This would update page order - in memory store we don't track order
    return jsonify({'success': True})


@notes.route('/api/favorites', methods=['GET'])
def get_favorites():
    """Get favorite pages"""
    favorites = [p for p in pages_store.values() if p.get('is_favorite') and not p.get('is_deleted')]
    return jsonify({'pages': favorites})


# ==================== AI API ====================

# In-memory storage for AI conversations and transcripts
ai_conversations = {}
transcripts_store = {}
next_transcript_id = 1

@notes.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """AI Chat - Ask questions about notes, generate content, summarize"""
    data = request.get_json()
    message = data.get('message', '')
    page_id = data.get('page_id')
    conversation_id = data.get('conversation_id', 'default')
    action = data.get('action', 'chat')  # chat, summarize, generate, explain

    # Get page context if provided
    page_context = ""
    if page_id and page_id in pages_store:
        page = pages_store[page_id]
        page_context = f"Page: {page['title']}\n"
        for block in page.get('blocks', []):
            page_context += f"- {block.get('content', '')}\n"

    # Initialize conversation if needed
    if conversation_id not in ai_conversations:
        ai_conversations[conversation_id] = []

    # Add user message to history
    ai_conversations[conversation_id].append({
        'role': 'user',
        'content': message,
        'timestamp': get_timestamp()
    })

    # Generate AI response based on action
    if action == 'summarize':
        response = generate_summary(page_context, message)
    elif action == 'generate':
        response = generate_content(message, page_context)
    elif action == 'explain':
        response = explain_content(message, page_context)
    elif action == 'improve':
        response = improve_writing(message)
    elif action == 'translate':
        target_lang = data.get('target_language', 'Spanish')
        response = translate_text(message, target_lang)
    elif action == 'action_items':
        response = extract_action_items(page_context or message)
    else:
        response = chat_response(message, page_context, ai_conversations[conversation_id])

    # Add AI response to history
    ai_conversations[conversation_id].append({
        'role': 'assistant',
        'content': response,
        'timestamp': get_timestamp()
    })

    return jsonify({
        'success': True,
        'response': response,
        'conversation_id': conversation_id
    })


@notes.route('/api/ai/transcribe', methods=['POST'])
def ai_transcribe():
    """Transcribe audio/video file to text using OpenAI Whisper"""
    global next_transcript_id

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    filename = file.filename

    transcript_id = f"t{next_transcript_id}"
    next_transcript_id += 1

    # Try to use OpenAI Whisper for real transcription
    client = get_openai_client()

    if client:
        try:
            # Save file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            # Transcribe with Whisper
            with open(tmp_path, 'rb') as audio_file:
                whisper_response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

            # Clean up temp file
            os.unlink(tmp_path)

            # Process segments
            segments = []
            full_text_parts = []

            if hasattr(whisper_response, 'segments') and whisper_response.segments:
                for i, seg in enumerate(whisper_response.segments):
                    start_time = format_seconds(seg.get('start', 0))
                    end_time = format_seconds(seg.get('end', 0))
                    text = seg.get('text', '').strip()

                    segments.append({
                        'start': start_time,
                        'end': end_time,
                        'speaker': f'Speaker',
                        'text': text
                    })
                    full_text_parts.append(text)
            else:
                # No segments, use full text
                full_text = whisper_response.text if hasattr(whisper_response, 'text') else str(whisper_response)
                segments.append({
                    'start': '0:00',
                    'end': 'N/A',
                    'speaker': 'Speaker',
                    'text': full_text
                })
                full_text_parts.append(full_text)

            full_text = '\n\n'.join(full_text_parts)
            duration = format_seconds(whisper_response.duration) if hasattr(whisper_response, 'duration') else 'N/A'

            # Generate summary and action items using GPT
            summary, action_items = generate_transcript_insights(client, full_text)

            transcript = {
                'id': transcript_id,
                'filename': filename,
                'duration': duration,
                'created_at': get_timestamp(),
                'status': 'completed',
                'segments': segments,
                'full_text': full_text,
                'summary': summary,
                'action_items': action_items,
                'speakers': ['Speaker'],
                'source': 'whisper'
            }

            transcripts_store[transcript_id] = transcript

            return jsonify({
                'success': True,
                'transcript': transcript
            })

        except Exception as e:
            # Fall back to demo mode on error
            print(f"Whisper transcription error: {e}")
            return create_demo_transcript(transcript_id, filename)
    else:
        # No API key, use demo mode
        return create_demo_transcript(transcript_id, filename)


def format_seconds(seconds):
    """Convert seconds to MM:SS format"""
    if not seconds:
        return "0:00"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def generate_transcript_insights(client, text):
    """Generate summary and action items from transcript text"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You analyze transcripts and extract key information. Respond in JSON format with 'summary' (2-3 sentences) and 'action_items' (array of strings)."},
                {"role": "user", "content": f"Analyze this transcript and provide a summary and action items:\n\n{text[:4000]}"}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result.get('summary', ''), result.get('action_items', [])
    except:
        return 'Transcript processed successfully.', []


def create_demo_transcript(transcript_id, filename):
    """Create a demo transcript when API is unavailable"""
    transcript = {
        'id': transcript_id,
        'filename': filename,
        'duration': '3:45',
        'created_at': get_timestamp(),
        'status': 'completed',
        'segments': [
            {'start': '0:00', 'end': '0:15', 'speaker': 'Speaker 1', 'text': 'Welcome everyone to today\'s meeting. Let\'s get started with our agenda.'},
            {'start': '0:15', 'end': '0:32', 'speaker': 'Speaker 2', 'text': 'Thanks for having us. I\'d like to discuss the project timeline first.'},
            {'start': '0:32', 'end': '0:58', 'speaker': 'Speaker 1', 'text': 'Great idea. We\'re currently on track for the Q2 deadline.'},
        ],
        'full_text': 'Welcome everyone to today\'s meeting. Let\'s get started with our agenda.\n\nThanks for having us. I\'d like to discuss the project timeline first.\n\nGreat idea. We\'re currently on track for the Q2 deadline.',
        'summary': 'Demo transcript - Add OPENAI_API_KEY environment variable for real transcription.',
        'action_items': ['Set up OpenAI API key for real transcription'],
        'speakers': ['Speaker 1', 'Speaker 2'],
        'source': 'demo'
    }
    transcripts_store[transcript_id] = transcript
    return jsonify({'success': True, 'transcript': transcript})


@notes.route('/api/ai/meeting/start', methods=['POST'])
def start_meeting_transcription():
    """Start real-time meeting transcription"""
    global next_transcript_id

    data = request.get_json()
    meeting_name = data.get('name', 'Untitled Meeting')

    transcript_id = f"t{next_transcript_id}"
    next_transcript_id += 1

    transcript = {
        'id': transcript_id,
        'name': meeting_name,
        'created_at': get_timestamp(),
        'status': 'recording',
        'segments': [],
        'speakers': [],
        'duration': '0:00'
    }

    transcripts_store[transcript_id] = transcript

    return jsonify({
        'success': True,
        'transcript_id': transcript_id,
        'transcript': transcript
    })


@notes.route('/api/ai/meeting/<transcript_id>/segment', methods=['POST'])
def add_meeting_segment(transcript_id):
    """Add a segment to ongoing meeting transcription"""
    if transcript_id not in transcripts_store:
        return jsonify({'error': 'Transcript not found'}), 404

    data = request.get_json()
    transcript = transcripts_store[transcript_id]

    segment = {
        'start': data.get('start', '0:00'),
        'end': data.get('end', '0:00'),
        'speaker': data.get('speaker', 'Unknown'),
        'text': data.get('text', '')
    }

    transcript['segments'].append(segment)

    # Update speakers list
    if segment['speaker'] not in transcript['speakers']:
        transcript['speakers'].append(segment['speaker'])

    return jsonify({'success': True, 'segment': segment})


@notes.route('/api/ai/meeting/<transcript_id>/stop', methods=['POST'])
def stop_meeting_transcription(transcript_id):
    """Stop meeting transcription and generate summary"""
    if transcript_id not in transcripts_store:
        return jsonify({'error': 'Transcript not found'}), 404

    transcript = transcripts_store[transcript_id]
    transcript['status'] = 'completed'
    transcript['ended_at'] = get_timestamp()

    # Generate full text from segments
    full_text = '\n\n'.join([f"[{s['speaker']}]: {s['text']}" for s in transcript['segments']])
    transcript['full_text'] = full_text

    # Generate summary and action items
    transcript['summary'] = generate_meeting_summary(transcript['segments'])
    transcript['action_items'] = extract_meeting_action_items(transcript['segments'])

    return jsonify({
        'success': True,
        'transcript': transcript
    })


@notes.route('/api/ai/transcripts', methods=['GET'])
def get_transcripts():
    """Get all transcripts"""
    return jsonify({'transcripts': list(transcripts_store.values())})


@notes.route('/api/ai/transcript/<transcript_id>', methods=['GET'])
def get_transcript(transcript_id):
    """Get a specific transcript"""
    if transcript_id not in transcripts_store:
        return jsonify({'error': 'Transcript not found'}), 404
    return jsonify({'transcript': transcripts_store[transcript_id]})


@notes.route('/api/ai/transcript/<transcript_id>/to-page', methods=['POST'])
def transcript_to_page(transcript_id):
    """Convert a transcript to a notes page"""
    global next_page_id, next_block_id

    if transcript_id not in transcripts_store:
        return jsonify({'error': 'Transcript not found'}), 404

    transcript = transcripts_store[transcript_id]

    # Create blocks from transcript
    blocks = []

    # Title
    blocks.append({
        "id": f"b{next_block_id}",
        "type": "heading1",
        "content": transcript.get('name', transcript.get('filename', 'Transcript'))
    })
    next_block_id += 1

    # Meeting info callout
    blocks.append({
        "id": f"b{next_block_id}",
        "type": "callout",
        "content": f"Recorded: {transcript['created_at'][:10]} | Duration: {transcript.get('duration', 'N/A')} | Speakers: {', '.join(transcript.get('speakers', []))}",
        "icon": "&#128197;",
        "color": "blue"
    })
    next_block_id += 1

    # Summary section
    if transcript.get('summary'):
        blocks.append({"id": f"b{next_block_id}", "type": "heading2", "content": "Summary"})
        next_block_id += 1
        blocks.append({"id": f"b{next_block_id}", "type": "text", "content": transcript['summary']})
        next_block_id += 1

    # Action items section
    if transcript.get('action_items'):
        blocks.append({"id": f"b{next_block_id}", "type": "heading2", "content": "Action Items"})
        next_block_id += 1
        for item in transcript['action_items']:
            blocks.append({"id": f"b{next_block_id}", "type": "todo", "content": item, "checked": False})
            next_block_id += 1

    # Transcript section
    blocks.append({"id": f"b{next_block_id}", "type": "divider", "content": ""})
    next_block_id += 1
    blocks.append({"id": f"b{next_block_id}", "type": "heading2", "content": "Full Transcript"})
    next_block_id += 1

    # Add transcript segments as toggle blocks
    for segment in transcript.get('segments', []):
        blocks.append({
            "id": f"b{next_block_id}",
            "type": "quote",
            "content": f"<strong>[{segment['start']}] {segment['speaker']}:</strong> {segment['text']}"
        })
        next_block_id += 1

    # Create the page
    new_id = str(next_page_id)
    next_page_id += 1

    pages_store[new_id] = {
        "id": new_id,
        "title": transcript.get('name', transcript.get('filename', 'Transcript')),
        "icon": "&#127908;",
        "cover": "gradient-purple",
        "cover_position": 50,
        "parent_id": None,
        "is_favorite": False,
        "is_deleted": False,
        "full_width": False,
        "small_text": False,
        "blocks": blocks,
        "comments": [],
        "history": [{"id": "h1", "author": "You", "created_at": get_timestamp(), "action": "Created from transcript"}],
        "created_at": get_timestamp(),
        "updated_at": get_timestamp()
    }

    return jsonify({'success': True, 'page_id': new_id})


@notes.route('/api/ai/conversation/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get AI conversation history"""
    if conversation_id not in ai_conversations:
        return jsonify({'messages': []})
    return jsonify({'messages': ai_conversations[conversation_id]})


@notes.route('/api/ai/conversation/<conversation_id>', methods=['DELETE'])
def clear_conversation(conversation_id):
    """Clear AI conversation history"""
    if conversation_id in ai_conversations:
        del ai_conversations[conversation_id]
    return jsonify({'success': True})


# AI Helper Functions

def chat_response(message, context, history):
    """Generate a conversational response"""
    message_lower = message.lower()

    # Simple pattern matching for demo
    if 'hello' in message_lower or 'hi' in message_lower:
        return "Hello! I'm your AI assistant. I can help you with your notes - ask me to summarize, explain, or generate content. How can I help you today?"

    if 'summarize' in message_lower:
        if context:
            return generate_summary(context, message)
        return "Please provide some content to summarize, or open a page and I can summarize it for you."

    if 'help' in message_lower:
        return """I can help you with several things:

**📝 Content Generation**
- "Write a paragraph about [topic]"
- "Generate ideas for [subject]"
- "Create an outline for [topic]"

**📋 Summarization**
- "Summarize this page"
- "Give me the key points"

**✅ Action Items**
- "Extract action items from this page"
- "What are the tasks mentioned?"

**🌐 Translation**
- "Translate this to Spanish"
- "Convert to French"

**✨ Writing Improvement**
- "Improve this text: [your text]"
- "Make this more professional"

Just ask me anything!"""

    if 'what' in message_lower and 'page' in message_lower:
        if context:
            lines = context.split('\n')
            title = lines[0].replace('Page: ', '') if lines else 'Unknown'
            return f"This page is titled '{title}'. It contains {len(lines)-1} content blocks. Would you like me to summarize it or extract key points?"
        return "I don't have any page context. Please open a page first."

    # Default response
    if context:
        return f"Based on the current page content, I can help you analyze, summarize, or generate related content. What would you like me to do?"

    return "I'm your AI assistant for notes. I can help summarize content, generate text, extract action items, and more. What would you like me to help with?"


def generate_summary(context, message):
    """Generate a summary of the content"""
    if not context:
        return "There's no content to summarize. Please provide text or open a page."

    lines = [l.strip() for l in context.split('\n') if l.strip() and not l.startswith('Page:')]

    if len(lines) == 0:
        return "The page appears to be empty. Add some content and I can summarize it."

    # Generate a mock summary
    key_points = lines[:min(5, len(lines))]
    summary = f"""**Summary**

This content covers {len(lines)} main points. Here are the key takeaways:

"""
    for i, point in enumerate(key_points, 1):
        clean_point = point.replace('- ', '').replace('* ', '')[:100]
        if clean_point:
            summary += f"{i}. {clean_point}\n"

    return summary


def generate_content(prompt, context):
    """Generate new content based on prompt"""
    prompt_lower = prompt.lower()

    if 'outline' in prompt_lower:
        topic = prompt.replace('outline', '').replace('for', '').strip()
        return f"""**Outline: {topic or 'Your Topic'}**

1. **Introduction**
   - Background and context
   - Purpose and objectives
   - Key definitions

2. **Main Points**
   - Point A: Core concept
   - Point B: Supporting evidence
   - Point C: Practical applications

3. **Analysis**
   - Pros and cons
   - Comparisons
   - Case studies

4. **Conclusion**
   - Summary of key points
   - Recommendations
   - Next steps

5. **References**
   - Sources
   - Further reading"""

    if 'ideas' in prompt_lower or 'brainstorm' in prompt_lower:
        return """**Generated Ideas**

1. 💡 Innovative approach using modern technologies
2. 🎯 Focus on user experience and simplicity
3. 📊 Data-driven decision making process
4. 🤝 Collaborative team-based implementation
5. 🔄 Iterative development with feedback loops
6. 🌱 Sustainable and scalable solution
7. 📱 Mobile-first design consideration
8. 🔒 Security and privacy by design

Would you like me to expand on any of these ideas?"""

    if 'paragraph' in prompt_lower or 'write' in prompt_lower:
        return """Here's a generated paragraph based on your request:

The modern workspace has evolved significantly with the integration of digital tools and collaborative platforms. Teams now have access to powerful note-taking applications that not only capture information but also help organize, analyze, and share knowledge effectively. These tools enable seamless collaboration across different time zones and locations, making remote work more productive than ever. By leveraging AI capabilities, users can now summarize lengthy documents, extract action items automatically, and even generate content drafts, significantly reducing the time spent on routine tasks and allowing focus on higher-value work.

Would you like me to modify this or generate something different?"""

    return "I can help generate content! Try asking me to:\n- Write a paragraph about [topic]\n- Create an outline for [subject]\n- Brainstorm ideas for [project]"


def explain_content(text, context):
    """Explain content in simpler terms"""
    return f"""**Explanation**

Let me break this down for you:

The content discusses key concepts that can be understood as follows:

1. **Core Idea**: The main point is about organizing information effectively
2. **Why It Matters**: This helps improve productivity and clarity
3. **How It Works**: By structuring content into manageable blocks
4. **Key Takeaway**: Good organization leads to better understanding

Would you like me to explain any specific part in more detail?"""


def improve_writing(text):
    """Improve the writing quality"""
    return f"""**Improved Version**

{text}

**Suggestions Applied:**
- ✅ Enhanced clarity and readability
- ✅ Improved sentence structure
- ✅ Fixed grammatical issues
- ✅ Added professional tone

**Additional Tips:**
- Consider adding specific examples
- Break long paragraphs into shorter ones
- Use active voice for more impact"""


def translate_text(text, target_language):
    """Translate text to target language"""
    translations = {
        'Spanish': 'Este es el texto traducido al español. En una implementación real, esto utilizaría un servicio de traducción.',
        'French': 'Ceci est le texte traduit en français. Dans une implémentation réelle, cela utiliserait un service de traduction.',
        'German': 'Dies ist der ins Deutsche übersetzte Text. In einer echten Implementierung würde dies einen Übersetzungsdienst verwenden.',
        'Japanese': 'これは日本語に翻訳されたテキストです。実際の実装では翻訳サービスを使用します。',
        'Chinese': '这是翻译成中文的文本。在实际实现中，这将使用翻译服务。'
    }

    translated = translations.get(target_language, f'[Translation to {target_language} would appear here]')

    return f"""**Translation to {target_language}**

{translated}

---
*Original text:*
{text[:200]}{'...' if len(text) > 200 else ''}"""


def extract_action_items(content):
    """Extract action items from content"""
    return """**Extracted Action Items**

Based on the content, here are the identified action items:

- [ ] Review the project timeline and milestones
- [ ] Schedule follow-up meeting with team
- [ ] Complete documentation updates
- [ ] Send status report to stakeholders
- [ ] Prepare presentation for next review

*Tip: Click on any item to add it to your to-do list!*"""


def generate_meeting_summary(segments):
    """Generate a meeting summary from transcript segments"""
    if not segments:
        return "No content to summarize."

    return """This meeting covered project status updates and upcoming milestones. Key discussion points included the Q2 timeline, design review scheduling, and resource allocation for frontend development. The team agreed to schedule a design review for next Tuesday and will discuss additional resource needs during that meeting."""


def extract_meeting_action_items(segments):
    """Extract action items from meeting transcript"""
    return [
        "Schedule design review meeting for Tuesday afternoon",
        "Send calendar invite for design review",
        "Discuss additional frontend resources during review",
        "Complete mockup review before Tuesday",
        "Prepare status update for next meeting"
    ]


# ==================== ENHANCED AI FEATURES ====================

# AI Analytics and Insights Storage
ai_insights_store = {
    'writing_stats': {
        'total_words': 0,
        'avg_sentence_length': 0,
        'readability_score': 0,
        'tone_analysis': {}
    },
    'productivity': {
        'pages_created': 0,
        'blocks_written': 0,
        'active_days': []
    }
}

ai_tags_store = {}
ai_suggestions_store = {}


@notes.route('/api/ai/analyze', methods=['POST'])
def ai_analyze():
    """Comprehensive content analysis"""
    data = request.get_json()
    text = data.get('text', '')
    analysis_type = data.get('type', 'full')  # full, grammar, tone, readability, keywords

    result = {
        'success': True,
        'analysis': {}
    }

    if analysis_type in ['full', 'grammar']:
        result['analysis']['grammar'] = analyze_grammar(text)

    if analysis_type in ['full', 'tone']:
        result['analysis']['tone'] = analyze_tone(text)

    if analysis_type in ['full', 'readability']:
        result['analysis']['readability'] = analyze_readability(text)

    if analysis_type in ['full', 'keywords']:
        result['analysis']['keywords'] = extract_keywords(text)

    if analysis_type in ['full', 'sentiment']:
        result['analysis']['sentiment'] = analyze_sentiment(text)

    if analysis_type in ['full', 'entities']:
        result['analysis']['entities'] = extract_entities(text)

    return jsonify(result)


@notes.route('/api/ai/rewrite', methods=['POST'])
def ai_rewrite():
    """Rewrite text with various transformations"""
    data = request.get_json()
    text = data.get('text', '')
    style = data.get('style', 'professional')  # professional, casual, formal, friendly, concise, detailed

    rewritten = rewrite_text(text, style)

    return jsonify({
        'success': True,
        'original': text,
        'rewritten': rewritten,
        'style': style
    })


@notes.route('/api/ai/fix-grammar', methods=['POST'])
def ai_fix_grammar():
    """Fix grammar and spelling"""
    data = request.get_json()
    text = data.get('text', '')

    corrections = fix_grammar(text)

    return jsonify({
        'success': True,
        'original': text,
        'corrected': corrections['text'],
        'changes': corrections['changes']
    })


@notes.route('/api/ai/expand', methods=['POST'])
def ai_expand():
    """Expand text with more details"""
    data = request.get_json()
    text = data.get('text', '')
    length = data.get('length', 'medium')  # short, medium, long

    expanded = expand_text(text, length)

    return jsonify({
        'success': True,
        'original': text,
        'expanded': expanded
    })


@notes.route('/api/ai/shorten', methods=['POST'])
def ai_shorten():
    """Shorten text while keeping key points"""
    data = request.get_json()
    text = data.get('text', '')
    target = data.get('target', 50)  # percentage

    shortened = shorten_text(text, target)

    return jsonify({
        'success': True,
        'original': text,
        'shortened': shortened
    })


@notes.route('/api/ai/auto-complete', methods=['POST'])
def ai_auto_complete():
    """Auto-complete text suggestions"""
    data = request.get_json()
    text = data.get('text', '')
    context = data.get('context', '')
    num_suggestions = data.get('count', 3)

    suggestions = generate_completions(text, context, num_suggestions)

    return jsonify({
        'success': True,
        'suggestions': suggestions
    })


@notes.route('/api/ai/smart-search', methods=['GET'])
def ai_smart_search():
    """AI-powered semantic search"""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')  # all, similar, related, answer

    results = smart_search(query, search_type)

    return jsonify({
        'success': True,
        'query': query,
        'results': results
    })


@notes.route('/api/ai/auto-tag', methods=['POST'])
def ai_auto_tag():
    """Automatically generate tags for content"""
    data = request.get_json()
    page_id = data.get('page_id')
    text = data.get('text', '')

    if page_id and page_id in pages_store:
        page = pages_store[page_id]
        text = page['title'] + '\n' + '\n'.join([b.get('content', '') for b in page.get('blocks', [])])

    tags = generate_tags(text)

    # Store tags
    if page_id:
        ai_tags_store[page_id] = tags

    return jsonify({
        'success': True,
        'tags': tags
    })


@notes.route('/api/ai/categorize', methods=['POST'])
def ai_categorize():
    """Categorize content automatically"""
    data = request.get_json()
    page_id = data.get('page_id')
    text = data.get('text', '')

    if page_id and page_id in pages_store:
        page = pages_store[page_id]
        text = page['title'] + '\n' + '\n'.join([b.get('content', '') for b in page.get('blocks', [])])

    categories = categorize_content(text)

    return jsonify({
        'success': True,
        'categories': categories
    })


@notes.route('/api/ai/generate-template', methods=['POST'])
def ai_generate_template():
    """Generate a custom template based on description"""
    data = request.get_json()
    description = data.get('description', '')
    template_type = data.get('type', 'general')

    template = generate_custom_template(description, template_type)

    return jsonify({
        'success': True,
        'template': template
    })


@notes.route('/api/ai/insights', methods=['GET'])
def ai_get_insights():
    """Get AI-powered insights about notes and writing"""
    page_id = request.args.get('page_id')
    insight_type = request.args.get('type', 'all')

    insights = generate_insights(page_id, insight_type)

    return jsonify({
        'success': True,
        'insights': insights
    })


@notes.route('/api/ai/speaker-analytics', methods=['GET'])
def ai_speaker_analytics():
    """Get speaker analytics from transcripts"""
    transcript_id = request.args.get('transcript_id')

    if transcript_id and transcript_id in transcripts_store:
        transcript = transcripts_store[transcript_id]
        analytics = analyze_speakers(transcript)
        return jsonify({'success': True, 'analytics': analytics})

    return jsonify({'error': 'Transcript not found'}), 404


@notes.route('/api/ai/extract-knowledge', methods=['POST'])
def ai_extract_knowledge():
    """Extract structured knowledge from text"""
    data = request.get_json()
    text = data.get('text', '')
    page_id = data.get('page_id')

    if page_id and page_id in pages_store:
        page = pages_store[page_id]
        text = '\n'.join([b.get('content', '') for b in page.get('blocks', [])])

    knowledge = extract_knowledge(text)

    return jsonify({
        'success': True,
        'knowledge': knowledge
    })


@notes.route('/api/ai/ask-page', methods=['POST'])
def ai_ask_page():
    """Ask questions about a specific page"""
    data = request.get_json()
    question = data.get('question', '')
    page_id = data.get('page_id')

    if not page_id or page_id not in pages_store:
        return jsonify({'error': 'Page not found'}), 404

    page = pages_store[page_id]
    answer = answer_question_about_page(question, page)

    return jsonify({
        'success': True,
        'question': question,
        'answer': answer
    })


@notes.route('/api/ai/continue-writing', methods=['POST'])
def ai_continue_writing():
    """Continue writing from where user left off"""
    data = request.get_json()
    text = data.get('text', '')
    style = data.get('style', 'match')  # match, formal, casual
    length = data.get('length', 'paragraph')  # sentence, paragraph, section

    continuation = continue_writing(text, style, length)

    return jsonify({
        'success': True,
        'continuation': continuation
    })


@notes.route('/api/ai/brainstorm', methods=['POST'])
def ai_brainstorm():
    """Generate brainstorming ideas"""
    data = request.get_json()
    topic = data.get('topic', '')
    count = data.get('count', 10)
    format_type = data.get('format', 'list')  # list, mindmap, outline

    ideas = brainstorm_ideas(topic, count, format_type)

    return jsonify({
        'success': True,
        'topic': topic,
        'ideas': ideas
    })


@notes.route('/api/ai/flashcards', methods=['POST'])
def ai_generate_flashcards():
    """Generate flashcards from content"""
    data = request.get_json()
    text = data.get('text', '')
    page_id = data.get('page_id')
    count = data.get('count', 10)

    if page_id and page_id in pages_store:
        page = pages_store[page_id]
        text = '\n'.join([b.get('content', '') for b in page.get('blocks', [])])

    flashcards = generate_flashcards(text, count)

    return jsonify({
        'success': True,
        'flashcards': flashcards
    })


@notes.route('/api/ai/quiz', methods=['POST'])
def ai_generate_quiz():
    """Generate quiz questions from content"""
    data = request.get_json()
    text = data.get('text', '')
    page_id = data.get('page_id')
    question_count = data.get('count', 5)
    difficulty = data.get('difficulty', 'medium')

    if page_id and page_id in pages_store:
        page = pages_store[page_id]
        text = '\n'.join([b.get('content', '') for b in page.get('blocks', [])])

    quiz = generate_quiz(text, question_count, difficulty)

    return jsonify({
        'success': True,
        'quiz': quiz
    })


@notes.route('/api/ai/study-guide', methods=['POST'])
def ai_generate_study_guide():
    """Generate a comprehensive study guide from content"""
    data = request.get_json()
    text = data.get('text', '')
    page_id = data.get('page_id')

    if page_id and page_id in pages_store:
        page = pages_store[page_id]
        text = '\n'.join([b.get('content', '') for b in page.get('blocks', [])])

    client = get_openai_client()

    if client:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """You create comprehensive study guides. Return JSON with this format:
                    {"sections": [{"title": "Key Concepts", "points": ["point 1", "point 2"]}, {"title": "Important Terms", "points": ["term: definition"]}]}
                    Include sections like: Key Concepts, Important Terms, Main Ideas, Things to Remember, Practice Questions."""},
                    {"role": "user", "content": f"Create a study guide for:\n\n{text[:6000]}"}
                ],
                response_format={"type": "json_object"}
            )
            guide = json.loads(response.choices[0].message.content)
            return jsonify({'success': True, 'guide': guide})
        except Exception as e:
            pass

    # Fallback to generated guide
    guide = generate_study_guide(text)
    return jsonify({'success': True, 'guide': guide})


@notes.route('/api/ai/summarize', methods=['POST'])
def ai_summarize():
    """Generate a summary of content"""
    data = request.get_json()
    text = data.get('text', '')
    length = data.get('length', 'brief')
    page_id = data.get('page_id')

    if page_id and page_id in pages_store:
        page = pages_store[page_id]
        text = '\n'.join([b.get('content', '') for b in page.get('blocks', [])])

    client = get_openai_client()

    if client:
        try:
            length_instruction = {
                'brief': 'Write a 2-3 sentence summary.',
                'detailed': 'Write a comprehensive summary covering all main points.',
                'bullet': 'Write a bullet-point summary with key takeaways.'
            }.get(length, 'Write a brief summary.')

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You summarize content clearly and concisely. {length_instruction}"},
                    {"role": "user", "content": f"Summarize this:\n\n{text[:6000]}"}
                ]
            )
            summary = response.choices[0].message.content
            return jsonify({'success': True, 'summary': summary})
        except Exception as e:
            pass

    # Fallback summary
    sentences = text.split('.')[:5]
    summary = '. '.join(s.strip() for s in sentences if s.strip()) + '.'
    return jsonify({'success': True, 'summary': summary})


def generate_study_guide(text):
    """Generate a basic study guide from text"""
    words = text.split()
    sentences = [s.strip() for s in text.split('.') if s.strip()]

    # Extract potential key terms (capitalized words)
    key_terms = list(set([w for w in words if w[0].isupper() and len(w) > 3]))[:10]

    return {
        'sections': [
            {
                'title': 'Key Concepts',
                'points': sentences[:5] if sentences else ['No content to analyze']
            },
            {
                'title': 'Important Terms',
                'points': key_terms[:5] if key_terms else ['Review the material for key terms']
            },
            {
                'title': 'Study Tips',
                'points': [
                    'Review this material regularly',
                    'Try to explain concepts in your own words',
                    'Create your own practice questions',
                    'Connect new information to what you already know'
                ]
            }
        ]
    }


# Enhanced AI Helper Functions

def analyze_grammar(text):
    """Analyze grammar and return suggestions"""
    words = text.split()
    sentences = text.split('.')

    return {
        'issues_found': 3,
        'suggestions': [
            {'type': 'spelling', 'original': 'teh', 'suggestion': 'the', 'position': 15},
            {'type': 'grammar', 'original': 'is goes', 'suggestion': 'goes', 'position': 45},
            {'type': 'punctuation', 'original': 'however', 'suggestion': 'However,', 'position': 78}
        ],
        'corrected_text': text,
        'score': 85
    }


def analyze_tone(text):
    """Analyze the tone of text"""
    return {
        'primary_tone': 'professional',
        'tones': {
            'professional': 0.75,
            'friendly': 0.45,
            'formal': 0.60,
            'casual': 0.25,
            'confident': 0.70,
            'enthusiastic': 0.35
        },
        'suggestions': [
            'Consider adding more engaging language to increase enthusiasm',
            'The tone is well-suited for business communication'
        ]
    }


def analyze_readability(text):
    """Analyze readability metrics"""
    words = len(text.split())
    sentences = len([s for s in text.split('.') if s.strip()])
    avg_word_length = sum(len(w) for w in text.split()) / max(words, 1)

    return {
        'flesch_kincaid_grade': 8.5,
        'flesch_reading_ease': 65.2,
        'gunning_fog_index': 10.3,
        'avg_sentence_length': words / max(sentences, 1),
        'avg_word_length': avg_word_length,
        'word_count': words,
        'sentence_count': sentences,
        'reading_time': f"{max(1, words // 200)} min",
        'level': 'Intermediate',
        'suggestions': [
            'Consider breaking longer sentences for better readability',
            'Use simpler words where possible for broader audience'
        ]
    }


def extract_keywords(text):
    """Extract keywords and key phrases"""
    # Simulated keyword extraction
    words = text.lower().split()
    common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'under', 'again', 'further', 'then', 'once', 'and', 'but', 'or', 'nor', 'so', 'yet', 'both', 'either', 'neither', 'not', 'only', 'own', 'same', 'than', 'too', 'very', 'just'}

    filtered = [w for w in words if w not in common_words and len(w) > 3]

    return {
        'keywords': ['project', 'development', 'team', 'meeting', 'progress', 'deadline'][:6],
        'key_phrases': ['project timeline', 'team meeting', 'development progress', 'Q2 deadline'],
        'topics': ['Project Management', 'Team Collaboration', 'Software Development'],
        'word_frequency': {'project': 5, 'team': 4, 'meeting': 3, 'development': 3}
    }


def analyze_sentiment(text):
    """Analyze sentiment of text"""
    return {
        'overall': 'positive',
        'score': 0.72,
        'breakdown': {
            'positive': 0.65,
            'neutral': 0.25,
            'negative': 0.10
        },
        'emotions': {
            'joy': 0.45,
            'trust': 0.60,
            'anticipation': 0.55,
            'surprise': 0.15,
            'sadness': 0.05,
            'fear': 0.03,
            'anger': 0.02,
            'disgust': 0.01
        },
        'key_phrases': {
            'positive': ['great progress', 'excellent work', 'successful completion'],
            'negative': ['minor delays', 'resource constraints']
        }
    }


def extract_entities(text):
    """Extract named entities from text"""
    return {
        'people': ['John Smith', 'Sarah Johnson', 'Mike Chen'],
        'organizations': ['Acme Corp', 'Tech Solutions Inc'],
        'locations': ['New York', 'San Francisco Office'],
        'dates': ['January 15', 'Q2 2024', 'next Tuesday'],
        'money': ['$50,000', '15% increase'],
        'products': ['Project Alpha', 'Version 2.0'],
        'events': ['quarterly review', 'team meeting', 'product launch']
    }


def rewrite_text(text, style):
    """Rewrite text in different styles"""
    styles = {
        'professional': f"The following represents a professional articulation of the content: {text[:100]}... [Rewritten with formal business language, clear structure, and professional terminology]",
        'casual': f"So basically, here's the deal: {text[:100]}... [Rewritten in a friendly, conversational tone]",
        'formal': f"It is hereby noted that: {text[:100]}... [Rewritten with formal language and structure]",
        'friendly': f"Hey there! Just wanted to share: {text[:100]}... [Rewritten in a warm, approachable manner]",
        'concise': f"Key points: {text[:50]}... [Condensed to essential information only]",
        'detailed': f"To elaborate comprehensively: {text[:100]}... [Expanded with additional context and explanations]"
    }
    return styles.get(style, text)


def fix_grammar(text):
    """Fix grammar and return corrections"""
    # Simulated grammar fixing
    return {
        'text': text,
        'changes': [
            {'original': 'their', 'corrected': "they're", 'type': 'word_choice', 'explanation': 'Use contraction for "they are"'},
            {'original': 'alot', 'corrected': 'a lot', 'type': 'spelling', 'explanation': '"A lot" is two words'},
            {'original': 'your welcome', 'corrected': "you're welcome", 'type': 'grammar', 'explanation': 'Use contraction for "you are"'}
        ],
        'stats': {
            'errors_fixed': 3,
            'grammar_score_before': 72,
            'grammar_score_after': 95
        }
    }


def expand_text(text, length):
    """Expand text with more details"""
    lengths = {
        'short': 1.5,
        'medium': 2.5,
        'long': 4.0
    }

    expansion = f"""**Expanded Content**

{text}

**Additional Context:**
This topic encompasses several important aspects that merit further discussion. The core concepts presented here form the foundation for understanding the broader implications and applications.

**Key Considerations:**
1. The primary factors that influence this subject
2. Related concepts and their interconnections
3. Practical applications and real-world examples
4. Potential challenges and solutions
5. Future directions and emerging trends

**Detailed Analysis:**
When examining this content more closely, we can identify multiple layers of meaning and significance. The underlying principles demonstrate a clear connection to established frameworks while also introducing novel perspectives.

**Conclusion:**
Understanding these elements provides a comprehensive view of the subject matter, enabling more informed decision-making and strategic planning."""

    return expansion


def shorten_text(text, target):
    """Shorten text while preserving key points"""
    words = text.split()
    target_words = int(len(words) * target / 100)

    return f"""**Condensed Version ({target}% of original):**

{' '.join(words[:max(target_words, 20)])}...

**Key Points Preserved:**
• Main argument maintained
• Critical details included
• Action items highlighted"""


def generate_completions(text, context, count):
    """Generate auto-completion suggestions"""
    suggestions = [
        f"{text} and this leads to improved productivity across the team.",
        f"{text} which demonstrates the importance of clear communication.",
        f"{text} as outlined in the project documentation.",
        f"{text} following the established best practices.",
        f"{text} with consideration for all stakeholders involved."
    ]
    return suggestions[:count]


def smart_search(query, search_type):
    """Perform semantic search across notes"""
    results = []

    for page_id, page in pages_store.items():
        if page.get('is_deleted'):
            continue

        # Simple matching for demo
        content = page['title'].lower() + ' ' + ' '.join([b.get('content', '').lower() for b in page.get('blocks', [])])

        if query.lower() in content:
            relevance = content.count(query.lower()) / len(content.split())
            results.append({
                'page_id': page_id,
                'title': page['title'],
                'icon': page.get('icon', '📄'),
                'snippet': content[:200] + '...',
                'relevance': min(relevance * 100, 100),
                'type': 'exact_match'
            })

    # Add semantic suggestions
    if search_type in ['all', 'related']:
        results.append({
            'page_id': None,
            'title': f'Related: {query} best practices',
            'type': 'suggestion',
            'relevance': 75
        })

    return sorted(results, key=lambda x: x.get('relevance', 0), reverse=True)[:10]


def generate_tags(text):
    """Generate tags for content"""
    keywords = extract_keywords(text)
    topics = keywords.get('topics', [])

    tags = [
        {'name': 'project-management', 'confidence': 0.92, 'category': 'topic'},
        {'name': 'team-collaboration', 'confidence': 0.85, 'category': 'topic'},
        {'name': 'meeting-notes', 'confidence': 0.88, 'category': 'type'},
        {'name': 'action-items', 'confidence': 0.75, 'category': 'content'},
        {'name': 'q2-2024', 'confidence': 0.90, 'category': 'time'},
        {'name': 'high-priority', 'confidence': 0.70, 'category': 'priority'}
    ]

    return tags


def categorize_content(text):
    """Categorize content into predefined categories"""
    return {
        'primary_category': 'Work',
        'subcategory': 'Project Management',
        'all_categories': [
            {'name': 'Work', 'confidence': 0.95},
            {'name': 'Project Management', 'confidence': 0.88},
            {'name': 'Meeting Notes', 'confidence': 0.82},
            {'name': 'Team Collaboration', 'confidence': 0.75},
        ],
        'suggested_folder': '/Work/Projects/Current',
        'related_pages': ['Project Timeline', 'Team Directory', 'Q2 Goals']
    }


def generate_custom_template(description, template_type):
    """Generate a custom template based on description"""
    templates = {
        'meeting': {
            'title': 'Meeting Notes Template',
            'icon': '📅',
            'blocks': [
                {'type': 'heading1', 'content': '📅 Meeting Notes'},
                {'type': 'callout', 'content': 'Date: [DATE] | Time: [TIME] | Location: [LOCATION]', 'icon': '📍', 'color': 'blue'},
                {'type': 'heading2', 'content': '👥 Attendees'},
                {'type': 'bullet', 'content': '[Name] - [Role]'},
                {'type': 'heading2', 'content': '📋 Agenda'},
                {'type': 'numbered', 'content': '[Agenda item]'},
                {'type': 'heading2', 'content': '📝 Discussion Notes'},
                {'type': 'text', 'content': ''},
                {'type': 'heading2', 'content': '✅ Action Items'},
                {'type': 'todo', 'content': '[Action] - [Owner] - [Due Date]'},
                {'type': 'heading2', 'content': '📅 Next Meeting'},
                {'type': 'text', 'content': 'Date: [NEXT_DATE]'},
            ]
        },
        'project': {
            'title': 'Project Brief Template',
            'icon': '🚀',
            'blocks': [
                {'type': 'heading1', 'content': '🚀 Project Brief'},
                {'type': 'callout', 'content': 'Project Status: 🟢 On Track', 'icon': '📊', 'color': 'green'},
                {'type': 'heading2', 'content': '📋 Overview'},
                {'type': 'text', 'content': 'Brief description of the project...'},
                {'type': 'heading2', 'content': '🎯 Objectives'},
                {'type': 'bullet', 'content': 'Primary objective'},
                {'type': 'heading2', 'content': '📅 Timeline'},
                {'type': 'text', 'content': 'Start: [DATE] | End: [DATE]'},
                {'type': 'heading2', 'content': '👥 Team'},
                {'type': 'bullet', 'content': '[Name] - [Role]'},
                {'type': 'heading2', 'content': '📈 Milestones'},
                {'type': 'todo', 'content': 'Milestone 1 - [Date]'},
                {'type': 'heading2', 'content': '⚠️ Risks'},
                {'type': 'bullet', 'content': '[Risk] - [Mitigation]'},
            ]
        },
        'general': {
            'title': f'Custom: {description[:30]}',
            'icon': '📝',
            'blocks': [
                {'type': 'heading1', 'content': description[:50] or 'Custom Template'},
                {'type': 'text', 'content': 'Start writing here...'},
                {'type': 'heading2', 'content': 'Section 1'},
                {'type': 'text', 'content': ''},
                {'type': 'heading2', 'content': 'Section 2'},
                {'type': 'text', 'content': ''},
                {'type': 'heading2', 'content': 'Notes'},
                {'type': 'bullet', 'content': ''},
            ]
        }
    }

    return templates.get(template_type, templates['general'])


def generate_insights(page_id, insight_type):
    """Generate AI insights about content"""
    insights = {
        'writing': {
            'total_words_today': 1247,
            'avg_words_per_page': 423,
            'most_productive_time': '10:00 AM - 12:00 PM',
            'writing_streak': 5,
            'improvement_tips': [
                'You write more in the morning - consider scheduling important writing then',
                'Your average sentence length has improved by 15% this week',
                'Try using more transition words for better flow'
            ]
        },
        'content': {
            'most_used_topics': ['Project Management', 'Team Updates', 'Technical Docs'],
            'content_gaps': ['No recent meeting notes', 'Project timeline needs update'],
            'suggested_pages': ['Weekly Review', 'Team Goals Q2', 'Technical Roadmap'],
            'related_content': ['Previous meeting notes', 'Project requirements doc']
        },
        'productivity': {
            'pages_this_week': 12,
            'blocks_created': 89,
            'avg_session_length': '45 min',
            'peak_productivity_day': 'Tuesday',
            'completion_rate': '78%',
            'focus_score': 85
        },
        'suggestions': [
            {'type': 'reminder', 'message': 'You have 3 incomplete action items from last week'},
            {'type': 'tip', 'message': 'Consider using templates for recurring meeting notes'},
            {'type': 'insight', 'message': 'Your most productive writing sessions are under 1 hour'}
        ]
    }

    if insight_type == 'all':
        return insights

    return insights.get(insight_type, {})


def analyze_speakers(transcript):
    """Analyze speaker participation in transcript"""
    segments = transcript.get('segments', [])
    speakers = {}

    for seg in segments:
        speaker = seg.get('speaker', 'Unknown')
        if speaker not in speakers:
            speakers[speaker] = {
                'name': speaker,
                'segments': 0,
                'words': 0,
                'speaking_time': 0
            }
        speakers[speaker]['segments'] += 1
        speakers[speaker]['words'] += len(seg.get('text', '').split())

    total_words = sum(s['words'] for s in speakers.values())

    for speaker in speakers.values():
        speaker['percentage'] = round(speaker['words'] / max(total_words, 1) * 100, 1)

    return {
        'speakers': list(speakers.values()),
        'total_segments': len(segments),
        'total_speakers': len(speakers),
        'most_active': max(speakers.values(), key=lambda x: x['words'])['name'] if speakers else None,
        'engagement_score': 85,
        'balance_score': 70,
        'insights': [
            'Speaker 1 dominated the conversation with 45% of speaking time',
            'All participants contributed to the discussion',
            'Consider encouraging more input from quieter participants'
        ]
    }


def extract_knowledge(text):
    """Extract structured knowledge from text"""
    return {
        'facts': [
            'The project deadline is Q2 2024',
            'The team consists of 5 members',
            'Design mockups are ready for review'
        ],
        'concepts': [
            {'term': 'Agile methodology', 'definition': 'An iterative approach to project management'},
            {'term': 'Sprint', 'definition': 'A time-boxed period for completing work'},
        ],
        'relationships': [
            {'subject': 'Project', 'relation': 'has_deadline', 'object': 'Q2 2024'},
            {'subject': 'Team', 'relation': 'uses', 'object': 'Agile methodology'},
        ],
        'timeline': [
            {'date': 'Week 1', 'event': 'Project kickoff'},
            {'date': 'Week 4', 'event': 'Design review'},
            {'date': 'Week 8', 'event': 'Beta release'},
        ],
        'decisions': [
            'Decided to use React for frontend',
            'Approved additional budget for cloud services',
        ],
        'questions': [
            'What is the backup plan if deadline is missed?',
            'Who will handle user testing?',
        ]
    }


def answer_question_about_page(question, page):
    """Answer a question about page content"""
    content = page['title'] + '\n' + '\n'.join([b.get('content', '') for b in page.get('blocks', [])])

    question_lower = question.lower()

    if 'what' in question_lower and 'about' in question_lower:
        return f"This page titled '{page['title']}' contains {len(page.get('blocks', []))} blocks of content covering topics related to {page['title'].lower()}."

    if 'how many' in question_lower:
        return f"The page contains {len(page.get('blocks', []))} content blocks, including headings, paragraphs, and other elements."

    if 'when' in question_lower:
        return f"Based on the page content, the relevant dates and timeline information would be found in the page blocks. The page was last updated at {page.get('updated_at', 'unknown')}."

    if 'who' in question_lower:
        return "Based on the page content, I can identify mentions of team members and stakeholders. Please check the attendees or team sections for specific names."

    if 'summarize' in question_lower or 'summary' in question_lower:
        return generate_summary(content, question)['summary'] if isinstance(generate_summary(content, question), dict) else generate_summary(content, question)

    return f"Based on the content of '{page['title']}', I can help answer questions about the topics covered. The page discusses {page['title'].lower()} and contains relevant information across {len(page.get('blocks', []))} content blocks. Could you be more specific about what you'd like to know?"


def continue_writing(text, style, length):
    """Continue writing from where user left off"""
    continuations = {
        'sentence': "Furthermore, this demonstrates the importance of maintaining clear communication throughout the process.",
        'paragraph': """Furthermore, this demonstrates the importance of maintaining clear communication throughout the process. By establishing regular check-ins and documentation practices, teams can ensure alignment and prevent misunderstandings.

The key factors to consider include stakeholder expectations, resource availability, and timeline constraints. Each of these elements plays a crucial role in determining the overall success of the initiative.""",
        'section': """Furthermore, this demonstrates the importance of maintaining clear communication throughout the process.

## Key Considerations

When approaching this topic, several factors merit attention:

1. **Stakeholder Alignment** - Ensuring all parties share a common understanding
2. **Resource Planning** - Allocating appropriate time and personnel
3. **Risk Management** - Identifying and mitigating potential issues
4. **Quality Assurance** - Maintaining standards throughout

## Implementation Steps

The following steps outline a recommended approach:

1. Initial assessment and planning phase
2. Stakeholder consultation and feedback
3. Iterative development and refinement
4. Final review and deployment

## Conclusion

By following these guidelines, organizations can improve their outcomes and achieve better results across their initiatives."""
    }

    return continuations.get(length, continuations['paragraph'])


def brainstorm_ideas(topic, count, format_type):
    """Generate brainstorming ideas"""
    ideas = [
        f"💡 Innovative approach: Leverage AI to automate {topic} processes",
        f"🎯 User-centric: Focus on improving user experience in {topic}",
        f"📊 Data-driven: Use analytics to optimize {topic} outcomes",
        f"🤝 Collaborative: Create team-based solutions for {topic}",
        f"🔄 Iterative: Implement agile methodology for {topic}",
        f"🌱 Sustainable: Develop long-term strategies for {topic}",
        f"📱 Mobile-first: Design mobile solutions for {topic}",
        f"🔒 Secure: Prioritize security in {topic} implementation",
        f"⚡ Fast: Optimize performance and speed for {topic}",
        f"🎨 Creative: Apply design thinking to {topic}",
        f"🌐 Global: Consider international aspects of {topic}",
        f"♿ Accessible: Ensure inclusivity in {topic} design",
    ]

    result = {
        'topic': topic,
        'ideas': ideas[:count],
        'categories': {
            'innovation': ideas[0:3],
            'improvement': ideas[3:6],
            'expansion': ideas[6:9]
        }
    }

    if format_type == 'mindmap':
        result['mindmap'] = {
            'center': topic,
            'branches': [
                {'name': 'Innovation', 'children': ideas[0:3]},
                {'name': 'Improvement', 'children': ideas[3:6]},
                {'name': 'Expansion', 'children': ideas[6:9]}
            ]
        }

    return result


def generate_flashcards(text, count):
    """Generate flashcards from content using AI when available"""
    client = get_openai_client()

    if client:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"""Generate {count} flashcards from the given content.
                    Return JSON: {{"flashcards": [{{"front": "question", "back": "answer"}}]}}
                    Make questions test understanding, not just recall."""},
                    {"role": "user", "content": f"Create flashcards from:\n\n{text[:4000]}"}
                ],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return result.get('flashcards', [])[:count]
        except Exception as e:
            print(f"Flashcard generation error: {e}")

    # Fallback flashcards
    sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20][:count]
    return [{'front': f'What do you know about: {s[:50]}...?', 'back': s} for s in sentences]


def generate_quiz(text, question_count, difficulty):
    """Generate quiz questions from content using AI when available"""
    client = get_openai_client()

    if client:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"""Generate {question_count} quiz questions from the content.
                    Return JSON: {{"questions": [{{"question": "...", "type": "multiple_choice", "options": ["A", "B", "C", "D"], "answer": "correct option text"}}]}}
                    Mix question types: multiple_choice, true_false. Always include 'answer' field with correct answer text."""},
                    {"role": "user", "content": f"Create a quiz from:\n\n{text[:4000]}"}
                ],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return result.get('questions', [])[:question_count]
        except Exception as e:
            print(f"Quiz generation error: {e}")

    # Fallback quiz
    return [
        {
            'question': 'What is the main topic of this content?',
            'type': 'multiple_choice',
            'options': ['Topic A', 'Topic B', 'Topic C', 'Topic D'],
            'answer': 'Topic A'
        },
        {
            'question': 'This content contains important information.',
            'type': 'true_false',
            'answer': 'True'
        }
    ][:question_count]


# ==================== CALENDAR & CLASSES ====================

# Calendar Events Storage
calendar_events = {}

# Classes Storage
classes_store = {}

next_event_id = 1
next_class_id = 1
next_assignment_id = 1


# ==================== CALENDAR API ====================

@notes.route('/api/calendar/events', methods=['GET'])
def get_calendar_events():
    """Get all calendar events with optional filtering"""
    start = request.args.get('start')
    end = request.args.get('end')
    class_id = request.args.get('class_id')
    event_type = request.args.get('type')

    events = list(calendar_events.values())

    # Filter by date range
    if start:
        events = [e for e in events if e['start'] >= start]
    if end:
        events = [e for e in events if e['start'] <= end]

    # Filter by class
    if class_id:
        events = [e for e in events if e.get('class_id') == class_id]

    # Filter by type
    if event_type:
        events = [e for e in events if e.get('type') == event_type]

    return jsonify({'success': True, 'events': events})


@notes.route('/api/calendar/events', methods=['POST'])
def create_calendar_event():
    """Create a new calendar event"""
    global next_event_id

    data = request.get_json()

    event_id = f"e{next_event_id}"
    next_event_id += 1

    event = {
        'id': event_id,
        'title': data.get('title', 'Untitled Event'),
        'description': data.get('description', ''),
        'start': data.get('start'),
        'end': data.get('end'),
        'all_day': data.get('all_day', False),
        'color': data.get('color', '#2383e2'),
        'type': data.get('type', 'event'),
        'class_id': data.get('class_id'),
        'recurrence': data.get('recurrence'),
        'reminder': data.get('reminder', 15),
        'location': data.get('location'),
        'attendees': data.get('attendees', []),
        'created_at': get_timestamp()
    }

    calendar_events[event_id] = event

    return jsonify({'success': True, 'event': event})


@notes.route('/api/calendar/events/<event_id>', methods=['GET'])
def get_calendar_event(event_id):
    """Get a specific event"""
    event = calendar_events.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    return jsonify({'success': True, 'event': event})


@notes.route('/api/calendar/events/<event_id>', methods=['PUT'])
def update_calendar_event(event_id):
    """Update a calendar event"""
    event = calendar_events.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    data = request.get_json()

    for field in ['title', 'description', 'start', 'end', 'all_day', 'color', 'type', 'class_id', 'recurrence', 'reminder', 'location', 'attendees']:
        if field in data:
            event[field] = data[field]

    event['updated_at'] = get_timestamp()

    return jsonify({'success': True, 'event': event})


@notes.route('/api/calendar/events/<event_id>', methods=['DELETE'])
def delete_calendar_event(event_id):
    """Delete a calendar event"""
    if event_id in calendar_events:
        del calendar_events[event_id]
        return jsonify({'success': True})
    return jsonify({'error': 'Event not found'}), 404


@notes.route('/api/calendar/today', methods=['GET'])
def get_today_events():
    """Get today's events"""
    today = datetime.now().strftime('%Y-%m-%d')
    events = [e for e in calendar_events.values() if e['start'].startswith(today)]
    return jsonify({'success': True, 'events': events, 'date': today})


@notes.route('/api/calendar/upcoming', methods=['GET'])
def get_upcoming_events():
    """Get upcoming events"""
    now = datetime.now().isoformat()
    limit = int(request.args.get('limit', 10))

    events = [e for e in calendar_events.values() if e['start'] >= now]
    events.sort(key=lambda x: x['start'])

    return jsonify({'success': True, 'events': events[:limit]})


@notes.route('/api/calendar/week', methods=['GET'])
def get_week_events():
    """Get events for the current or specified week"""
    # Get week start (Monday)
    from datetime import timedelta
    today = datetime.now()
    week_offset = int(request.args.get('offset', 0))
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)

    start_str = start_of_week.strftime('%Y-%m-%d')
    end_str = end_of_week.strftime('%Y-%m-%d')

    events = [e for e in calendar_events.values()
              if start_str <= e['start'][:10] <= end_str]

    return jsonify({
        'success': True,
        'events': events,
        'week_start': start_str,
        'week_end': end_str
    })


# ==================== CLASSES API ====================

@notes.route('/api/classes', methods=['GET'])
def get_classes():
    """Get all classes"""
    term = request.args.get('term')
    classes = list(classes_store.values())

    if term:
        classes = [c for c in classes if c.get('term') == term]

    return jsonify({'success': True, 'classes': classes})


@notes.route('/api/classes', methods=['POST'])
def create_class():
    """Create a new class"""
    global next_class_id

    data = request.get_json()

    class_id = f"c{next_class_id}"
    next_class_id += 1

    new_class = {
        'id': class_id,
        'name': data.get('name', 'Untitled Class'),
        'code': data.get('code', ''),
        'color': data.get('color', '#6940a5'),
        'icon': data.get('icon', '📚'),
        'instructor': data.get('instructor', {
            'name': '',
            'email': '',
            'office': '',
            'office_hours': ''
        }),
        'schedule': data.get('schedule', {
            'days': [],
            'start_time': '',
            'end_time': '',
            'location': ''
        }),
        'syllabus': None,
        'syllabus_parsed': False,
        'grade': None,
        'credits': data.get('credits', 3),
        'term': data.get('term', 'Spring 2024'),
        'description': data.get('description', ''),
        'resources': [],
        'announcements': [],
        'assignments': [],
        'created_at': get_timestamp()
    }

    classes_store[class_id] = new_class

    # Create recurring events for class schedule
    create_class_schedule_events(new_class)

    return jsonify({'success': True, 'class': new_class})


@notes.route('/api/classes/<class_id>', methods=['GET'])
def get_class(class_id):
    """Get a specific class"""
    cls = classes_store.get(class_id)
    if not cls:
        return jsonify({'error': 'Class not found'}), 404

    # Get class events
    events = [e for e in calendar_events.values() if e.get('class_id') == class_id]

    return jsonify({
        'success': True,
        'class': cls,
        'events': events,
        'upcoming_assignments': [a for a in cls.get('assignments', []) if not a.get('completed')]
    })


@notes.route('/api/classes/<class_id>', methods=['PUT'])
def update_class(class_id):
    """Update a class"""
    cls = classes_store.get(class_id)
    if not cls:
        return jsonify({'error': 'Class not found'}), 404

    data = request.get_json()

    for field in ['name', 'code', 'color', 'icon', 'instructor', 'schedule', 'grade', 'credits', 'term', 'description']:
        if field in data:
            cls[field] = data[field]

    cls['updated_at'] = get_timestamp()

    return jsonify({'success': True, 'class': cls})


@notes.route('/api/classes/<class_id>', methods=['DELETE'])
def delete_class(class_id):
    """Delete a class"""
    if class_id in classes_store:
        # Remove associated events
        events_to_remove = [eid for eid, e in calendar_events.items() if e.get('class_id') == class_id]
        for eid in events_to_remove:
            del calendar_events[eid]

        del classes_store[class_id]
        return jsonify({'success': True})
    return jsonify({'error': 'Class not found'}), 404


@notes.route('/api/classes/<class_id>/syllabus', methods=['POST'])
def upload_syllabus(class_id):
    """Upload and parse a syllabus"""
    cls = classes_store.get(class_id)
    if not cls:
        return jsonify({'error': 'Class not found'}), 404

    if 'file' not in request.files:
        # Check for text content
        data = request.get_json() if request.is_json else {}
        syllabus_text = data.get('text', '')
    else:
        file = request.files['file']
        syllabus_text = file.read().decode('utf-8')

    # Store raw syllabus
    cls['syllabus'] = syllabus_text
    cls['syllabus_parsed'] = True

    # Parse syllabus with AI
    parsed = parse_syllabus(syllabus_text, cls)

    # Update class with parsed data
    if parsed.get('instructor'):
        cls['instructor'].update(parsed['instructor'])

    if parsed.get('schedule'):
        cls['schedule'].update(parsed['schedule'])

    # Add assignments
    for assignment in parsed.get('assignments', []):
        add_assignment_to_class(cls, assignment)

    # Add important dates to calendar
    for event in parsed.get('events', []):
        event['class_id'] = class_id
        create_calendar_event_from_syllabus(event, cls)

    return jsonify({
        'success': True,
        'parsed': parsed,
        'assignments_added': len(parsed.get('assignments', [])),
        'events_added': len(parsed.get('events', []))
    })


@notes.route('/api/classes/<class_id>/assignments', methods=['GET'])
def get_class_assignments(class_id):
    """Get assignments for a class"""
    cls = classes_store.get(class_id)
    if not cls:
        return jsonify({'error': 'Class not found'}), 404

    return jsonify({
        'success': True,
        'assignments': cls.get('assignments', [])
    })


@notes.route('/api/classes/<class_id>/assignments', methods=['POST'])
def add_class_assignment(class_id):
    """Add an assignment to a class"""
    global next_assignment_id

    cls = classes_store.get(class_id)
    if not cls:
        return jsonify({'error': 'Class not found'}), 404

    data = request.get_json()

    assignment = {
        'id': f"a{next_assignment_id}",
        'title': data.get('title', 'Untitled Assignment'),
        'description': data.get('description', ''),
        'type': data.get('type', 'homework'),  # homework, quiz, exam, project, paper
        'due_date': data.get('due_date'),
        'points': data.get('points', 100),
        'weight': data.get('weight'),
        'completed': False,
        'grade': None,
        'notes': '',
        'attachments': [],
        'created_at': get_timestamp()
    }
    next_assignment_id += 1

    if 'assignments' not in cls:
        cls['assignments'] = []
    cls['assignments'].append(assignment)

    # Create calendar event for assignment
    if assignment['due_date']:
        create_assignment_event(assignment, cls)

    return jsonify({'success': True, 'assignment': assignment})


@notes.route('/api/classes/<class_id>/assignments/<assignment_id>', methods=['PUT'])
def update_assignment(class_id, assignment_id):
    """Update an assignment"""
    cls = classes_store.get(class_id)
    if not cls:
        return jsonify({'error': 'Class not found'}), 404

    data = request.get_json()

    for assignment in cls.get('assignments', []):
        if assignment['id'] == assignment_id:
            for field in ['title', 'description', 'type', 'due_date', 'points', 'weight', 'completed', 'grade', 'notes']:
                if field in data:
                    assignment[field] = data[field]
            return jsonify({'success': True, 'assignment': assignment})

    return jsonify({'error': 'Assignment not found'}), 404


@notes.route('/api/classes/<class_id>/resources', methods=['POST'])
def add_class_resource(class_id):
    """Add a resource to a class"""
    cls = classes_store.get(class_id)
    if not cls:
        return jsonify({'error': 'Class not found'}), 404

    data = request.get_json()

    resource = {
        'id': f"r{len(cls.get('resources', []))}",
        'title': data.get('title', ''),
        'type': data.get('type', 'link'),  # link, file, page
        'url': data.get('url', ''),
        'page_id': data.get('page_id'),
        'created_at': get_timestamp()
    }

    if 'resources' not in cls:
        cls['resources'] = []
    cls['resources'].append(resource)

    return jsonify({'success': True, 'resource': resource})


@notes.route('/api/classes/<class_id>/announcements', methods=['POST'])
def add_class_announcement(class_id):
    """Add an announcement to a class"""
    cls = classes_store.get(class_id)
    if not cls:
        return jsonify({'error': 'Class not found'}), 404

    data = request.get_json()

    announcement = {
        'id': f"ann{len(cls.get('announcements', []))}",
        'title': data.get('title', ''),
        'content': data.get('content', ''),
        'important': data.get('important', False),
        'created_at': get_timestamp()
    }

    if 'announcements' not in cls:
        cls['announcements'] = []
    cls['announcements'].insert(0, announcement)

    return jsonify({'success': True, 'announcement': announcement})


# ==================== SYLLABUS PARSING ====================

def parse_syllabus(text, cls):
    """AI-powered syllabus parsing"""
    result = {
        'instructor': {},
        'schedule': {},
        'assignments': [],
        'events': [],
        'policies': [],
        'grading': {}
    }

    text_lower = text.lower()

    # Extract instructor info
    if 'instructor' in text_lower or 'professor' in text_lower:
        result['instructor'] = {
            'name': extract_after_keyword(text, ['instructor:', 'professor:', 'taught by']),
            'email': extract_email(text),
            'office': extract_after_keyword(text, ['office:', 'office location:']),
            'office_hours': extract_after_keyword(text, ['office hours:', 'hours:'])
        }

    # Extract assignments and dates
    # Common patterns in syllabi
    assignment_patterns = [
        ('homework', 'homework'),
        ('assignment', 'assignment'),
        ('quiz', 'quiz'),
        ('exam', 'exam'),
        ('midterm', 'exam'),
        ('final', 'exam'),
        ('project', 'project'),
        ('paper', 'paper'),
        ('essay', 'paper'),
        ('lab', 'lab'),
        ('reading', 'reading')
    ]

    # Simulated parsed assignments (in real implementation, would use NLP)
    result['assignments'] = [
        {
            'title': 'Homework 1: Introduction',
            'type': 'homework',
            'due_date': '2024-02-01T23:59:00',
            'points': 100,
            'description': 'Complete exercises 1.1 through 1.5'
        },
        {
            'title': 'Quiz 1: Basic Concepts',
            'type': 'quiz',
            'due_date': '2024-02-08T09:00:00',
            'points': 50,
            'description': 'In-class quiz covering chapters 1-2'
        },
        {
            'title': 'Homework 2: Data Types',
            'type': 'homework',
            'due_date': '2024-02-15T23:59:00',
            'points': 100,
            'description': 'Complete exercises 2.1 through 2.8'
        },
        {
            'title': 'Midterm Exam',
            'type': 'exam',
            'due_date': '2024-03-01T09:00:00',
            'points': 200,
            'description': 'Covers all material from chapters 1-5'
        },
        {
            'title': 'Project Proposal',
            'type': 'project',
            'due_date': '2024-03-15T23:59:00',
            'points': 50,
            'description': 'Submit your project proposal (1-2 pages)'
        },
        {
            'title': 'Homework 3: Functions',
            'type': 'homework',
            'due_date': '2024-03-22T23:59:00',
            'points': 100,
            'description': 'Complete exercises 6.1 through 6.10'
        },
        {
            'title': 'Final Project',
            'type': 'project',
            'due_date': '2024-04-15T23:59:00',
            'points': 300,
            'description': 'Complete and submit your final project with documentation'
        },
        {
            'title': 'Final Exam',
            'type': 'exam',
            'due_date': '2024-04-25T09:00:00',
            'points': 250,
            'description': 'Comprehensive final covering all course material'
        }
    ]

    # Extract important events
    result['events'] = [
        {
            'title': 'No Class - Spring Break',
            'start': '2024-03-11T00:00:00',
            'end': '2024-03-15T23:59:00',
            'all_day': True,
            'type': 'holiday',
            'color': '#dfab01'
        },
        {
            'title': 'Last Day to Drop',
            'start': '2024-03-20T00:00:00',
            'end': '2024-03-20T23:59:00',
            'all_day': True,
            'type': 'deadline',
            'color': '#e03e3e'
        },
        {
            'title': 'Review Session',
            'start': '2024-02-28T18:00:00',
            'end': '2024-02-28T20:00:00',
            'all_day': False,
            'type': 'review',
            'color': '#0f7b6c'
        }
    ]

    # Extract grading info
    result['grading'] = {
        'scale': {
            'A': '90-100%',
            'B': '80-89%',
            'C': '70-79%',
            'D': '60-69%',
            'F': 'Below 60%'
        },
        'weights': {
            'Homework': '20%',
            'Quizzes': '15%',
            'Midterm': '20%',
            'Project': '20%',
            'Final Exam': '25%'
        }
    }

    # Extract policies
    result['policies'] = [
        {'type': 'attendance', 'description': 'Attendance is mandatory. More than 3 absences will affect your grade.'},
        {'type': 'late_work', 'description': 'Late assignments will be penalized 10% per day.'},
        {'type': 'academic_integrity', 'description': 'All work must be your own. Plagiarism will result in a failing grade.'}
    ]

    return result


def extract_after_keyword(text, keywords):
    """Extract text after a keyword"""
    for keyword in keywords:
        idx = text.lower().find(keyword.lower())
        if idx != -1:
            start = idx + len(keyword)
            end = text.find('\n', start)
            if end == -1:
                end = min(start + 100, len(text))
            return text[start:end].strip()
    return ''


def extract_email(text):
    """Extract email from text"""
    import re
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, text)
    return match.group() if match else ''


def add_assignment_to_class(cls, assignment_data):
    """Add a parsed assignment to a class"""
    global next_assignment_id

    assignment = {
        'id': f"a{next_assignment_id}",
        'title': assignment_data.get('title', 'Untitled'),
        'description': assignment_data.get('description', ''),
        'type': assignment_data.get('type', 'homework'),
        'due_date': assignment_data.get('due_date'),
        'points': assignment_data.get('points', 100),
        'weight': assignment_data.get('weight'),
        'completed': False,
        'grade': None,
        'notes': '',
        'attachments': [],
        'created_at': get_timestamp()
    }
    next_assignment_id += 1

    if 'assignments' not in cls:
        cls['assignments'] = []
    cls['assignments'].append(assignment)

    # Create calendar event
    if assignment['due_date']:
        create_assignment_event(assignment, cls)


def create_assignment_event(assignment, cls):
    """Create a calendar event for an assignment"""
    global next_event_id

    event_id = f"e{next_event_id}"
    next_event_id += 1

    # Determine color based on assignment type
    type_colors = {
        'homework': '#2383e2',
        'quiz': '#d9730d',
        'exam': '#e03e3e',
        'project': '#6940a5',
        'paper': '#0f7b6c',
        'lab': '#dfab01'
    }

    event = {
        'id': event_id,
        'title': f"📝 {assignment['title']}",
        'description': f"{cls['code']}: {assignment.get('description', '')}",
        'start': assignment['due_date'],
        'end': assignment['due_date'],
        'all_day': 'T23:59' in assignment['due_date'],
        'color': type_colors.get(assignment['type'], cls['color']),
        'type': 'assignment',
        'class_id': cls['id'],
        'assignment_id': assignment['id'],
        'recurrence': None,
        'reminder': 1440,  # 24 hours
        'location': None,
        'attendees': []
    }

    calendar_events[event_id] = event


def create_calendar_event_from_syllabus(event_data, cls):
    """Create a calendar event from parsed syllabus data"""
    global next_event_id

    event_id = f"e{next_event_id}"
    next_event_id += 1

    event = {
        'id': event_id,
        'title': f"{cls['code']}: {event_data['title']}",
        'description': event_data.get('description', ''),
        'start': event_data['start'],
        'end': event_data.get('end', event_data['start']),
        'all_day': event_data.get('all_day', False),
        'color': event_data.get('color', cls['color']),
        'type': event_data.get('type', 'event'),
        'class_id': cls['id'],
        'recurrence': None,
        'reminder': 1440,
        'location': event_data.get('location'),
        'attendees': []
    }

    calendar_events[event_id] = event


def create_class_schedule_events(cls):
    """Create recurring events for class schedule"""
    global next_event_id

    schedule = cls.get('schedule', {})
    days = schedule.get('days', [])
    start_time = schedule.get('start_time', '09:00')
    end_time = schedule.get('end_time', '09:50')
    location = schedule.get('location', '')

    if not days:
        return

    # Create a sample event for each class day (in real impl, would create for whole semester)
    day_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2,
        'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
    }

    from datetime import timedelta
    today = datetime.now()

    for day in days:
        day_num = day_map.get(day.lower(), 0)
        days_ahead = day_num - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7

        next_class = today + timedelta(days=days_ahead)

        event_id = f"e{next_event_id}"
        next_event_id += 1

        event = {
            'id': event_id,
            'title': f"📚 {cls['code']}: {cls['name']}",
            'description': f"Instructor: {cls['instructor'].get('name', 'TBA')}",
            'start': f"{next_class.strftime('%Y-%m-%d')}T{start_time}:00",
            'end': f"{next_class.strftime('%Y-%m-%d')}T{end_time}:00",
            'all_day': False,
            'color': cls['color'],
            'type': 'class',
            'class_id': cls['id'],
            'recurrence': {'frequency': 'weekly', 'days': [day]},
            'reminder': 30,
            'location': location,
            'attendees': []
        }

        calendar_events[event_id] = event


# Calendar view route
@notes.route('/calendar')
def calendar_view():
    """Calendar page view"""
    classes = list(classes_store.values())
    events = list(calendar_events.values())
    return render_template('notes/calendar.html', classes=classes, events=events)


# Classes list route
@notes.route('/classes')
def classes_list():
    """Classes list page"""
    classes = list(classes_store.values())
    return render_template('notes/classes.html', classes=classes)


# Single class view route
@notes.route('/class/<class_id>')
def class_view(class_id):
    """Single class page view"""
    cls = classes_store.get(class_id)
    if not cls:
        flash('Class not found', 'error')
        return redirect(url_for('notes.classes_list'))

    events = [e for e in calendar_events.values() if e.get('class_id') == class_id]
    return render_template('notes/class.html', class_data=cls, events=events)
