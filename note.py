from flask import Flask, request, render_template_string, redirect, url_for
import sqlite3
import json
import os

app = Flask(__name__)
DB_FILE = 'bookmarks.db'

# --- 数据库初始化 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bookmarks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  url TEXT, 
                  remark TEXT,
                  target_accounts TEXT,
                  done_accounts TEXT,
                  enable_stats INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    c.execute('SELECT value FROM settings WHERE key = ?', ('global_accounts',))
    if c.fetchone() is None:
        default_accs = json.dumps(['账号1', '账号2', '账号3'])
        c.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('global_accounts', default_accs))
        
    c.execute('SELECT value FROM settings WHERE key = ?', ('address_book',))
    if c.fetchone() is None:
        c.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('address_book', '[]'))

    conn.commit()
    conn.close()

def get_global_accounts():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', ('global_accounts',))
    row = c.fetchone()
    conn.close()
    if row: return json.loads(row[0])
    return []

# --- HTML 模板 (修复按钮点击问题) ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>任务分发控制台</title>
    <style>
        /* --- 颜色变量 --- */
        :root {
            --bg-color: #f4f4f9;
            --text-color: #333;
            --sidebar-bg: #2c3e50;
            --sidebar-text: white;
            --card-bg: white;
            --input-bg: white;
            --border-color: #ddd;
            --shadow: rgba(0,0,0,0.05);
            --addr-card-bg: #263544;
            --addr-text: #bdc3c7;
            --btn-bg: #e0e0e0;
        }

        [data-theme="dark"] {
            --bg-color: #121212;
            --text-color: #e0e0e0;
            --sidebar-bg: #0f1519;
            --sidebar-text: #ccc;
            --card-bg: #1e1e1e;
            --input-bg: #2d2d2d;
            --border-color: #444;
            --shadow: rgba(0,0,0,0.5);
            --addr-card-bg: #1c2329;
            --addr-text: #888;
            --btn-bg: #333;
        }

        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; 
            margin: 0; 
            background: var(--bg-color); 
            color: var(--text-color); 
            display: flex; 
            min-height: 100vh; 
            transition: background 0.3s, color 0.3s;
            position: relative;
        }
        
        /* 右上角开关 (修复版：加了 z-index) */
        .theme-switch-wrapper { 
            position: absolute; 
            top: 15px; 
            right: 20px; 
            z-index: 9999; /* 关键：确保浮在最上面 */
        }
        .theme-btn { 
            background: var(--btn-bg); 
            border: 1px solid var(--border-color); 
            color: var(--text-color); 
            padding: 8px 15px; 
            cursor: pointer; 
            border-radius: 20px; 
            font-size: 14px;
            font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            transition: all 0.2s;
        }
        .theme-btn:hover { transform: scale(1.05); }
        .theme-btn:active { transform: scale(0.95); }
        
        /* --- 👈 左侧边栏 --- */
        .sidebar { 
            width: 380px; 
            background: var(--sidebar-bg); 
            color: var(--sidebar-text); 
            padding: 20px; 
            display: flex; 
            flex-direction: column; 
            position: fixed; 
            height: 100%; 
            overflow-y: auto; 
            box-shadow: 2px 0 10px rgba(0,0,0,0.2); 
            z-index: 100;
        }
        .sidebar h3 { margin-top: 0; border-bottom: 1px solid #34495e; padding-bottom: 10px; margin-bottom: 15px; font-size: 1.1em; }
        .sidebar-desc { font-size: 0.8em; color: #bdc3c7; margin-bottom: 10px; }
        
        .setting-box { background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.1); }
        .setting-label { font-size: 0.9em; font-weight: bold; margin-bottom: 8px; display: block; color: #ecf0f1; }
        
        .account-editor { width: 100%; height: 80px; background: #ecf0f1; border: none; border-radius: 4px; padding: 8px; margin-bottom: 8px; font-family: monospace; resize: vertical; font-size: 0.9em; }
        .btn-save-settings { width: 100%; padding: 8px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.9em; }
        
        .addr-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 10px; }
        .addr-card { background: var(--addr-card-bg); padding: 12px; border-radius: 6px; font-size: 0.85em; border: 1px solid rgba(255,255,255,0.1); }
        .addr-header { display: flex; justify-content: space-between; margin-bottom: 8px; font-weight: bold; color: #3498db; border-bottom: 1px dashed #3e5366; padding-bottom: 5px; font-size: 1.05em; }
        .addr-row { display: flex; align-items: center; justify-content: space-between; margin-top: 6px; color: var(--addr-text); }
        .addr-val { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 240px; font-family: monospace; background: rgba(0,0,0,0.3); padding: 2px 5px; border-radius: 3px; }
        
        .btn-copy-icon { background: none; border: 1px solid #576d80; color: #bdc3c7; cursor: pointer; border-radius: 3px; font-size: 0.8em; padding: 1px 6px; transition: 0.2s; white-space: nowrap; }
        .btn-copy-icon:hover { background: #3498db; color: white; border-color: #3498db; }
        .btn-copy-icon.copied { background: #2ecc71; border-color: #2ecc71; color: white; }
        .btn-del-addr { color: #e74c3c; text-decoration: none; font-weight: bold; cursor: pointer; font-size: 1.2em; line-height: 1; }

        .btn-show-form { width: 100%; background: #27ae60; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 5px; transition: 0.2s; }
        .add-addr-container { display: none; margin-top: 10px; background: var(--addr-card-bg); padding: 10px; border-radius: 6px; border: 1px solid #3e5366; }
        .add-addr-form { display: flex; flex-direction: column; gap: 8px; }
        .add-addr-form input { padding: 8px; border-radius: 4px; border: none; font-size: 0.9em; background: #ecf0f1; }
        .btn-submit-addr { background: #3498db; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; font-weight: bold; }

        /* --- 👉 右侧主内容 --- */
        .main-content { flex: 1; margin-left: 380px; padding: 40px; max-width: 1000px; position: relative; z-index: 1; }

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
        .link-row { display: flex; align-items: center; gap: 10px; margin-bottom: 5px; }
        .url-link { color: #2980b9; text-decoration: none; font-weight: 600; font-size: 1.1em; word-break: break-all; }
        .btn-copy { background: #ecf0f1; border: 1px solid #bdc3c7; color: #555; border-radius: 4px; padding: 2px 8px; font-size: 0.8em; cursor: pointer; transition: 0.2s; display: inline-flex; align-items: center; }
        .btn-copy:hover { background: #dfe6e9; color: #2c3e50; }
        .btn-copy.copied { background: #2ecc71; color: white; border-color: #2ecc71; }
        .remark { font-size: 0.9em; background: rgba(0,0,0,0.05); padding: 3px 8px; border-radius: 4px; color: var(--text-color); opacity: 0.8; }
        
        .badge { font-size: 0.8em; padding: 4px 8px; border-radius: 4px; font-weight: bold; white-space: nowrap; }
        .badge-success { background: #d5f5e3; color: #196f3d; }
        .badge-warning { background: #fcf3cf; color: #7d6608; }
        .badge-gray { background: #ecf0f1; color: #7f8c8d; }

        .toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
        .btn-sm { padding: 5px 10px; font-size: 0.85em; background: #95a5a6; color: white; text-decoration: none; border-radius: 4px; border:none; cursor: pointer;}
        .btn-toggle { background: #1abc9c; }
        .btn-del { background: #e74c3c; margin-left: auto; }
        
        .edit-area { margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.02); display: none; }
        .edit-area textarea { width: 100%; padding: 5px; margin-bottom: 5px; border: 1px solid #ccc; font-family: monospace; }
        
        .stats-area { margin-top: 15px; padding-top: 15px; border-top: 1px dashed var(--border-color); }
        .checkbox-group { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px; }
        .cb-label { display: flex; align-items: center; gap: 5px; font-size: 0.9em; background: var(--input-bg); padding: 5px 10px; border-radius: 4px; cursor: pointer; border: 1px solid var(--border-color); }
        .cb-label:hover { border-color: #3498db; }
        .btn-update { background: #3498db; color: white; padding: 6px 15px; border: none; border-radius: 4px; cursor: pointer; }

        /* 弹窗样式 */
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 10000; }
        .modal-box { background: var(--card-bg); padding: 20px; border-radius: 8px; text-align: center; width: 300px; box-shadow: 0 5px 15px rgba(0,0,0,0.3); border: 1px solid var(--border-color); }
        .modal-box input { width: 80%; margin: 15px 0; text-align: center; }
        .modal-buttons { display: flex; justify-content: space-around; }
        .btn-confirm { background-color: #007bff; color: white; padding: 5px 15px; border: none; border-radius: 4px; cursor: pointer; }
        .btn-cancel { background-color: #6c757d; color: white; padding: 5px 15px; border: none; border-radius: 4px; cursor: pointer; }

        @media (max-width: 768px) {
            body { flex-direction: column; }
            .sidebar { width: 100%; position: relative; height: auto; }
            .main-content { margin-left: 0; padding: 20px; margin-top: 40px; }
            .theme-switch-wrapper { top: 10px; right: 10px; }
        }
    </style>
</head>
<body>
    <div class="theme-switch-wrapper">
        <button class="theme-btn" onclick="toggleTheme()" id="themeBtn">☀️/🌙 切换</button>
    </div>

    <aside class="sidebar">
        <h3>⚙️ 控制台</h3>
        
        <div class="setting-box">
            <span class="setting-label">📥 默认账户模板</span>
            <div class="sidebar-desc">新任务默认使用 (逗号分隔):</div>
            <form action="/update_global_settings" method="post">
                <textarea name="global_accounts_str" class="account-editor">{{ global_accounts_str }}</textarea>
                <button type="submit" class="btn-save-settings">💾 保存模板</button>
            </form>
        </div>

        <div class="setting-box">
            <span class="setting-label">🏦 地址/UID 备忘录</span>
            <div class="addr-list">
                {% for item in address_book %}
                <div class="addr-card">
                    <div class="addr-header">
                        <span>{{ item.name }}</span>
                        <span class="btn-del-addr" onclick="triggerAuth('delete_addr', {{ loop.index0 }})">×</span>
                    </div>
                    {% if item.addr %}
                    <div class="addr-row">
                        <span style="font-size:0.8em; opacity:0.7;">Add:</span>
                        <span class="addr-val" title="{{ item.addr }}">{{ item.addr }}</span>
                        <button class="btn-copy-icon" data-val="{{ item.addr }}" onclick="copyContent(this.dataset.val, this)">复制</button>
                    </div>
                    {% endif %}
                    {% if item.uid %}
                    <div class="addr-row">
                        <span style="font-size:0.8em; opacity:0.7;">UID:</span>
                        <span class="addr-val" title="{{ item.uid }}">{{ item.uid }}</span>
                        <button class="btn-copy-icon" data-val="{{ item.uid }}" onclick="copyContent(this.dataset.val, this)">复制</button>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>

            <button id="btn-toggle-addr" class="btn-show-form" onclick="toggleAddrForm()">＋ 添加新备忘</button>
            
            <div id="addr-form-container" class="add-addr-container">
                <form id="realAddForm" action="/add_addr" method="post" class="add-addr-form" onsubmit="event.preventDefault(); triggerAuth('add_addr', this);">
                    <input type="text" name="name" placeholder="账户备注 (如: 大号)" required>
                    <input type="text" name="addr" placeholder="Add (地址)">
                    <input type="text" name="uid" placeholder="UID">
                    <button type="submit" class="btn-submit-addr">确认添加 (需密码)</button>
                </form>
            </div>
        </div>
        <div class="sidebar-desc" style="margin-top: auto; opacity: 0.5; text-align: center;">LegendVPS Tool v3.6 (Fixed)</div>
    </aside>

    <main class="main-content">
        <h2>📋 任务分发管理</h2>
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
                            <button class="btn-copy" data-url="{{ item.url }}" onclick="copyContent(this.dataset.url, this)" title="复制内容">
                                📋 复制
                            </button>
                        </div>
                        {% if item.remark %}<span class="remark">{{ item.remark }}</span>{% endif %}
                    </div>
                    {% if item.enable_stats %}
                        {% if item.is_complete %}
                            <span class="badge badge-success">✅ 已完成</span>
                        {% else %}
                            <span class="badge badge-warning">⏳ {{ item.done_count }} / {{ item.total_count }}</span>
                        {% endif %}
                    {% else %}
                        <span class="badge badge-gray">⚪ 统计关闭</span>
                    {% endif %}
                </div>

                <div class="toolbar">
                    <a href="/toggle_stats/{{ item.id }}" class="btn-sm btn-toggle">
                        {% if item.enable_stats %}👁️ 隐藏{% else %}📊 开启统计{% endif %}
                    </a>
                    {% if item.enable_stats %}
                    <button type="button" class="btn-sm" onclick="toggleEdit({{ item.id }})">⚙️ 修改此任务账号</button>
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
                            <label class="cb-label">
                                <input type="checkbox" name="done_accounts" value="{{ acc }}" 
                                       {% if acc in item.done_accounts %}checked{% endif %}>
                                {{ acc }}
                            </label>
                            {% endfor %}
                        </div>
                        <button type="submit" class="btn-update">更新进度</button>
                    </form>
                {% endif %}
            </li>
            {% endfor %}
        </ul>
    </main>

    <div class="modal-overlay" id="authModal">
        <div class="modal-box">
            <h3>安全验证</h3>
            <p>请输入操作密码：</p>
            <input type="password" id="authPassword" placeholder="***" maxlength="10">
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeModal()">取消</button>
                <button class="btn-confirm" onclick="confirmAction()">确认</button>
            </div>
        </div>
    </div>
    
    <script>
        // --- 模式切换逻辑 ---
        function toggleTheme() {
            try {
                const currentTheme = document.documentElement.getAttribute("data-theme");
                const newTheme = currentTheme === "dark" ? "light" : "dark";
                document.documentElement.setAttribute("data-theme", newTheme);
                localStorage.setItem("theme", newTheme);
                console.log("Switched to " + newTheme);
            } catch(e) {
                console.error(e);
            }
        }
        
        // 页面加载时恢复主题
        document.addEventListener("DOMContentLoaded", function() {
            const savedTheme = localStorage.getItem("theme") || "light";
            document.documentElement.setAttribute("data-theme", savedTheme);
        });

        // --- 其他逻辑 ---
        function toggleEdit(id) {
            var el = document.getElementById('edit-' + id);
            el.style.display = el.style.display === 'block' ? 'none' : 'block';
        }
        function toggleAddrForm() {
            var el = document.getElementById('addr-form-container');
            var btn = document.getElementById('btn-toggle-addr');
            if (el.style.display === 'block') {
                el.style.display = 'none';
                btn.innerText = '＋ 添加新备忘';
            } else {
                el.style.display = 'block';
                btn.innerText = '－ 收起';
            }
        }
        function copyContent(text, btnElement) {
            navigator.clipboard.writeText(text).then(function() {
                var originalText = btnElement.innerText;
                var isIcon = btnElement.classList.contains('btn-copy-icon');
                btnElement.innerText = isIcon ? "OK" : "✅ 已复制";
                btnElement.classList.add('copied');
                setTimeout(function() {
                    btnElement.innerText = originalText;
                    btnElement.classList.remove('copied');
                }, 2000);
            }, function(err) {
                alert('复制失败，请手动复制');
            });
        }

        // --- 安全验证 JS ---
        let pendingAction = null; 
        let pendingData = null;

        function triggerAuth(action, data) {
            const modal = document.getElementById('authModal');
            const passInput = document.getElementById('authPassword');
            pendingAction = action;
            pendingData = data; 
            passInput.value = ""; 
            modal.style.display = 'flex';
            passInput.focus();
        }

        function closeModal() {
            document.getElementById('authModal').style.display = 'none';
            pendingAction = null;
            pendingData = null;
        }

        function confirmAction() {
            const password = document.getElementById('authPassword').value;
            if (password === "110") {
                if (pendingAction === 'delete_addr') {
                    window.location.href = "/delete_addr/" + pendingData;
                } else if (pendingAction === 'add_addr') {
                    document.getElementById('realAddForm').submit();
                } else if (pendingAction === 'delete_task') {
                    window.location.href = "/delete/" + pendingData;
                }
                closeModal();
            } else {
                alert("密码错误！");
                document.getElementById('authPassword').value = "";
            }
        }
        
        document.addEventListener("DOMContentLoaded", function() {
            const passInput = document.getElementById('authPassword');
            if(passInput){
                passInput.addEventListener("keypress", function(event) {
                    if (event.key === "Enter") confirmAction();
                });
            }
        });
    </script>
</body>
</html>
'''

# --- 路由 ---
@app.route('/')
def index():
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', ('global_accounts',))
    row_setting = c.fetchone()
    global_accounts = json.loads(row_setting[0]) if row_setting else []
    global_accounts_str = ",".join(global_accounts)
    
    c.execute('SELECT value FROM settings WHERE key = ?', ('address_book',))
    row_addr = c.fetchone()
    address_book = json.loads(row_addr[0]) if row_addr else []

    c.execute('SELECT id, url, remark, target_accounts, done_accounts, enable_stats FROM bookmarks ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    
    items = []
    for row in rows:
        try: target_accs = json.loads(row[3])
        except: target_accs = []
        try: done_accs = json.loads(row[4])
        except: done_accs = []
        enable_stats = (row[5] == 1)
        total_count = len(target_accs)
        is_complete = (len(done_accs) >= total_count) and (total_count > 0)
        
        items.append({
            'id': row[0],
            'url': row[1],
            'remark': row[2],
            'target_accounts': target_accs,
            'target_accounts_str': ",".join(target_accs),
            'done_accounts': done_accs,
            'done_count': len(done_accs),
            'total_count': total_count,
            'enable_stats': enable_stats,
            'is_complete': is_complete
        })
    return render_template_string(HTML_TEMPLATE, items=items, global_accounts_str=global_accounts_str, address_book=address_book)

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
    default_accs = get_global_accounts()
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
