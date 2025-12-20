from flask import Flask, render_template, request, redirect
import sqlite3
import os

app = Flask(__name__)
DB_FILE = 'database.db'

# 初始化数据库函数
def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE accounts 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      address TEXT, 
                      uid TEXT)''')
        conn.commit()
        conn.close()

# 每次启动应用前检查数据库
init_db()

@app.route('/')
def index():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT * FROM accounts')
    accounts = c.fetchall()
    conn.close()
    return render_template('index.html', accounts=accounts)

@app.route('/add', methods=['POST'])
def add_account():
    wallet_address = request.form.get('wallet_address')
    uid = request.form.get('uid')
    
    if wallet_address and uid:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO accounts (address, uid) VALUES (?, ?)', (wallet_address, uid))
        conn.commit()
        conn.close()
    
    return redirect('/')

@app.route('/delete/<int:id>')
def delete_account(id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM accounts WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
