from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory
import sqlite3
import json
import os
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)
DB_FILE = 'bookmarks.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 数据库初始化 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bookmarks (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, remark TEXT, target_accounts TEXT, done_accounts TEXT, enable_stats INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, avatar TEXT, remark TEXT, account_number TEXT, link TEXT)''')
    try: c.execute('ALTER TABLE profiles ADD COLUMN account_number TEXT')
    except: pass
    try: c.execute('ALTER TABLE profiles ADD COLUMN link TEXT')
    except: pass
    c.execute('SELECT value FROM settings WHERE key = ?', ('global_accounts',))
    if c.fetchone() is None:
        default_accs = json.dumps(['账号1', '账号2', '账号3'])
        c.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('global_accounts', default_accs))
    c.execute('SELECT value FROM settings WHERE key = ?', ('address_book',))
    if c.fetchone() is None:
        c.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('address_book', '[]'))
    defaults = {'left_bg': '#2c3e50', 'left_text': '#ffffff', 'right_bg': '#ffffff', 'right_text': '#333333'}
    for k, v in defaults.items():
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))
    conn.commit()
    conn.close()

def get_settings_dict():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT key, value FROM settings')
    rows = c.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

# --- HTML 模板 ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>小记管理控制台</title>
    <style>
        :root {
            --left-bg: {{ settings.get('left_bg', '#2c3e50') }};
            --left-text: {{ settings.get('left_text', '#ffffff') }};
            --right-bg: {{ settings.get('right_bg', '#ffffff') }};
            --right-text: {{ settings.get('right_text', '#333333') }};
            
            --bg-color: #f4f4f9;
            --text-color: #333;
            --card-bg: white;
            --input-bg: white;
            --border-color: #ddd;
            --shadow: 0 4px 12px rgba(0,0,0,0.08);
            --addr-card-bg: rgba(0,0,0,0.2); 
            --addr-text: rgba(255,255,255,0.7); 
            --btn-bg: #e0e0e0;
            --highlight: #3498db;
            
            --left-sidebar-width: 320px;
            --drawer-width: 800px; 
        }

        .sidebar-left { color: var(--left-text) !important; }
        .sidebar-left .addr-row { color: var(--left-text); opacity: 0.8; }
        .sidebar-left .sidebar-desc { color: var(--left-text); opacity: 0.6; }
        .sidebar-left .setting-label { color: var(--left-text); }
        .sidebar-left h3 { border-bottom-color: rgba(255,255,255,0.2); }

        .sidebar-right { color: var(--right-text) !important; }
        .profile-name { color: var(--right-text); }
        .profile-remark { color: var(--right-text); opacity: 0.7; }
        .profile-bottom { color: var(--right-text); background: rgba(128,128,128,0.1); }

        [data-theme="dark"] {
            --bg-color: #121212;
            --text-color: #e0e0e0;
            --card-bg: #1e1e1e;
            --input-bg: #2d2d2d;
            --border-color: #444;
            --shadow: 0 4px 12px rgba(0,0,0,0.6);
            --btn-bg: #333;
            --highlight: #5dade2;
            --left-bg: #0f1519; --left-text: #ccc;
            --right-bg: #1e1e1e; --right-text: #ccc;
        }

        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; 
            margin: 0; background: var(--bg-color); color: var(--text-color); 
            display: flex; min-height: 100vh; overflow-x: hidden;
        }
        
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(128,128,128,0.3); border-radius: 3px; }

        .theme-switch-wrapper { position: fixed; top: 15px; right: 20px; z-index: 9999; }
        .theme-btn { 
            background: var(--btn-bg); border: 1px solid var(--border-color); color: var(--text-color); 
            padding: 8px 15px; cursor: pointer; border-radius: 20px; font-size: 14px; font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2); transition: all 0.2s;
        }
        .theme-btn:hover { transform: scale(1.05); }

        .sidebar-left { 
            width: var(--left-sidebar-width); background: var(--left-bg); padding: 20px; 
            display: flex; flex-direction: column; position: fixed; left: 0; top: 0; bottom: 0; 
            overflow-y: auto; z-index: 100; box-shadow: 2px 0 10px rgba(0,0,0,0.2); transition: background 0.3s;
        }

        .drawer-handle {
            position: fixed; top: 50%; right: 0; transform: translateY(-50%);
            background: var(--highlight); color: white; padding: 15px 5px; cursor: pointer; z-index: 2000;
            border-top-left-radius: 8px; border-bottom-left-radius: 8px;
            writing-mode: vertical-rl; text-orientation: upright; font-weight: bold;
            box-shadow: -2px 0 10px rgba(0,0,0,0.2); transition: right 0.3s ease; letter-spacing: 2px;
        }
        .drawer-handle:hover { padding-left: 10px; }

        .sidebar-right {
            position: fixed; top: 0; right: 0; bottom: 0; width: var(--drawer-width); max-width: 90vw;
            background: var(--right-bg); z-index: 3000; transform: translateX(100%); transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: -5px 0 20px rgba(0,0,0,0.2); padding: 20px; display: flex; flex-direction: column; overflow-y: auto;
        }
        .sidebar-right.open { transform: translateX(0); }

        .drawer-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 2500;
            display: none; backdrop-filter: blur(2px); opacity: 0; transition: opacity 0.3s;
        }
        .drawer-overlay.open { display: block; opacity: 1; }

        .right-header { font-size: 1.5em; font-weight: bold; margin-bottom: 20px; text-align: center; border-bottom: 2px solid var(--highlight); padding-bottom: 10px; color: var(--highlight); display: flex; justify-content: space-between; align-items: center;}
        .close-drawer-btn { font-size: 0.8em; cursor: pointer; color: var(--right-text); opacity: 0.5; border: 1px solid var(--border-color); padding: 5px 10px; border-radius: 4px; }
        .close-drawer-btn:hover { opacity: 1; background: var(--btn-bg); }

        #profile-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 15px; padding-bottom: 20px; }

        .profile-card {
            background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px;
            display: flex; flex-direction: column; position: relative; transition: transform 0.2s; box-shadow: 0 2px 5px var(--shadow); height: 100%;
        }
        .profile-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px var(--shadow); z-index: 2; }

        .profile-top { display: flex; gap: 10px; margin-bottom: 10px; align-items: center; }
        .profile-avatar {
            width: 50px; height: 50px; border-radius: 50%; object-fit: cover;
            border: 2px solid var(--border-color); background: #eee; cursor: pointer; transition: transform 0.2s;
        }
        .profile-avatar:hover { transform: scale(1.1); border-color: var(--highlight); }

        .profile-info { flex: 1; overflow: hidden; display: flex; flex-direction: column; justify-content: center; }
        .profile-name { font-weight: bold; font-size: 1.05em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .profile-remark { font-size: 0.8em; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .profile-bottom { border-radius: 4px; padding: 6px; display: flex; align-items: center; justify-content: space-between; font-size: 0.85em; margin-top: auto; }
        .acc-num { font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px; }
        
        .profile-actions { position: absolute; top: 5px; right: 5px; display: flex; gap: 5px; }
        .action-icon { cursor: pointer; font-size: 1.1em; opacity: 0.2; transition: 0.2s; }
        .profile-card:hover .action-icon { opacity: 0.6; }
        .action-icon:hover { opacity: 1; }
        
        .main-content { margin-left: var(--left-sidebar-width); width: calc(100% - var(--left-sidebar-width)); padding: 40px; display: flex; flex-direction: column; align-items: center; }
        .content-container { width: 100%; max-width: 900px; }

        .sidebar-left h3 { margin-top: 0; border-bottom: 1px solid; padding-bottom: 10px; margin-bottom: 15px; font-size: 1.1em; }
        .sidebar-desc { font-size: 0.8em; margin-bottom: 10px; }
        .setting-box { background: rgba(128,128,128,0.1); padding: 15px; border-radius: 8px; margin-bottom: 25px; border: 1px solid rgba(128,128,128,0.2); }
        .setting-label { font-size: 0.9em; font-weight: bold; margin-bottom: 8px; display: block; }
        .account-editor { width: 100%; height: 80px; background: rgba(255,255,255,0.9); border: none; border-radius: 4px; padding: 8px; margin-bottom: 8px; font-family: monospace; resize: vertical; font-size: 0.9em; color: #333; }
        .btn-save-settings { width: 100%; padding: 8px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.9em; }
        
        .addr-card { background: var(--addr-card-bg); padding: 12px; border-radius: 6px; font-size: 0.85em; border: 1px solid rgba(128,128,128,0.2); }
        .addr-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px dashed; padding-bottom: 5px; border-color: rgba(128,128,128,0.3); }
        .addr-name { font-size: 1.2em; font-weight: 800; color: var(--highlight); } 
        .addr-val { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; font-family: monospace; background: rgba(0,0,0,0.3); padding: 2px 5px; border-radius: 3px; color: #ccc; }
        
        .btn-show-form { width: 100%; background: #27ae60; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 5px; }
        .add-addr-container { display: none; margin-top: 10px; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; }
        .add-addr-form input { padding: 8px; border-radius: 4px; border: none; font-size: 0.9em; background: #fff; width: 100%; margin-bottom: 5px; }
        .btn-submit-addr { background: #3498db; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%; }

        h2 { text-align: center; margin-bottom: 30px; color: var(--text-color); }
        .input-group { background: var(--card-bg); padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px var(--shadow); display: flex; gap: 10px; margin-bottom: 30px; border: 1px solid var(--border-color); }
        input[type="text"] { flex: 1; padding: 12px; border: 1px solid var(--border-color); border-radius: 6px; font-size: 16px; background: var(--input-bg); color: var(--text-color); }
        button.add-btn { padding: 0 25px; background: #27ae60; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 16px; }

        .list-group { list-style: none; padding: 0; }
        .list-item { background: var(--card-bg); border: 1px solid var(--border-color); padding: 20px; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 5px var(--shadow); transition: all 0.2s; }
        .list-item:hover { box-shadow: 0 5px 15px var(--shadow); }
        .list-item.stats-off { border-left: 5px solid #bdc3c7; }
        .list-item.pending { border-left: 5px solid #f1c40f; }
        .list-item.completed { border-left: 5px solid #2ecc71; background: rgba(46, 204, 113, 0.1); }

        .item-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; }
        .content-wrapper { flex: 1; margin-right: 15px; }
        .link-row { display: flex; align-items: center; gap: 10px; margin-bottom: 5px; flex-wrap: wrap; }
        .url-link { color: #2980b9; text-decoration: none; font-weight: 600; font-size: 1.1em; word-break: break-all; }
        .btn-copy { background: #ecf0f1; border: 1px solid #bdc3c7; color: #555; border-radius: 4px; padding: 2px 8px; font-size: 0.8em; cursor: pointer; display: inline-flex; align-items: center; }
        .btn-copy.copied { background: #2ecc71; color: white; border-color: #2ecc71; }
        
        .toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
        .btn-sm { padding: 5px 10px; font-size: 0.85em; background: #95a5a6; color: white; text-decoration: none; border-radius: 4px; border:none; cursor: pointer;}
        .btn-toggle { background: #1abc9c; }
        .btn-edit-info { background: #f39c12; }
        .btn-del { background: #e74c3c; margin-left: auto; }
        .btn-update { background: #3498db; color: white; padding: 6px 15px; border: none; border-radius: 4px; cursor: pointer; }

        .btn-copy-mini { font-size: 0.9em; cursor: pointer; color: inherit; border: none; background: none; padding: 0 2px; opacity: 0.6; }
        .btn-copy-mini:hover { opacity: 1; color: var(--highlight); }
        .icon-edit { color: #f39c12; }
        .icon-del { color: #e74c3c; }

        .add-profile-box { margin-top: 10px; padding: 15px; background: var(--input-bg); border: 1px dashed var(--border-color); border-radius: 8px; }
        .file-input { width: 100%; margin: 5px 0; font-size: 0.8em; }
        .edit-area { margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.02); display: none; }
        .edit-area textarea { width: 100%; padding: 5px; margin-bottom: 5px; border: 1px solid #ccc; font-family: monospace; }
        .stats-area { margin-top: 15px; padding-top: 15px; border-top: 1px dashed var(--border-color); }
        .checkbox-group { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px; }
        .cb-label { display: flex; align-items: center; gap: 5px; font-size: 0.9em; background: var(--input-bg); padding: 5px 10px; border-radius: 4px; cursor: pointer; border: 1px solid var(--border-color); }

        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 10000; }
        .modal-box { background: var(--card-bg); padding: 30px; border-radius: 10px; text-align: center; width: 360px; box-shadow: 0 5px 20px rgba(0,0,0,0.4); border: 1px solid var(--border-color); }
        .modal-box h3 { margin-top: 0; color: var(--text-color); margin-bottom: 15px; }
        #authPassword { width: 100%; margin: 20px 0; padding: 15px; border: 2px solid var(--highlight); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 24px; font-weight: bold; text-align: center; letter-spacing: 2px; }
        #authPassword:focus { outline: none; box-shadow: 0 0 10px rgba(52, 152, 219, 0.3); }
        .modal-buttons { display: flex; justify-content: space-between; margin-top: 20px; gap: 15px; }
        .btn-confirm { background-color: #3498db; color: white; padding: 12px 0; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; flex: 1; font-size: 16px; }
        .btn-cancel { background-color: #95a5a6; color: white; padding: 12px 0; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; flex: 1; font-size: 16px; }

        .modal-input-group { text-align: left; margin-bottom: 10px; }
        .modal-input-label { font-size: 0.85em; color: #888; margin-bottom: 4px; display: block; }
        .modal-input { width: 100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--input-bg); color: var(--text-color); }
        .color-picker-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; padding: 5px 0; border-bottom: 1px solid #eee; }
        input[type="color"] { border: none; width: 50px; height: 30px; cursor: pointer; background: none; }

        @media (max-width: 768px) {
            body { flex-direction: column; }
            .sidebar-left { width: 100%; position: relative; height: auto; }
            .main-content { margin-left: 0; width: 100%; padding: 20px; }
            .sidebar-right { width: 100%; max-width: 85vw; }
            #profile-list { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
        }
    </style>
</head>
<body>
    <div class="theme-switch-wrapper">
        <button class="theme-btn" onclick="toggleTheme()" id="themeBtn">☀️/🌙</button>
    </div>

    <div class="drawer-handle" onclick="toggleDrawer()">🎨 账户展馆</div>

    <div class="drawer-overlay" id="drawerOverlay" onclick="toggleDrawer()"></div>

    <aside class="sidebar-left">
        <h3>⚙️ 控制台</h3>
        <button onclick="openColorModal()" style="width:100%; padding:8px; background:linear-gradient(45deg, #ff9a9e, #fad0c4); color:#333; border:none; border-radius:4px; font-weight:bold; cursor:pointer; margin-bottom:20px;">🎨 界面颜色设置</button>
        <div class="setting-box">
            <span class="setting-label">📥 默认账户模板</span>
            <form action="/update_global_settings" method="post">
                <textarea name="global_accounts_str" class="account-editor">{{ global_accounts_str }}</textarea>
                <button type="submit" class="btn-save-settings">💾 保存模板</button>
            </form>
        </div>
        <div class="setting-box">
            <span class="setting-label">🏦 地址本</span>
            <div class="addr-list">
                {% for item in address_book %}
                <div class="addr-card">
                    <div class="addr-header">
                        <span class="addr-name">{{ item.name }}</span>
                        <div class="addr-actions">
                            <span class="btn-icon btn-edit-addr" 
                                  data-index="{{ loop.index0 }}" data-name="{{ item.name }}"
                                  data-addr="{{ item.addr }}" data-uid="{{ item.uid }}"
                                  onclick="openEditAddrModal(this)">✏️</span>
                            <span class="btn-icon btn-del-addr" onclick="triggerAuth('delete_addr', {{ loop.index0 }})">×</span>
                        </div>
                    </div>
                    {% if item.addr %}
                    <div class="addr-row">
                        <span style="font-size:0.8em; opacity:0.7;">Add:</span>
                        <span class="addr-val" title="{{ item.addr }}">{{ item.addr }}</span>
                        <button class="btn-copy-icon" data-val="{{ item.addr }}" onclick="copyContent(this.dataset.val, this)">Copy</button>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            <button id="btn-toggle-addr" class="btn-show-form" onclick="toggleAddrForm()">＋ 添加新备忘</button>
            <div id="addr-form-container" class="add-addr-container">
                <form id="realAddForm" action="/add_addr" method="post" class="add-addr-form" onsubmit="event.preventDefault(); triggerAuth('add_addr', this);">
                    <input type="text" name="name" placeholder="账户备注" required>
                    <input type="text" name="addr" placeholder="Address">
                    <input type="text" name="uid" placeholder="UID">
                    <button type="submit" class="btn-submit-addr">添加 (需密码)</button>
                </form>
            </div>
        </div>
        <div class="sidebar-desc" style="margin-top: auto; opacity: 0.5; text-align: center;">LegendVPS Tool v4.5 (Drawer Fixed)</div>
    </aside>

    <aside class="sidebar-right" id="rightDrawer">
        <div class="right-header">
            <span>🎨 账户展馆</span>
            <button class="close-drawer-btn" onclick="toggleDrawer()">收起 >></button>
        </div>
        
        <div id="profile-list">
            {% for p in profiles %}
            <div class="profile-card">
                <div class="profile-actions">
                    <span class="action-icon icon-edit"
                          data-id="{{ p.id }}" data-name="{{ p.name }}" data-remark="{{ p.remark }}"
                          data-acc="{{ p.account_number }}" data-link="{{ p.link }}"
                          onclick="openEditProfileModal(this)">✏️</span>
                    <span class="action-icon icon-del" onclick="triggerAuth('delete_profile', {{ p.id }})">×</span>
                </div>
                <div class="profile-top">
                    <a href="{{ p.link if p.link else '#' }}" target="_blank">
                        <img src="{{ url_for('uploaded_file', filename=p.avatar) }}" class="profile-avatar" onerror="this.src='https://via.placeholder.com/50?text=User'">
                    </a>
                    <div class="profile-info">
                        <div class="profile-name" title="{{ p.name }}">{{ p.name }}</div>
                        <div class="profile-remark" title="{{ p.remark }}">{{ p.remark }}</div>
                    </div>
                </div>
                {% if p.account_number %}
                <div class="profile-bottom">
                    <span class="acc-num" title="{{ p.account_number }}">{{ p.account_number }}</span>
                    <button class="btn-copy-mini" onclick="copyContent('{{ p.account_number }}', this)">📋</button>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        <button class="btn-show-form" onclick="document.getElementById('add-profile-form').style.display = 'block'">＋ 添加展示账户</button>
        <div id="add-profile-form" class="add-profile-box" style="display:none;">
            <form id="realProfileForm" action="/add_profile" method="post" enctype="multipart/form-data" onsubmit="event.preventDefault(); triggerAuth('add_profile', this);">
                <input type="text" name="name" placeholder="账户昵称" required class="file-input">
                <input type="text" name="remark" placeholder="备注信息" class="file-input">
                <input type="text" name="account_number" placeholder="账户号" class="file-input">
                <input type="text" name="link" placeholder="链接" class="file-input">
                <label style="font-size:0.8em;">头像:</label>
                <input type="file" name="file" class="file-input" accept="image/*" required>
                <button type="submit" class="btn-submit-addr" style="width:100%; margin-top:5px;">上传并添加</button>
            </form>
        </div>
    </aside>

    <main class="main-content">
        <div class="content-container">
            <h2>📋 小记管理</h2>
            <form action="/add" method="post" class="input-group">
                <input type="text" name="url" placeholder="任务链接 / 文字小记..." required>
                <input type="text" name="remark" placeholder="备注 (可选)" style="flex: 0.7;">
                <button type="submit" class="add-btn">＋ 发布</button>
            </form>
            <ul class="list-group">
                {% for item in items %}
                <li class="list-item {% if not item.enable_stats %}stats-off{% elif item.is_complete %}completed{% else %}pending{% endif %}">
                    <div class="item-header">
                        <div class="content-wrapper">
                            <div class="link-row">
                                <a href="{{ item.url }}" class="url-link" target="_blank">{{ item.url }}</a>
                                <button class="btn-copy" data-url="{{ item.url }}" onclick="copyContent(this.dataset.url, this)" title="复制内容">📋</button>
                            </div>
                            {% if item.remark %}<span class="remark">{{ item.remark }}</span>{% endif %}
                        </div>
                        {% if item.enable_stats %}
                            {% if item.is_complete %}<span class="badge badge-success">✅ 已完成</span>
                            {% else %}<span class="badge badge-warning">⏳ {{ item.done_count }} / {{ item.total_count }}</span>{% endif %}
                        {% else %}<span class="badge badge-gray">⚪ 统计关闭</span>{% endif %}
                    </div>
                    <div class="toolbar">
                        <a href="/toggle_stats/{{ item.id }}" class="btn-sm btn-toggle">{% if item.enable_stats %}👁️ 隐藏{% else %}📊 开启统计{% endif %}</a>
                        {% if item.enable_stats %}
                        <button type="button" class="btn-sm" onclick="toggleEdit({{ item.id }})">⚙️ 改账户</button>
                        <button type="button" class="btn-sm btn-edit-info" onclick="openEditTaskModal({{ item.id }}, '{{ item.url|replace("'", "\\'") }}', '{{ item.remark|replace("'", "\\'") }}')">✏️ 改内容</button>
                        {% endif %}
                        <span class="btn-sm btn-del" onclick="triggerAuth('delete_task', {{ item.id }})">🗑️ 删除</span>
                    </div>
                    {% if item.enable_stats %}
                        <form action="/update_item_accounts/{{ item.id }}" method="post" id="edit-{{ item.id }}" class="edit-area">
                            <textarea name="target_accounts_str">{{ item.target_accounts_str }}</textarea>
                            <button type="submit" class="btn-sm" style="background:#3498db; margin-top:5px;">保存修改</button>
                        </form>
                        <form action="/update_progress/{{ item.id }}" method="post" class="stats-area">
                            <div class="checkbox-group">
                                {% for acc in item.target_accounts %}
                                <label class="cb-label"><input type="checkbox" name="done_accounts" value="{{ acc }}" {% if acc in item.done_accounts %}checked{% endif %}> {{ acc }}</label>
                                {% endfor %}
                            </div>
                            <button type="submit" class="btn-update">更新进度</button>
                        </form>
                    {% endif %}
                </li>
                {% endfor %}
            </ul>
        </div>
    </main>

    <div class="modal-overlay" id="authModal">
        <div class="modal-box"><h3>请验证</h3><input type="password" id="authPassword" maxlength="10"><div class="modal-buttons"><button class="btn-cancel" onclick="closeModal('authModal')">取消</button><button class="btn-confirm" onclick="confirmAction()">确认</button></div></div>
    </div>
    <div class="modal-overlay" id="colorModal">
        <div class="modal-box"><h3>🎨 界面配色</h3><form id="colorForm" action="/save_theme" method="post" onsubmit="event.preventDefault(); triggerAuth('save_theme', this);"><div class="color-picker-row"><span class="color-picker-label">👈 左侧背景</span><input type="color" name="left_bg" value="{{ settings.get('left_bg', '#2c3e50') }}"></div><div class="color-picker-row"><span class="color-picker-label">👈 左侧文字</span><input type="color" name="left_text" value="{{ settings.get('left_text', '#ffffff') }}"></div><hr style="border:0; border-top:1px dashed #ddd; margin:15px 0;"><div class="color-picker-row"><span class="color-picker-label">👉 右侧背景</span><input type="color" name="right_bg" value="{{ settings.get('right_bg', '#ffffff') }}"></div><div class="color-picker-row"><span class="color-picker-label">👉 右侧文字</span><input type="color" name="right_text" value="{{ settings.get('right_text', '#333333') }}"></div><div class="modal-buttons"><button type="button" class="btn-cancel" onclick="closeModal('colorModal')">取消</button><button type="submit" class="btn-confirm">保存 (需密码)</button></div></form></div>
    </div>
    <div class="modal-overlay" id="editAddrModal">
        <div class="modal-box"><h3>✏️ 修改地址</h3><form id="editAddrForm" action="/edit_addr" method="post" onsubmit="event.preventDefault(); triggerAuth('edit_addr', this);"><input type="hidden" name="index" id="edit_index"><div class="modal-input-group"><label class="modal-input-label">备注:</label><input type="text" name="name" id="edit_name" class="modal-input" required></div><div class="modal-input-group"><label class="modal-input-label">Address:</label><input type="text" name="addr" id="edit_addr_val" class="modal-input"></div><div class="modal-input-group"><label class="modal-input-label">UID:</label><input type="text" name="uid" id="edit_uid_val" class="modal-input"></div><div class="modal-buttons"><button type="button" class="btn-cancel" onclick="closeModal('editAddrModal')">取消</button><button type="submit" class="btn-confirm">保存</button></div></form></div>
    </div>
    <div class="modal-overlay" id="editTaskModal">
        <div class="modal-box"><h3>✏️ 修改小记</h3><form id="editTaskForm" action="/edit_task_info" method="post" onsubmit="event.preventDefault(); triggerAuth('edit_task_info', this);"><input type="hidden" name="id" id="edit_task_id"><div class="modal-input-group"><label class="modal-input-label">内容:</label><input type="text" name="url" id="edit_task_url" class="modal-input" required></div><div class="modal-input-group"><label class="modal-input-label">备注:</label><input type="text" name="remark" id="edit_task_remark" class="modal-input"></div><div class="modal-buttons"><button type="button" class="btn-cancel" onclick="closeModal('editTaskModal')">取消</button><button type="submit" class="btn-confirm">保存</button></div></form></div>
    </div>
    <div class="modal-overlay" id="editProfileModal">
        <div class="modal-box"><h3>✏️ 修改展示</h3><form id="editProfileForm" action="/edit_profile" method="post" onsubmit="event.preventDefault(); triggerAuth('edit_profile', this);"><input type="hidden" name="id" id="edit_profile_id"><div class="modal-input-group"><label class="modal-input-label">昵称:</label><input type="text" name="name" id="edit_profile_name" class="modal-input" required></div><div class="modal-input-group"><label class="modal-input-label">备注:</label><input type="text" name="remark" id="edit_profile_remark" class="modal-input"></div><div class="modal-input-group"><label class="modal-input-label">账户号:</label><input type="text" name="account_number" id="edit_profile_acc" class="modal-input"></div><div class="modal-input-group"><label class="modal-input-label">链接:</label><input type="text" name="link" id="edit_profile_link" class="modal-input"></div><div class="modal-buttons"><button type="button" class="btn-cancel" onclick="closeModal('editProfileModal')">取消</button><button type="submit" class="btn-confirm">保存</button></div></form></div>
    </div>
    
    <script>
        function toggleTheme() { try { const c = document.documentElement.getAttribute("data-theme"); const n = c === "dark" ? "light" : "dark"; document.documentElement.setAttribute("data-theme", n); localStorage.setItem("theme", n); } catch(e) {} }
        document.addEventListener("DOMContentLoaded", function() { const s = localStorage.getItem("theme") || "light"; document.documentElement.setAttribute("data-theme", s); const p = document.getElementById('authPassword'); if(p){ p.addEventListener("keypress", function(e) { if (e.key === "Enter") confirmAction(); }); } });
        // Drawer Toggle
        function toggleDrawer() {
            var drawer = document.getElementById('rightDrawer');
            var overlay = document.getElementById('drawerOverlay');
            if (drawer.classList.contains('open')) { drawer.classList.remove('open'); overlay.classList.remove('open'); }
            else { drawer.classList.add('open'); overlay.classList.add('open'); }
        }
        // Toggles
        function toggleEdit(id) { var el = document.getElementById('edit-' + id); el.style.display = el.style.display === 'block' ? 'none' : 'block'; }
        function toggleAddrForm() { var el = document.getElementById('addr-form-container'); var btn = document.getElementById('btn-toggle-addr'); if (el.style.display === 'block') { el.style.display = 'none'; btn.innerText = '＋ 添加新备忘'; } else { el.style.display = 'block'; btn.innerText = '－ 收起'; } }
        function copyContent(text, btnElement) { navigator.clipboard.writeText(text).then(function() { var originalText = btnElement.innerText; btnElement.innerText = "OK"; setTimeout(function() { btnElement.innerText = originalText; }, 1500); }, function(err) { alert('复制失败'); }); }
        // Modals
        function openEditAddrModal(btn) { document.getElementById('edit_index').value = btn.dataset.index; document.getElementById('edit_name').value = btn.dataset.name; document.getElementById('edit_addr_val').value = btn.dataset.addr; document.getElementById('edit_uid_val').value = btn.dataset.uid; document.getElementById('editAddrModal').style.display = 'flex'; }
        function openEditTaskModal(id, url, remark) { document.getElementById('edit_task_id').value = id; document.getElementById('edit_task_url').value = url; document.getElementById('edit_task_remark').value = remark; document.getElementById('editTaskModal').style.display = 'flex'; }
        function openEditProfileModal(btn) { document.getElementById('edit_profile_id').value = btn.dataset.id; document.getElementById('edit_profile_name').value = btn.dataset.name; document.getElementById('edit_profile_remark').value = btn.dataset.remark; document.getElementById('edit_profile_acc').value = btn.dataset.acc; document.getElementById('edit_profile_link').value = btn.dataset.link; document.getElementById('editProfileModal').style.display = 'flex'; }
        function openColorModal() { document.getElementById('colorModal').style.display = 'flex'; }
        // Auth
        let pendingAction = null; let pendingData = null;
        function triggerAuth(action, data) {
            const modal = document.getElementById('authModal'); const passInput = document.getElementById('authPassword');
            pendingAction = action; pendingData = data; passInput.value = ""; 
            ['editAddrModal', 'editTaskModal', 'editProfileModal', 'colorModal'].forEach(id => document.getElementById(id).style.display = 'none');
            modal.style.display = 'flex'; passInput.focus();
        }
        function closeModal(modalId) { document.getElementById(modalId).style.display = 'none'; pendingAction = null; pendingData = null; }
        function confirmAction() {
            const password = document.getElementById('authPassword').value;
            if (password === "110") {
                if (pendingAction === 'delete_addr') window.location.href = "/delete_addr/" + pendingData;
                else if (pendingAction === 'add_addr') document.getElementById('realAddForm').submit();
                else if (pendingAction === 'delete_task') window.location.href = "/delete/" + pendingData;
                else if (pendingAction === 'edit_addr') document.getElementById('editAddrForm').submit();
                else if (pendingAction === 'edit_task_info') document.getElementById('editTaskForm').submit();
                else if (pendingAction === 'add_profile') document.getElementById('realProfileForm').submit();
                else if (pendingAction === 'delete_profile') window.location.href = "/delete_profile/" + pendingData;
                else if (pendingAction === 'edit_profile') document.getElementById('editProfileForm').submit();
                else if (pendingAction === 'save_theme') document.getElementById('colorForm').submit();
                closeModal('authModal');
            } else { alert("密码错误！"); document.getElementById('authPassword').value = ""; }
        }
    </script>
</body>
</html>
'''

# --- 路由 ---
@app.route('/')
def index():
    init_db(); settings = get_settings_dict(); global_accounts_str = ",".join(json.loads(settings.get('global_accounts', '[]'))); address_book = json.loads(settings.get('address_book', '[]'))
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    try: c.execute('SELECT id, name, avatar, remark, account_number, link FROM profiles'); profiles = [{'id': r[0], 'name': r[1], 'avatar': r[2], 'remark': r[3], 'account_number': r[4], 'link': r[5]} for r in c.fetchall()]
    except: profiles = []
    c.execute('SELECT id, url, remark, target_accounts, done_accounts, enable_stats FROM bookmarks ORDER BY id DESC')
    items = []; 
    for row in c.fetchall():
        try: t = json.loads(row[3])
        except: t = []
        try: d = json.loads(row[4])
        except: d = []
        items.append({'id': row[0], 'url': row[1], 'remark': row[2], 'target_accounts': t, 'target_accounts_str': ",".join(t), 'done_accounts': d, 'done_count': len(d), 'total_count': len(t), 'enable_stats': row[5]==1, 'is_complete': len(d)>=len(t) and len(t)>0})
    conn.close(); return render_template_string(HTML_TEMPLATE, items=items, global_accounts_str=global_accounts_str, address_book=address_book, profiles=profiles, settings=settings)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/save_theme', methods=['POST'])
def save_theme():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    for k in ['left_bg', 'left_text', 'right_bg', 'right_text']: c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, request.form[k]))
    conn.commit(); conn.close(); return redirect(url_for('index'))

@app.route('/add_profile', methods=['POST'])
def add_profile():
    name = request.form['name']
    remark = request.form['remark']
    account_number = request.form['account_number']
    link = request.form['link']
    file = request.files['file']
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = str(int(time.time())) + "_" + filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO profiles (name, avatar, remark, account_number, link) VALUES (?, ?, ?, ?, ?)', 
                  (name, filename, remark, account_number, link))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    pid = request.form['id']
    name = request.form['name']
    remark = request.form['remark']
    account_number = request.form['account_number']
    link = request.form['link']
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE profiles SET name=?, remark=?, account_number=?, link=? WHERE id=?', 
              (name, remark, account_number, link, pid))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_profile/<int:id>')
def delete_profile(id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM profiles WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit_task_info', methods=['POST'])
def edit_task_info():
    task_id = request.form['id']
    url = request.form['url']
    remark = request.form['remark']
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE bookmarks SET url = ?, remark = ? WHERE id = ?', (url, remark, task_id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/update_global_settings', methods=['POST'])
def update_global_settings():
    raw_str = request.form['global_accounts_str']
    new_list = [x.strip() for x in raw_str.replace('，', ',').split(',') if x.strip()]
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('global_accounts', json.dumps(new_list)))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_addr', methods=['POST'])
def add_addr():
    name = request.form['name']
    addr = request.form['addr']
    uid = request.form['uid']
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', ('address_book',))
    row = c.fetchone()
    current_list = json.loads(row[0]) if row else []
    current_list.append({'name': name, 'addr': addr, 'uid': uid})
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('address_book', json.dumps(current_list)))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit_addr', methods=['POST'])
def edit_addr():
    index = int(request.form['index'])
    name = request.form['name']
    addr = request.form['addr']
    uid = request.form['uid']
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', ('address_book',))
    row = c.fetchone()
    if row:
        current_list = json.loads(row[0])
        if 0 <= index < len(current_list):
            current_list[index] = {'name': name, 'addr': addr, 'uid': uid}
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('address_book', json.dumps(current_list)))
            conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_addr/<int:index>')
def delete_addr(index):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', ('address_book',))
    row = c.fetchone()
    if row:
        current_list = json.loads(row[0])
        if 0 <= index < len(current_list):
            current_list.pop(index)
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('address_book', json.dumps(current_list)))
            conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add', methods=['POST'])
def add_entry():
    url = request.form['url']
    remark = request.form['remark']
    default_accs = get_settings_dict().get('global_accounts')
    default_accs = json.loads(default_accs) if default_accs else []
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO bookmarks (url, remark, target_accounts, done_accounts, enable_stats) VALUES (?, ?, ?, ?, 1)', 
              (url, remark, json.dumps(default_accs), '[]'))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/toggle_stats/<int:id>')
def toggle_stats(id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE bookmarks SET enable_stats = NOT enable_stats WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/update_item_accounts/<int:id>', methods=['POST'])
def update_item_accounts(id):
    raw_str = request.form['target_accounts_str']
    new_list = [x.strip() for x in raw_str.replace('，', ',').split(',') if x.strip()]
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE bookmarks SET target_accounts = ? WHERE id = ?', (json.dumps(new_list), id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/update_progress/<int:id>', methods=['POST'])
def update_progress(id):
    done_accounts = request.form.getlist('done_accounts')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE bookmarks SET done_accounts = ? WHERE id = ?', (json.dumps(done_accounts), id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_entry(id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM bookmarks WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
