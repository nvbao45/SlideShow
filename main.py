#!/usr/bin/env python3
from flask import Flask, render_template, send_from_directory, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import json

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'your-secret-key-change-this-in-production'

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Default admin account (should be changed in production)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = generate_password_hash('admin123')  # Password: admin123

@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_USERNAME:
        return User(user_id)
    return None

PHOTOS_FOLDER = 'photos'
STATIC_FOLDER = 'static'
DURATIONS_FILE = 'durations.json'
DEFAULT_DURATION_SECONDS = 8  # fallback default display time per image if not configured
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

def load_default_duration():
    if not os.path.exists(DURATIONS_FILE):
        return DEFAULT_DURATION_SECONDS
    try:
        with open(DURATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            val = data.get('__default')
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
            return DEFAULT_DURATION_SECONDS
    except Exception:
        return DEFAULT_DURATION_SECONDS

@app.route('/')
def index():
    photos = get_photos()
    durations = load_durations()
    default_duration = load_default_duration()
    return render_template('index.html', photos=photos, durations=durations, default_duration=default_duration)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            user = User(username)
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin'))
        else:
            flash('Invalid username or password!')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!')
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    photos = get_photos()
    durations = load_durations()
    default_duration = load_default_duration()
    return render_template('admin.html', photos=photos, durations=durations, default_duration=default_duration)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'files[]' not in request.files:
        flash('No file part')
        return redirect(url_for('admin'))
    
    files = request.files.getlist('files[]')
    uploaded_count = 0
    renamed_count = 0

    for file in files:
        if file and file.filename and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            filename = original_filename
            target_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(target_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while True:
                    candidate = f"{base}-{counter}{ext}"
                    candidate_path = os.path.join(app.config['UPLOAD_FOLDER'], candidate)
                    if not os.path.exists(candidate_path):
                        filename = candidate
                        renamed_count += 1
                        break
                    counter += 1
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            uploaded_count += 1

    if uploaded_count == 0:
        flash('No valid files uploaded')
    else:
        if renamed_count:
            flash(f'Uploaded {uploaded_count} file(s). {renamed_count} duplicate name(s) were auto-renamed.')
        else:
            flash(f'Uploaded {uploaded_count} file(s).')
    return redirect(url_for('admin'))

@app.route('/durations', methods=['POST'])
@login_required
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
    # Default duration update
    default_value = request.form.get('default_duration')
    if default_value:
        try:
            dv = float(default_value)
            if dv > 0:
                durations['__default'] = dv
        except ValueError:
            pass
    # Remove entries for deleted photos
    cleaned = {}
    for k, v in durations.items():
        if k == '__default' or k in photos:
            cleaned[k] = v
    durations = cleaned
    if save_durations(durations):
        flash('Durations updated successfully')
    else:
        flash('Failed to save durations')
    return redirect(url_for('admin'))

@app.route('/delete/<filename>', methods=['POST'])
@login_required
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
