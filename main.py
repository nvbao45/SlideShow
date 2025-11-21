#!/usr/bin/env python3
from flask import Flask, render_template, send_from_directory, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import os
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

PHOTOS_FOLDER = 'photos'
DURATIONS_FILE = 'durations.json'
DEFAULT_DURATION_SECONDS = 8  # default display time per image if not configured
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

app.config['UPLOAD_FOLDER'] = PHOTOS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_photos():
    photos = []
    if os.path.exists(PHOTOS_FOLDER):
        for filename in os.listdir(PHOTOS_FOLDER):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                photos.append(filename)
    photos.sort()
    return photos

def load_durations():
    if not os.path.exists(DURATIONS_FILE):
        return {}
    try:
        with open(DURATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure only existing photos retained and numeric values
            cleaned = {}
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    cleaned[k] = float(v)
            return cleaned
    except Exception:
        return {}

def save_durations(durations):
    try:
        with open(DURATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(durations, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

@app.route('/')
def index():
    photos = get_photos()
    durations = load_durations()
    return render_template('index.html', photos=photos, durations=durations, default_duration=DEFAULT_DURATION_SECONDS)

@app.route('/admin')
def admin():
    photos = get_photos()
    durations = load_durations()
    return render_template('admin.html', photos=photos, durations=durations, default_duration=DEFAULT_DURATION_SECONDS)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files[]' not in request.files:
        flash('No file part')
        return redirect(url_for('admin'))
    
    files = request.files.getlist('files[]')
    uploaded_count = 0
    
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            uploaded_count += 1
    
    flash(f'Successfully uploaded {uploaded_count} file(s)')
    return redirect(url_for('admin'))

@app.route('/durations', methods=['POST'])
def update_durations():
    photos = set(get_photos())
    durations = load_durations()
    # Expect form fields: durations[filename] = seconds
    for key, value in request.form.items():
        if key.startswith('durations[') and key.endswith(']'):
            filename = key[len('durations['):-1]
            if filename in photos:
                try:
                    sec = float(value)
                    if sec <= 0:
                        # remove if non-positive
                        if filename in durations:
                            del durations[filename]
                    else:
                        durations[filename] = sec
                except ValueError:
                    continue
    # Remove entries for deleted photos
    durations = {k: v for k, v in durations.items() if k in photos}
    if save_durations(durations):
        flash('Durations updated successfully')
    else:
        flash('Failed to save durations')
    return redirect(url_for('admin'))

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    try:
        filepath = os.path.join(PHOTOS_FOLDER, secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': True, 'message': 'File deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/photos/<filename>')
def photo(filename):
    return send_from_directory(PHOTOS_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
