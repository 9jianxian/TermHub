from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from functools import wraps
import sqlite3
import json
import requests
import hashlib
import os
import asyncio
import edge_tts
import tempfile

app = Flask(__name__, static_folder='static')
app.secret_key = 'vocabulary_admin_secret_key_2024'

# 数据库路径
DB_PATH = 'vocabulary_user.db'

# 语音配置
BRITISH_VOICE = 'en-GB-SoniaNeural'
AMERICAN_VOICE = 'en-US-JennyNeural'

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def add_log(action, description=''):
    """记录操作日志"""
    try:
        conn = get_db()
        ip = request.remote_addr if request else ''
        conn.execute(
            'INSERT INTO logs (action, description, ip_address) VALUES (?, ?, ?)',
            (action, description, ip)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'记录日志失败: {e}')

def is_logged_in():
    """检查是否已登录"""
    return 'username' in session

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            if request.path.startswith('/api/'):
                return jsonify({'error': '未登录'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== 前台页面 ====================

@app.route('/')
def index():
    """首页"""
    conn = get_db()
    
    # 获取所有分类（从分类表）
    cursor = conn.execute("SELECT id, name FROM categories ORDER BY name")
    categories = [dict(row) for row in cursor.fetchall()]
    
    # 获取分类对应的词汇数量
    category_counts = {}
    for cat in categories:
        cursor = conn.execute("SELECT COUNT(*) as count FROM vocabulary WHERE category_id = ?", (cat['id'],))
        category_counts[cat['name']] = cursor.fetchone()['count']
    
    # 总词汇数
    cursor = conn.execute("SELECT COUNT(*) as count FROM vocabulary")
    total_count = cursor.fetchone()['count']
    
    # 默认分类（第一个）
    default_category = categories[0]['name'] if categories else ''
    
    # 默认分类的词汇
    if categories:
        cursor = conn.execute("""
            SELECT v.*, c.name as Category 
            FROM vocabulary v 
            JOIN categories c ON v.category_id = c.id 
            WHERE c.name = ? 
            ORDER BY v.id
        """, (default_category,))
        words = [dict(row) for row in cursor.fetchall()]
    else:
        words = []
    
    # 获取站点设置
    site_settings = conn.execute('SELECT * FROM site_settings WHERE id = 1').fetchone()
    
    conn.close()
    
    return render_template('index.html', 
                          categories=[cat['name'] for cat in categories],
                          category_counts=category_counts,
                          default_category=default_category,
                          words=words,
                          total_count=total_count,
                          is_logged_in=is_logged_in(),
                          site_settings=site_settings)

@app.route('/api/categories')
def get_categories():
    """获取所有分类及数量"""
    conn = get_db()
    cursor = conn.execute("SELECT id, name FROM categories ORDER BY name")
    categories = [dict(row) for row in cursor.fetchall()]
    
    # 获取每个分类的单词数量
    result = []
    for cat in categories:
        cursor = conn.execute("SELECT COUNT(*) as count FROM vocabulary WHERE category_id = ?", (cat['id'],))
        count = cursor.fetchone()['count']
        result.append({
            'name': cat['name'],
            'count': count
        })
    
    conn.close()
    return jsonify(result)

@app.route('/api/category')
def get_words_by_category():
    """按分类获取词汇"""
    category_name = request.args.get('name', '')
    
    conn = get_db()
    cursor = conn.execute("""
        SELECT v.*, c.name as Category 
        FROM vocabulary v 
        JOIN categories c ON v.category_id = c.id 
        WHERE c.name = ? 
        ORDER BY v.id
    """, (category_name,))
    words = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(words)

@app.route('/api/search')
def search_words():
    """搜索词汇"""
    keyword = request.args.get('q', '')
    
    conn = get_db()
    cursor = conn.execute("""
        SELECT v.*, c.name as Category 
        FROM vocabulary v 
        JOIN categories c ON v.category_id = c.id 
        WHERE v.english_word LIKE ? OR v.chinese_definition LIKE ? 
        ORDER BY v.id 
        LIMIT 500
    """, (f'%{keyword}%', f'%{keyword}%'))
    words = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(words)

@app.route('/api/all')
def get_all_words():
    """获取所有词汇"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT v.*, c.name as Category 
        FROM vocabulary v 
        JOIN categories c ON v.category_id = c.id 
        ORDER BY v.id
    """)
    words = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(words)

@app.route('/api/speak')
def speak_word():
    """实时生成单词发音"""
    word = request.args.get('word', '')
    accent = request.args.get('accent', 'british')
    
    if not word:
        return jsonify({'error': '单词不能为空'}), 400
    
    voice = BRITISH_VOICE if accent == 'british' else AMERICAN_VOICE
    tmp_path = None
    
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        
        # 生成音频
        async def generate():
            communicate = edge_tts.Communicate(word, voice)
            await communicate.save(tmp_path)
        
        asyncio.run(generate())
        
        # 读取到内存
        with open(tmp_path, 'rb') as f:
            audio_data = f.read()
        
        # 返回音频，设置浏览器缓存（缓存30天）
        response = Response(audio_data, mimetype='audio/mpeg')
        response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30天
        response.headers['Accept-Ranges'] = 'bytes'
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # 清理临时文件
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except:
            pass

# ==================== 登录相关 ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        # MD5加密密码
        password_md5 = hashlib.md5(password.encode()).hexdigest()
        
        conn = get_db()
        cursor = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password_md5))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['username'] = username
            add_log('用户登录', f'用户 {username} 登录成功')
            return redirect(url_for('admin'))
        else:
            error = '用户名或密码错误'
            return render_template('login.html', error=error)
    
    if is_logged_in():
        return redirect(url_for('admin'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """退出登录"""
    username = session.get('username', '')
    session.clear()
    if username:
        add_log('用户退出', f'用户 {username} 退出登录')
    return redirect(url_for('index'))

# ==================== 管理后台页面 ====================

@app.route('/admin')
@login_required
def admin():
    """管理后台页面"""
    conn = get_db()
    cursor = conn.execute("SELECT COUNT(*) as count FROM vocabulary")
    total_count = cursor.fetchone()['count']
    cursor = conn.execute("SELECT COUNT(*) as count FROM categories")
    category_count = cursor.fetchone()['count']
    conn.close()
    return render_template('admin.html', total_count=total_count, category_count=category_count)

# ---------- 分类管理 ----------

@app.route('/api/admin/categories')
@login_required
def admin_get_categories():
    """获取所有分类"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT c.id, c.name, COUNT(v.id) as count 
        FROM categories c 
        LEFT JOIN vocabulary v ON c.id = v.category_id 
        GROUP BY c.id 
        ORDER BY c.name
    """)
    categories = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(categories)

@app.route('/api/admin/category', methods=['POST'])
@login_required
def admin_add_category():
    """添加分类"""
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': '分类名称不能为空'})
    
    conn = get_db()
    try:
        cursor = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        add_log('添加分类', f'添加分类：{name}')
        return jsonify({'success': True, 'id': new_id, 'name': name})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': '该分类已存在'})

@app.route('/api/admin/category', methods=['PUT'])
@login_required
def admin_update_category():
    """修改分类名称"""
    data = request.get_json()
    category_id = data.get('id')
    new_name = data.get('name', '').strip()
    
    if not category_id or not new_name:
        return jsonify({'success': False, 'message': '参数错误'})
    
    conn = get_db()
    try:
        cursor = conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, category_id))
        conn.commit()
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'message': '分类不存在'})
        conn.close()
        add_log('修改分类', f'修改分类ID {category_id} 为：{new_name}')
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': '该分类名称已存在'})

@app.route('/api/admin/category', methods=['DELETE'])
@login_required
def admin_delete_category():
    """删除分类（同时删除该分类下所有单词）"""
    data = request.get_json()
    category_id = data.get('id')
    
    if not category_id:
        return jsonify({'success': False, 'message': '参数错误'})
    
    conn = get_db()
    
    # 获取分类名称用于日志
    cursor = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
    cat = cursor.fetchone()
    cat_name = cat['name'] if cat else ''
    
    conn.execute("DELETE FROM vocabulary WHERE category_id = ?", (category_id,))
    cursor = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'success': False, 'message': '分类不存在'})
    
    conn.close()
    add_log('删除分类', f'删除分类：{cat_name}（ID: {category_id}），同时删除该分类下所有单词')
    return jsonify({'success': True})


@app.route('/api/admin/categories/merge', methods=['POST'])
@login_required
def admin_merge_categories():
    """合并多个分类"""
    data = request.get_json()
    from_ids = data.get('from_ids', [])
    to_id = data.get('to_id')
    to_name = data.get('to_name')
    
    if not from_ids:
        return jsonify({'success': False, 'message': '请选择要合并的分类'})
    
    if not to_id and not to_name:
        return jsonify({'success': False, 'message': '请选择或输入目标分类'})
    
    if isinstance(from_ids, str):
        from_ids = [from_ids]
    
    conn = get_db()
    
    # 获取或创建目标分类
    if to_id:
        # 使用已有分类
        target = conn.execute('SELECT id, name FROM categories WHERE id = ?', (to_id,)).fetchone()
        if not target:
            conn.close()
            return jsonify({'success': False, 'message': '目标分类不存在'})
    else:
        # 使用新分类名
        to_name = to_name.strip()
        if not to_name:
            conn.close()
            return jsonify({'success': False, 'message': '请输入新分类名称'})
        
        # 检查分类是否已存在
        existing = conn.execute('SELECT id, name FROM categories WHERE name = ?', (to_name,)).fetchone()
        if existing:
            target = existing
        else:
            # 创建新分类
            conn.execute('INSERT INTO categories (name) VALUES (?)', (to_name,))
            conn.commit()
            target = conn.execute('SELECT id, name FROM categories WHERE name = ?', (to_name,)).fetchone()
    
    # 检查目标分类是否在源分类中
    if str(target['id']) in [str(x) for x in from_ids]:
        conn.close()
        return jsonify({'success': False, 'message': '目标分类不能在源分类中'})
    
    moved_count = 0
    deleted_count = 0
    deleted_names = []
    
    for from_id in from_ids:
        cat = conn.execute('SELECT id, name FROM categories WHERE id = ?', (from_id,)).fetchone()
        if cat and cat['id'] != target['id']:
            # 移动单词
            cursor = conn.execute('UPDATE vocabulary SET category_id = ? WHERE category_id = ?', (target['id'], cat['id']))
            moved_count += cursor.rowcount
            # 删除源分类
            conn.execute('DELETE FROM categories WHERE id = ?', (cat['id'],))
            deleted_count += 1
            deleted_names.append(cat['name'])
    
    conn.commit()
    conn.close()
    
    add_log('合并分类', f'合并分类：{", ".join(deleted_names)} -> {target["name"]}，移动了{moved_count}个单词')
    
    return jsonify({
        'success': True,
        'message': f'合并成功：移动了{moved_count}个单词，删除了{deleted_count}个分类',
        'moved_count': moved_count,
        'deleted_count': deleted_count,
        'target_name': target['name']
    })

# ---------- 单词管理 ----------

@app.route('/api/admin/words')
@login_required
def admin_get_words():
    """获取单词列表（支持搜索、分类筛选、分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', 0, type=int)
    category_name = request.args.get('category', '')
    
    offset = (page - 1) * per_page
    
    conn = get_db()
    
    # 如果传了分类名称，先找到分类ID
    if category_name and not category_id:
        cursor = conn.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
        cat = cursor.fetchone()
        if cat:
            category_id = cat['id']
    
    # 构建查询
    query = """
        SELECT v.*, c.name as category_name 
        FROM vocabulary v 
        JOIN categories c ON v.category_id = c.id 
        WHERE 1=1
    """
    params = []
    
    if keyword:
        query += " AND (v.english_word LIKE ? OR v.chinese_definition LIKE ?)"
        params.extend([f'%{keyword}%', f'%{keyword}%'])
    
    if category_id:
        query += " AND v.category_id = ?"
        params.append(category_id)
    
    # 总数
    count_query = query.replace('SELECT v.*, c.name as category_name', 'SELECT COUNT(*) as count')
    cursor = conn.execute(count_query, params)
    total = cursor.fetchone()['count']
    
    # 分页数据
    query += " ORDER BY v.id LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    cursor = conn.execute(query, params)
    words = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'words': words,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })

@app.route('/api/admin/word/<int:word_id>')
@login_required
def admin_get_word(word_id):
    """获取单个单词详情"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT v.*, c.name as category_name 
        FROM vocabulary v 
        JOIN categories c ON v.category_id = c.id 
        WHERE v.id = ?
    """, (word_id,))
    word = cursor.fetchone()
    conn.close()
    
    if not word:
        return jsonify({'error': '单词不存在'}), 404
    
    return jsonify(dict(word))

@app.route('/api/admin/word', methods=['POST'])
@login_required
def admin_add_word():
    """添加单词"""
    data = request.get_json()
    
    category_name = data.get('category_name', '')
    category_id = data.get('category_id')
    english_word = data.get('english_word', '').strip()
    british_phonetic = data.get('british_phonetic', '')
    american_phonetic = data.get('american_phonetic', '')
    chinese_definition = data.get('chinese_definition', '')
    
    if not english_word:
        return jsonify({'success': False, 'message': '英文单词不能为空'})
    
    conn = get_db()
    
    # 处理分类
    if not category_id and category_name:
        cursor = conn.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
        cat = cursor.fetchone()
        if cat:
            category_id = cat['id']
        else:
            cursor = conn.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
            category_id = cursor.lastrowid
    
    if not category_id:
        conn.close()
        return jsonify({'success': False, 'message': '请选择分类'})
    
    try:
        cursor = conn.execute("""
            INSERT INTO vocabulary (category_id, english_word, british_phonetic, american_phonetic, chinese_definition)
            VALUES (?, ?, ?, ?, ?)
        """, (category_id, english_word, british_phonetic, american_phonetic, chinese_definition))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        add_log('添加单词', f'添加单词：{english_word}')
        return jsonify({'success': True, 'id': new_id})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/word', methods=['PUT'])
@login_required
def admin_update_word():
    """修改单词"""
    data = request.get_json()
    
    word_id = data.get('id')
    category_name = data.get('category_name', '')
    category_id = data.get('category_id')
    english_word = data.get('english_word', '').strip()
    british_phonetic = data.get('british_phonetic', '')
    american_phonetic = data.get('american_phonetic', '')
    chinese_definition = data.get('chinese_definition', '')
    
    if not word_id or not english_word:
        return jsonify({'success': False, 'message': '参数错误'})
    
    conn = get_db()
    
    # 处理分类
    if category_name:
        cursor = conn.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
        cat = cursor.fetchone()
        if cat:
            category_id = cat['id']
        else:
            cursor = conn.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
            category_id = cursor.lastrowid
    
    if not category_id:
        conn.close()
        return jsonify({'success': False, 'message': '请选择分类'})
    
    cursor = conn.execute("""
        UPDATE vocabulary 
        SET category_id = ?, english_word = ?, british_phonetic = ?, american_phonetic = ?, chinese_definition = ?
        WHERE id = ?
    """, (category_id, english_word, british_phonetic, american_phonetic, chinese_definition, word_id))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'success': False, 'message': '单词不存在'})
    
    conn.close()
    add_log('修改单词', f'修改单词：{english_word}（ID: {word_id}）')
    return jsonify({'success': True})

@app.route('/api/admin/word', methods=['DELETE'])
@login_required
def admin_delete_word():
    """删除单词"""
    data = request.get_json()
    word_id = data.get('id')
    
    if not word_id:
        return jsonify({'success': False, 'message': '参数错误'})
    
    conn = get_db()
    
    # 获取单词用于日志
    cursor = conn.execute("SELECT english_word FROM vocabulary WHERE id = ?", (word_id,))
    word = cursor.fetchone()
    word_name = word['english_word'] if word else ''
    
    cursor = conn.execute("DELETE FROM vocabulary WHERE id = ?", (word_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'success': False, 'message': '单词不存在'})
    
    conn.close()
    add_log('删除单词', f'删除单词：{word_name}（ID: {word_id}）')
    return jsonify({'success': True})




@app.route('/api/admin/words/batch', methods=['PUT'])
@login_required
def admin_batch_update_words():
    """批量修改单词"""
    data = request.get_json()
    word_ids = data.get('ids', [])
    update_data = data.get('data', {})
    
    if not word_ids:
        return jsonify({'success': False, 'message': '请选择要修改的单词'})
    
    if not update_data:
        return jsonify({'success': False, 'message': '请填写要修改的内容'})
    
    conn = get_db()
    
    # 构建更新字段
    update_fields = []
    params = []
    
    if 'category_id' in update_data and update_data['category_id']:
        update_fields.append('category_id = ?')
        params.append(update_data['category_id'])
    
    if 'british_phonetic' in update_data and update_data['british_phonetic']:
        update_fields.append('british_phonetic = ?')
        params.append(update_data['british_phonetic'])
    
    if 'american_phonetic' in update_data and update_data['american_phonetic']:
        update_fields.append('american_phonetic = ?')
        params.append(update_data['american_phonetic'])
    
    if 'chinese_definition' in update_data and update_data['chinese_definition']:
        update_fields.append('chinese_definition = ?')
        params.append(update_data['chinese_definition'])
    
    if not update_fields:
        conn.close()
        return jsonify({'success': False, 'message': '没有要修改的字段'})
    
    # 构建IN条件
    placeholders = ','.join(['?' for _ in word_ids])
    params.extend(word_ids)
    
    # 执行更新
    sql = f"UPDATE vocabulary SET {', '.join(update_fields)} WHERE id IN ({placeholders})"
    cursor = conn.execute(sql, params)
    updated_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    add_log('批量修改单词', f'批量修改了{updated_count}个单词')
    
    return jsonify({
        'success': True,
        'message': f'成功修改了{updated_count}个单词',
        'updated_count': updated_count
    })


@app.route('/api/admin/words/batch', methods=['DELETE'])
@login_required
def admin_batch_delete_words():
    """批量删除单词"""
    data = request.get_json()
    word_ids = data.get('ids', [])
    
    if not word_ids:
        return jsonify({'success': False, 'message': '请选择要删除的单词'})
    
    conn = get_db()
    
    # 构建IN条件
    placeholders = ','.join(['?' for _ in word_ids])
    
    # 先获取要删除的单词数量用于日志
    cursor = conn.execute(f"SELECT COUNT(*) as count FROM vocabulary WHERE id IN ({placeholders})", word_ids)
    count = cursor.fetchone()['count']
    
    # 执行删除
    conn.execute(f"DELETE FROM vocabulary WHERE id IN ({placeholders})", word_ids)
    conn.commit()
    conn.close()
    
    add_log('批量删除单词', f'批量删除了{count}个单词')
    
    return jsonify({
        'success': True,
        'message': f'成功删除了{count}个单词',
        'deleted_count': count
    })

@app.route('/api/admin/template')
@login_required
def admin_download_template():
    """下载CSV导入模板"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(['category_name', 'english_word', 'british_phonetic', 'american_phonetic', 'chinese_definition'])
    
    # 写入示例数据
    writer.writerow(['网络安全基础', 'firewall', '/ˈfaɪəwɔːl/', '/ˈfaɪərwɔːl/', '防火墙：一种网络安全系统，用于监控和控制进出网络流量'])
    writer.writerow(['Web安全与渗透', 'sql injection', '/ˌes kjuː ˈel ɪnˈdʒekʃn/', '/ˌes kjuː ˈel ɪnˈdʒekʃn/', 'SQL注入：一种代码注入技术，攻击者将恶意SQL代码插入到应用程序的查询中'])
    
    output.seek(0)
    
    # 添加UTF-8 BOM，解决Excel打开乱码问题
    csv_content = '\ufeff' + output.getvalue()
    
    return Response(
        csv_content,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=vocabulary_template.csv'}
    )

@app.route('/api/admin/import', methods=['POST'])
@login_required
def admin_import_words():
    """批量导入单词"""
    import csv
    import io
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '请选择文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '请选择文件'})
    
    if not file.filename.endswith('.csv'):
        return jsonify({'success': False, 'message': '只支持CSV文件'})
    
    # 读取CSV内容（使用utf-8-sig自动处理BOM）
    stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
    reader = csv.DictReader(stream)
    
    conn = get_db()
    
    added = 0
    updated = 0
    skipped = 0
    errors = []
    
    try:
        for i, row in enumerate(reader, start=2):  # 第2行开始是数据
            try:
                category_name = row.get('category_name', '').strip()
                english_word = row.get('english_word', '').strip()
                british_phonetic = row.get('british_phonetic', '').strip()
                american_phonetic = row.get('american_phonetic', '').strip()
                chinese_definition = row.get('chinese_definition', '').strip()
                
                if not english_word:
                    errors.append(f'第{i}行：英文单词为空，跳过')
                    skipped += 1
                    continue
                
                if not category_name:
                    category_name = '其他'
                
                # 处理分类
                cursor = conn.execute('SELECT id FROM categories WHERE name = ?', (category_name,))
                cat = cursor.fetchone()
                if cat:
                    category_id = cat['id']
                else:
                    cursor = conn.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
                    category_id = cursor.lastrowid
                
                # 检查单词是否已存在
                cursor = conn.execute('SELECT id FROM vocabulary WHERE english_word = ?', (english_word,))
                existing = cursor.fetchone()
                
                if existing:
                    # 更新已存在的单词
                    conn.execute("""
                        UPDATE vocabulary 
                        SET category_id = ?, british_phonetic = ?, american_phonetic = ?, chinese_definition = ?
                        WHERE id = ?
                    """, (category_id, british_phonetic, american_phonetic, chinese_definition, existing['id']))
                    updated += 1
                else:
                    # 添加新单词
                    conn.execute("""
                        INSERT INTO vocabulary (category_id, english_word, british_phonetic, american_phonetic, chinese_definition)
                        VALUES (?, ?, ?, ?, ?)
                    """, (category_id, english_word, british_phonetic, american_phonetic, chinese_definition))
                    added += 1
                    
            except Exception as e:
                errors.append(f'第{i}行：{str(e)}')
                skipped += 1
        
        conn.commit()
        conn.close()
        
        add_log('批量导入', f'批量导入完成：新增{added}个，更新{updated}个，跳过{skipped}个')
        
        return jsonify({
            'success': True,
            'added': added,
            'updated': updated,
            'skipped': skipped,
            'errors': errors
        })
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'message': f'导入失败：{str(e)}'})

@app.route('/api/admin/export')
@login_required
def admin_export_words():
    """批量导出单词为CSV"""
    import csv
    import io
    
    category_id = request.args.get('category_id', type=int)
    category_name = request.args.get('category', '')
    
    conn = get_db()
    
    try:
        if category_id:
            # 按分类ID导出
            cursor = conn.execute("""
                SELECT v.*, c.name as category_name 
                FROM vocabulary v 
                JOIN categories c ON v.category_id = c.id 
                WHERE v.category_id = ? 
                ORDER BY v.id
            """, (category_id,))
        elif category_name:
            # 按分类名称导出
            cursor = conn.execute("""
                SELECT v.*, c.name as category_name 
                FROM vocabulary v 
                JOIN categories c ON v.category_id = c.id 
                WHERE c.name = ? 
                ORDER BY v.id
            """, (category_name,))
        else:
            # 导出全部
            cursor = conn.execute("""
                SELECT v.*, c.name as category_name 
                FROM vocabulary v 
                JOIN categories c ON v.category_id = c.id 
                ORDER BY c.name, v.id
            """)
        
        words = cursor.fetchall()
        conn.close()
        
        # 生成CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头（和导入模板一致）
        writer.writerow(['category_name', 'english_word', 'british_phonetic', 'american_phonetic', 'chinese_definition'])
        
        # 写入数据
        for word in words:
            writer.writerow([
                word['category_name'],
                word['english_word'],
                word['british_phonetic'],
                word['american_phonetic'],
                word['chinese_definition']
            ])
        
        # 添加UTF-8 BOM，解决Excel打开乱码问题
        csv_content = '\ufeff' + output.getvalue()
        output.close()
        
        # 记录日志
        if category_name:
            desc = f'导出分类「{category_name}」的单词，共{len(words)}个'
        elif category_id:
            desc = f'导出分类ID {category_id} 的单词，共{len(words)}个'
        else:
            desc = f'导出全部单词，共{len(words)}个'
        add_log('批量导出', desc)
        
        # 返回CSV文件
        from flask import Response
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=vocabulary_export.csv'}
        )
        
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'导出失败：{str(e)}'})

# ---------- 密码修改 ----------

@app.route('/api/admin/change-password', methods=['POST'])
@login_required
def admin_change_password():
    """修改密码"""
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    if not old_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': '请填写完整信息'})
    
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': '两次输入的新密码不一致'})
    
    if len(new_password) < 4:
        return jsonify({'success': False, 'message': '新密码长度不能少于4位'})
    
    username = session.get('username', '')
    if not username:
        return jsonify({'success': False, 'message': '未登录'})
    
    # MD5加密
    old_password_md5 = hashlib.md5(old_password.encode()).hexdigest()
    new_password_md5 = hashlib.md5(new_password.encode()).hexdigest()
    
    conn = get_db()
    
    # 验证旧密码
    cursor = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, old_password_md5))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'message': '旧密码错误'})
    
    # 更新密码
    cursor = conn.execute("UPDATE users SET password = ? WHERE username = ?", (new_password_md5, username))
    conn.commit()
    conn.close()
    
    add_log('修改密码', f'用户 {username} 修改了密码')
    
    return jsonify({'success': True, 'message': '密码修改成功'})

# ---------- 站点设置 ----------

@app.route('/api/admin/settings')
@login_required
def admin_get_settings():
    """获取站点设置"""
    conn = get_db()
    settings = conn.execute('SELECT * FROM site_settings WHERE id = 1').fetchone()
    conn.close()
    
    if not settings:
        return jsonify({'error': '设置不存在'}), 404
    
    return jsonify({
        'site_name': settings['site_name'],
        'site_description': settings['site_description'],
        'site_keywords': settings['site_keywords'],
        'site_copyright': settings['site_copyright'],
        'site_icp': settings['site_icp']
    })

@app.route('/api/admin/settings', methods=['PUT'])
@login_required
def admin_update_settings():
    """更新站点设置"""
    data = request.get_json()
    
    site_name = data.get('site_name', '').strip()
    site_description = data.get('site_description', '').strip()
    site_keywords = data.get('site_keywords', '').strip()
    site_copyright = data.get('site_copyright', '').strip()
    site_icp = data.get('site_icp', '').strip()
    
    if not site_name:
        return jsonify({'success': False, 'message': '站点名称不能为空'})
    
    conn = get_db()
    conn.execute("""
        UPDATE site_settings 
        SET site_name = ?, site_description = ?, site_keywords = ?, 
            site_copyright = ?, site_icp = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (site_name, site_description, site_keywords, site_copyright, site_icp))
    conn.commit()
    conn.close()
    
    add_log('修改站点设置', '更新了站点信息')
    
    return jsonify({'success': True, 'message': '站点设置更新成功'})

# ---------- 日志管理 ----------

@app.route('/api/admin/log-actions')
@login_required
def admin_get_log_actions():
    """获取所有操作类型"""
    conn = get_db()
    cursor = conn.execute("SELECT DISTINCT action FROM logs ORDER BY action")
    actions = [row['action'] for row in cursor.fetchall()]
    conn.close()
    return {'actions': actions}

@app.route('/api/admin/logs')
@login_required
def admin_get_logs():
    """获取日志列表（支持分页、操作类型筛选、归档状态筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    action = request.args.get('action', '')
    archived = request.args.get('archived', '0')  # 0: 未归档, 1: 已归档
    
    offset = (page - 1) * per_page
    
    conn = get_db()
    
    # 构建查询
    query = "SELECT * FROM logs WHERE 1=1"
    params = []
    
    if action:
        query += " AND action = ?"
        params.append(action)
    
    # 归档状态筛选
    if archived == '1':
        query += " AND is_archived = 1"
    else:
        query += " AND is_archived = 0"
    
    # 总数
    count_query = query.replace('SELECT *', 'SELECT COUNT(*) as count')
    cursor = conn.execute(count_query, params)
    total = cursor.fetchone()['count']
    
    # 分页数据（按时间倒序）
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    cursor = conn.execute(query, params)
    logs = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'logs': logs,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
        'archived': archived
    })

@app.route('/api/admin/log/<int:log_id>', methods=['DELETE'])
@login_required
def admin_delete_log(log_id):
    """删除单条日志"""
    conn = get_db()
    cursor = conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'success': False, 'message': '日志不存在'})
    
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/logs', methods=['DELETE'])
@login_required
def admin_clear_logs():
    """清空所有日志"""
    conn = get_db()
    cursor = conn.execute("DELETE FROM logs")
    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()
    
    add_log('清空日志', f'清空所有日志，共删除{deleted_count}条')
    
    return jsonify({'success': True, 'deleted': deleted_count})




@app.route('/api/admin/log/archive', methods=['POST'])
@login_required
def admin_archive_log():
    """归档日志（单条或批量）"""
    data = request.get_json()
    log_ids = data.get('ids', [])
    
    if not log_ids:
        return jsonify({'success': False, 'message': '请选择要归档的日志'})
    
    if isinstance(log_ids, int):
        log_ids = [log_ids]
    
    conn = get_db()
    
    # 构建IN条件
    placeholders = ','.join(['?' for _ in log_ids])
    
    # 执行归档
    cursor = conn.execute(
        f"UPDATE logs SET is_archived = 1 WHERE id IN ({placeholders})",
        log_ids
    )
    archived_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    add_log('归档日志', f'归档了{archived_count}条日志')
    
    return jsonify({
        'success': True,
        'message': f'成功归档了{archived_count}条日志',
        'archived_count': archived_count
    })

@app.route('/api/admin/log/unarchive', methods=['POST'])
@login_required
def admin_unarchive_log():
    """取消归档日志（单条或批量）"""
    data = request.get_json()
    log_ids = data.get('ids', [])
    
    if not log_ids:
        return jsonify({'success': False, 'message': '请选择要取消归档的日志'})
    
    if isinstance(log_ids, int):
        log_ids = [log_ids]
    
    conn = get_db()
    
    # 构建IN条件
    placeholders = ','.join(['?' for _ in log_ids])
    
    # 执行取消归档
    cursor = conn.execute(
        f"UPDATE logs SET is_archived = 0 WHERE id IN ({placeholders})",
        log_ids
    )
    unarchived_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    add_log('取消归档', f'取消归档了{unarchived_count}条日志')
    
    return jsonify({
        'success': True,
        'message': f'成功取消归档了{unarchived_count}条日志',
        'unarchived_count': unarchived_count
    })

@app.route('/api/admin/logs/archived', methods=['DELETE'])
@login_required
def admin_clear_archived_logs():
    """清空所有归档日志（永久删除）"""
    conn = get_db()
    cursor = conn.execute("DELETE FROM logs WHERE is_archived = 1")
    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()
    
    add_log('清空归档日志', f'永久删除了{deleted_count}条归档日志')
    
    return jsonify({'success': True, 'deleted': deleted_count})

@app.route('/api/admin/logs/auto-archive', methods=['POST'])
@login_required
def admin_auto_archive_logs():
    """自动归档超过90天的日志"""
    import datetime
    
    conn = get_db()
    
    # 计算90天前的日期
    ninety_days_ago = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
    
    # 执行自动归档
    cursor = conn.execute(
        "UPDATE logs SET is_archived = 1 WHERE is_archived = 0 AND created_at < ?",
        (ninety_days_ago,)
    )
    archived_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    if archived_count > 0:
        add_log('自动归档', f'自动归档了{archived_count}条超过90天的日志')
    
    return jsonify({
        'success': True,
        'message': f'自动归档了{archived_count}条超过90天的日志' if archived_count > 0 else '没有需要归档的日志',
        'archived_count': archived_count
    })



# ==================== AI模块相关API ====================

@app.route('/api/admin/ai-settings', methods=['GET'])
@login_required
def admin_get_ai_settings():
    """获取AI配置"""
    conn = get_db()
    cursor = conn.execute('SELECT * FROM ai_settings WHERE id = 1')
    settings = cursor.fetchone()
    conn.close()
    
    if settings:
        return jsonify({
            'success': True,
            'data': {
                'api_key': settings['api_key'],
                'api_url': settings['api_url'],
                'model_name': settings['model_name'],
                'system_prompt': settings['system_prompt']
            }
        })
    else:
        return jsonify({'success': False, 'message': '配置不存在'})

@app.route('/api/admin/ai-settings', methods=['PUT'])
@login_required
def admin_update_ai_settings():
    """更新AI配置"""
    data = request.get_json()
    
    api_key = data.get('api_key', '')
    api_url = data.get('api_url', '')
    model_name = data.get('model_name', '')
    system_prompt = data.get('system_prompt', '')
    
    if not api_url:
        return jsonify({'success': False, 'message': 'API地址不能为空'})
    
    conn = get_db()
    
    # 检查是否已有配置
    cursor = conn.execute('SELECT id FROM ai_settings WHERE id = 1')
    exists = cursor.fetchone()
    
    if exists:
        conn.execute('''
        UPDATE ai_settings 
        SET api_key = ?, api_url = ?, model_name = ?, system_prompt = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        ''', (api_key, api_url, model_name, system_prompt))
    else:
        conn.execute('''
        INSERT INTO ai_settings (api_key, api_url, model_name, system_prompt)
        VALUES (?, ?, ?, ?)
        ''', (api_key, api_url, model_name, system_prompt))
    
    conn.commit()
    conn.close()
    
    add_log('修改AI设置', '更新了AI配置信息')
    
    return jsonify({'success': True, 'message': '配置已保存'})


@app.route('/api/admin/ai-chat-history', methods=['GET'])
@login_required
def admin_get_ai_chat_history():
    """获取AI聊天历史"""
    conn = get_db()
    history = conn.execute('SELECT * FROM ai_chat_history ORDER BY created_at ASC LIMIT 100').fetchall()
    conn.close()
    
    return jsonify({
        'success': True,
        'history': [dict(h) for h in history]
    })

@app.route('/api/admin/ai-chat-history', methods=['DELETE'])
@login_required
def admin_clear_ai_chat_history():
    """清空AI聊天历史"""
    conn = get_db()
    conn.execute('DELETE FROM ai_chat_history')
    conn.commit()
    conn.close()
    
    add_log('clear_ai_chat', '清空AI聊天历史')
    
    return jsonify({'success': True, 'message': '聊天历史已清空'})

def execute_ai_action(action, data):
    """执行AI操作"""
    try:
        conn = get_db()
        
        # ========== 查询操作 ==========
        if action == 'query_categories':
            cursor = conn.execute("SELECT c.id, c.name, COUNT(v.id) as word_count FROM categories c LEFT JOIN vocabulary v ON c.id = v.category_id GROUP BY c.id ORDER BY c.id")
            categories = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return {'success': True, 'message': f'查询成功，共 {len(categories)} 个分类', 'data': categories}
        
        elif action == 'query_category_count':
            count = conn.execute('SELECT COUNT(*) as cnt FROM categories').fetchone()['cnt']
            conn.close()
            return {'success': True, 'message': f'共 {count} 个分类', 'count': count}
        
        elif action == 'query_category_by_name':
            name = data.get('name', '')
            category = conn.execute('SELECT * FROM categories WHERE name = ?', (name,)).fetchone()
            conn.close()
            if category:
                return {'success': True, 'message': f'找到分类：{name}', 'data': dict(category)}
            else:
                return {'success': False, 'message': f'分类不存在：{name}'}
        
        elif action == 'query_word_count':
            count = conn.execute('SELECT COUNT(*) as cnt FROM vocabulary').fetchone()['cnt']
            conn.close()
            return {'success': True, 'message': f'共 {count} 个单词', 'count': count}
        
        elif action == 'query_words':
            category_name = data.get('category_name')
            keyword = data.get('keyword', '')
            limit = data.get('limit', 50)
            
            sql = 'SELECT v.*, c.name as category_name FROM vocabulary v LEFT JOIN categories c ON v.category_id = c.id WHERE 1=1'
            params = []
            
            if category_name:
                sql += ' AND c.name = ?'
                params.append(category_name)
            
            if keyword:
                sql += ' AND (v.english_word LIKE ? OR v.chinese_definition LIKE ?)'
                params.extend([f'%{keyword}%', f'%{keyword}%'])
            
            sql += ' ORDER BY v.id LIMIT ?'
            params.append(limit)
            
            words = [dict(row) for row in conn.execute(sql, params).fetchall()]
            conn.close()
            return {'success': True, 'message': f'查询成功，共 {len(words)} 个单词', 'data': words}
        
        elif action == 'query_word_by_name':
            english_word = data.get('english_word', '')
            word = conn.execute("SELECT v.*, c.name as category_name FROM vocabulary v LEFT JOIN categories c ON v.category_id = c.id WHERE LOWER(v.english_word) = LOWER(?)", (english_word,)).fetchone()
            conn.close()
            if word:
                return {'success': True, 'message': f'找到单词：{english_word}', 'data': dict(word)}
            else:
                return {'success': False, 'message': f'单词不存在：{english_word}'}
        
        elif action == 'query_words_by_category':
            category_name = data.get('category_name', '')
            category = conn.execute('SELECT * FROM categories WHERE name = ?', (category_name,)).fetchone()
            if not category:
                conn.close()
                return {'success': False, 'message': f'分类不存在：{category_name}'}
            
            words = [dict(row) for row in conn.execute('SELECT * FROM vocabulary WHERE category_id = ? ORDER BY id', (category['id'],)).fetchall()]
            conn.close()
            return {'success': True, 'message': f'分类 {category_name} 共 {len(words)} 个单词', 'data': words}
        
        # ========== 修改操作 ==========
        elif action == 'add_category':
            name = data.get('name', '').strip()
            if not name:
                conn.close()
                return {'success': False, 'message': '分类名称不能为空'}
            
            exists = conn.execute('SELECT id FROM categories WHERE name = ?', (name,)).fetchone()
            if exists:
                conn.close()
                return {'success': False, 'message': f'分类已存在：{name}'}
            
            conn.execute('INSERT INTO categories (name) VALUES (?)', (name,))
            conn.commit()
            conn.close()
            add_log('ai_add_category', f'AI添加分类：{name}')
            return {'success': True, 'message': f'分类添加成功：{name}'}
        
        elif action == 'update_category':
            old_name = data.get('name', '')
            new_name = data.get('new_name', '').strip()
            
            if not new_name:
                conn.close()
                return {'success': False, 'message': '新分类名称不能为空'}
            
            category = conn.execute('SELECT * FROM categories WHERE name = ?', (old_name,)).fetchone()
            if not category:
                conn.close()
                return {'success': False, 'message': f'分类不存在：{old_name}'}
            
            exists = conn.execute('SELECT id FROM categories WHERE name = ? AND id != ?', (new_name, category['id'])).fetchone()
            if exists:
                conn.close()
                return {'success': False, 'message': f'分类名称已存在：{new_name}'}
            
            conn.execute('UPDATE categories SET name = ? WHERE id = ?', (new_name, category['id']))
            conn.commit()
            conn.close()
            add_log('ai_update_category', f'AI修改分类：{old_name} → {new_name}')
            return {'success': True, 'message': f'分类修改成功：{old_name} → {new_name}'}
        
        elif action == 'delete_category':
            name = data.get('name', '')
            category = conn.execute('SELECT * FROM categories WHERE name = ?', (name,)).fetchone()
            if not category:
                conn.close()
                return {'success': False, 'message': f'分类不存在：{name}'}
            
            conn.execute('DELETE FROM vocabulary WHERE category_id = ?', (category['id'],))
            conn.execute('DELETE FROM categories WHERE id = ?', (category['id'],))
            conn.commit()
            conn.close()
            add_log('ai_delete_category', f'AI删除分类：{name}')
            return {'success': True, 'message': f'分类删除成功：{name}（同时删除了该分类下的所有单词）'}
        
        elif action == 'add_word':
            english_word = data.get('english_word', '').strip()
            category_name = data.get('category_name', '')
            british_phonetic = data.get('british_phonetic', '')
            american_phonetic = data.get('american_phonetic', '')
            chinese_definition = data.get('chinese_definition', '')
            
            if not english_word:
                conn.close()
                return {'success': False, 'message': '英文单词不能为空'}
            if not chinese_definition:
                conn.close()
                return {'success': False, 'message': '中文释义不能为空'}
            
            exists = conn.execute('SELECT id FROM vocabulary WHERE LOWER(english_word) = LOWER(?)', (english_word,)).fetchone()
            if exists:
                conn.close()
                return {'success': False, 'message': f'单词已存在：{english_word}'}
            
            category_id = None
            if category_name:
                category = conn.execute('SELECT id FROM categories WHERE name = ?', (category_name,)).fetchone()
                if category:
                    category_id = category['id']
                else:
                    conn.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
                    category_id = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
                    add_log('ai_add_category', f'AI添加分类：{category_name}')
            
            conn.execute('INSERT INTO vocabulary (category_id, english_word, british_phonetic, american_phonetic, chinese_definition) VALUES (?, ?, ?, ?, ?)', 
                        (category_id, english_word, british_phonetic, american_phonetic, chinese_definition))
            conn.commit()
            conn.close()
            add_log('ai_add_word', f'AI添加单词：{english_word}')
            return {'success': True, 'message': f'单词添加成功：{english_word}'}
        
        elif action == 'update_word':
            english_word = data.get('english_word', '')
            word_id = data.get('id')
            
            word = None
            if word_id:
                word = conn.execute('SELECT * FROM vocabulary WHERE id = ?', (word_id,)).fetchone()
            elif english_word:
                word = conn.execute('SELECT * FROM vocabulary WHERE LOWER(english_word) = LOWER(?)', (english_word,)).fetchone()
            
            if not word:
                conn.close()
                return {'success': False, 'message': '单词不存在'}
            
            updates = []
            params = []
            
            if 'category_name' in data and data['category_name']:
                category = conn.execute('SELECT id FROM categories WHERE name = ?', (data['category_name'],)).fetchone()
                if not category:
                    conn.execute('INSERT INTO categories (name) VALUES (?)', (data['category_name'],))
                    category_id = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
                    add_log('ai_add_category', f'AI添加分类：{data["category_name"]}')
                else:
                    category_id = category['id']
                updates.append('category_id = ?')
                params.append(category_id)
            
            if 'british_phonetic' in data:
                updates.append('british_phonetic = ?')
                params.append(data['british_phonetic'])
            
            if 'american_phonetic' in data:
                updates.append('american_phonetic = ?')
                params.append(data['american_phonetic'])
            
            if 'chinese_definition' in data:
                updates.append('chinese_definition = ?')
                params.append(data['chinese_definition'])
            
            if 'english_word' in data and data['english_word'] != word['english_word']:
                exists = conn.execute('SELECT id FROM vocabulary WHERE LOWER(english_word) = LOWER(?) AND id != ?', (data['english_word'], word['id'])).fetchone()
                if exists:
                    conn.close()
                    return {'success': False, 'message': f'单词名已存在：{data["english_word"]}'}
                updates.append('english_word = ?')
                params.append(data['english_word'])
            
            if updates:
                params.append(word['id'])
                sql = f'UPDATE vocabulary SET {", ".join(updates)} WHERE id = ?'
                conn.execute(sql, params)
                conn.commit()
            
            conn.close()
            add_log('ai_update_word', f'AI修改单词：{word["english_word"]}')
            return {'success': True, 'message': f'单词修改成功：{word["english_word"]}'}
        
        elif action == 'delete_word':
            english_word = data.get('english_word', '')
            word_id = data.get('id')
            
            word = None
            if word_id:
                word = conn.execute('SELECT * FROM vocabulary WHERE id = ?', (word_id,)).fetchone()
            elif english_word:
                word = conn.execute('SELECT * FROM vocabulary WHERE LOWER(english_word) = LOWER(?)', (english_word,)).fetchone()
            
            if not word:
                conn.close()
                return {'success': False, 'message': '单词不存在'}
            
            conn.execute('DELETE FROM vocabulary WHERE id = ?', (word['id'],))
            conn.commit()
            conn.close()
            add_log('ai_delete_word', f'AI删除单词：{word["english_word"]}')
            return {'success': True, 'message': f'单词删除成功：{word["english_word"]}'}
        
        elif action == 'batch_delete_words':
            # 批量删除单词
            ids = data.get('ids', [])
            english_words = data.get('english_words', [])
            category_name = data.get('category_name', '')
            
            if not ids and not english_words and not category_name:
                conn.close()
                return {'success': False, 'message': '请提供要删除的单词ID、英文单词列表或分类名称'}
            
            # 如果是单个值，转成数组
            if isinstance(ids, (int, str)):
                ids = [ids]
            if isinstance(english_words, str):
                english_words = [english_words]
            
            deleted_count = 0
            deleted_words = []
            
            if ids:
                # 按ID删除
                placeholders = ','.join(['?' for _ in ids])
                # 先查询要删除的单词
                cursor = conn.execute(f'SELECT id, english_word FROM vocabulary WHERE id IN ({placeholders})', ids)
                words_to_delete = cursor.fetchall()
                deleted_words = [w['english_word'] for w in words_to_delete]
                
                # 执行删除
                conn.execute(f'DELETE FROM vocabulary WHERE id IN ({placeholders})', ids)
                deleted_count = len(words_to_delete)
            
            elif english_words:
                # 按英文单词删除
                placeholders = ','.join(['?' for _ in english_words])
                # 先查询要删除的单词
                lower_words = [w.lower() for w in english_words]
                placeholders_lower = ','.join(['?' for _ in lower_words])
                cursor = conn.execute(f'SELECT id, english_word FROM vocabulary WHERE LOWER(english_word) IN ({placeholders_lower})', lower_words)
                words_to_delete = cursor.fetchall()
                deleted_words = [w['english_word'] for w in words_to_delete]
                
                # 执行删除
                word_ids = [w['id'] for w in words_to_delete]
                if word_ids:
                    placeholders_ids = ','.join(['?' for _ in word_ids])
                    conn.execute(f'DELETE FROM vocabulary WHERE id IN ({placeholders_ids})', word_ids)
                    deleted_count = len(words_to_delete)
            
            elif category_name:
                # 按分类删除
                category = conn.execute('SELECT id, name FROM categories WHERE name = ?', (category_name,)).fetchone()
                if not category:
                    conn.close()
                    return {'success': False, 'message': f'分类不存在：{category_name}'}
                
                # 先查询要删除的单词数量
                cursor = conn.execute('SELECT COUNT(*) as count FROM vocabulary WHERE category_id = ?', (category['id'],))
                deleted_count = cursor.fetchone()['count']
                
                # 执行删除
                conn.execute('DELETE FROM vocabulary WHERE category_id = ?', (category['id'],))
            
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                desc = f'AI批量删除了{deleted_count}个单词'
                if category_name:
                    desc += f'（分类：{category_name}）'
                add_log('ai_batch_delete_word', desc)
            
            return {
                'success': True,
                'message': f'成功删除了{deleted_count}个单词',
                'deleted_count': deleted_count,
                'deleted_words': deleted_words[:10] if deleted_words else []  # 只返回前10个，避免太多
            }
        
        elif action == 'merge_categories':
            # 合并分类：把多个分类的单词移到目标分类，然后删除源分类
            from_categories = data.get('from_categories', [])
            to_category = data.get('to_category', '')
            
            if not from_categories or not to_category:
                conn.close()
                return {'success': False, 'message': '参数错误：需要from_categories和to_category'}
            
            if isinstance(from_categories, str):
                from_categories = [from_categories]
            
            # 确保目标分类存在
            target = conn.execute('SELECT id FROM categories WHERE name = ?', (to_category,)).fetchone()
            if target:
                target_id = target['id']
            else:
                conn.execute('INSERT INTO categories (name) VALUES (?)', (to_category,))
                target_id = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
                add_log('ai_add_category', f'AI添加分类：{to_category}')
            
            moved_count = 0
            deleted_count = 0
            
            for cat_name in from_categories:
                if cat_name == to_category:
                    continue
                cat = conn.execute('SELECT id FROM categories WHERE name = ?', (cat_name,)).fetchone()
                if cat:
                    # 移动该分类下的所有单词到目标分类
                    cursor = conn.execute('UPDATE vocabulary SET category_id = ? WHERE category_id = ?', (target_id, cat['id']))
                    moved_count += cursor.rowcount
                    # 删除源分类
                    conn.execute('DELETE FROM categories WHERE id = ?', (cat['id'],))
                    deleted_count += 1
            
            conn.commit()
            conn.close()
            add_log('ai_merge_category', f'AI合并分类：{len(from_categories)}个 -> {to_category}，移动{moved_count}个单词')
            return {'success': True, 'message': f'合并完成：移动了{moved_count}个单词，删除了{deleted_count}个分类', 'moved_count': moved_count, 'deleted_count': deleted_count}
        
        elif action == 'batch_add_words':
            # 批量添加/更新单词
            words = data.get('words', [])
            
            if not words:
                conn.close()
                return {'success': False, 'message': '单词列表为空'}
            
            added = 0
            updated = 0
            skipped = 0
            errors = []
            
            for idx, word in enumerate(words):
                try:
                    english_word = word.get('english_word', '').strip()
                    category_name = word.get('category_name', '其他').strip()
                    british_phonetic = word.get('british_phonetic', '').strip()
                    american_phonetic = word.get('american_phonetic', '').strip()
                    chinese_definition = word.get('chinese_definition', '').strip()
                    
                    if not english_word:
                        errors.append(f'第{idx+1}个：英文单词为空')
                        skipped += 1
                        continue
                    
                    if not chinese_definition:
                        errors.append(f'第{idx+1}个：中文释义为空')
                        skipped += 1
                        continue
                    
                    # 处理分类
                    cat = conn.execute('SELECT id FROM categories WHERE name = ?', (category_name,)).fetchone()
                    if cat:
                        category_id = cat['id']
                    else:
                        conn.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
                        category_id = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
                        add_log('ai_add_category', f'AI添加分类：{category_name}')
                    
                    # 检查单词是否已存在
                    existing = conn.execute('SELECT id FROM vocabulary WHERE LOWER(english_word) = LOWER(?)', (english_word,)).fetchone()
                    
                    if existing:
                        # 更新
                        conn.execute('UPDATE vocabulary SET category_id = ?, british_phonetic = ?, american_phonetic = ?, chinese_definition = ? WHERE id = ?', 
                            (category_id, british_phonetic, american_phonetic, chinese_definition, existing['id']))
                        updated += 1
                    else:
                        # 添加
                        conn.execute('INSERT INTO vocabulary (category_id, english_word, british_phonetic, american_phonetic, chinese_definition) VALUES (?, ?, ?, ?, ?)',
                            (category_id, english_word, british_phonetic, american_phonetic, chinese_definition))
                        added += 1
                        
                except Exception as e:
                    errors.append(f'第{idx+1}个：{str(e)}')
                    skipped += 1
            
            conn.commit()
            conn.close()
            add_log('ai_batch_add_word', f'AI批量添加单词：新增{added}个，更新{updated}个，跳过{skipped}个')
            return {
                'success': True, 
                'message': f'批量处理完成：新增{added}个，更新{updated}个，跳过{skipped}个',
                'added': added,
                'updated': updated,
                'skipped': skipped,
                'errors': errors[:10]
            }
        
        elif action == 'chat':
            message = data.get('message', '')
            conn.close()
            return {'success': True, 'message': message}
        
        else:
            conn.close()
            return {'success': False, 'message': f'未知操作：{action}'}
    
    except Exception as e:
        return {'success': False, 'message': f'操作失败：{str(e)}'}


@app.route('/api/ai-example', methods=['POST'])
@login_required
def ai_example():
    """生成AI例句"""
    data = request.get_json()
    word = data.get('word', '')
    category = data.get('category', '')
    
    if not word:
        return jsonify({'success': False, 'message': '请提供单词'})
    
    # 获取AI配置
    conn = get_db()
    settings = dict(conn.execute('SELECT * FROM ai_settings WHERE id = 1').fetchone())
    conn.close()
    
    if not settings.get('api_key'):
        return jsonify({'success': False, 'message': '请先在管理后台配置AI API Key'})
    
    try:
        api_url = settings['api_url']
        api_key = settings['api_key']
        model_name = settings['model_name'] or 'gpt-3.5-turbo'
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        # 构建prompt
        prompt = f"""请为单词 "{word}" 生成至少3个应用场景的中英文例句。
这个单词属于"{category}"分类，请结合这个分类的应用场景来造句。

要求：
1. 至少3个例句
2. 每个例句包含英文句子和对应的中文翻译
3. 句子要符合该单词在{category}领域的实际应用场景
4. 例句要自然、实用、有代表性

返回格式：
[
  {{"english": "英文例句1", "chinese": "中文翻译1"}},
  {{"english": "英文例句2", "chinese": "中文翻译2"}},
  {{"english": "英文例句3", "chinese": "中文翻译3"}}
]

只返回JSON数组，不要其他文字。"""
        
        messages = [
            {'role': 'system', 'content': '你是一个专业的英语老师，擅长结合专业领域背景生成实用的例句。'},
            {'role': 'user', 'content': prompt}
        ]
        
        payload = {
            'model': model_name,
            'messages': messages,
            'temperature': 0.7
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        ai_content = result['choices'][0]['message']['content'].strip()
        
        # 解析JSON
        examples = []
        try:
            # 尝试直接解析
            examples = json.loads(ai_content)
        except:
            # 尝试提取JSON数组
            import re
            match = re.search(r'\[.*\]', ai_content, re.DOTALL)
            if match:
                try:
                    examples = json.loads(match.group())
                except:
                    pass
        
        if not examples:
            # 如果解析失败，返回原始内容
            return jsonify({
                'success': True, 
                'examples': [{'english': ai_content, 'chinese': ''}],
                'raw': ai_content
            })
        
        # 记录操作日志
        add_log('ai_generate_example', f'生成单词 "{word}" 的例句，共{len(examples)}个')
        
        return jsonify({
            'success': True,
            'examples': examples
        })
        
    except Exception as e:
        print(f'生成例句失败: {e}')
        return jsonify({'success': False, 'message': f'生成例句失败: {str(e)}'})


@app.route('/api/ai-complete-word', methods=['POST'])
@login_required
def ai_complete_word():
    """AI补全单词信息（音标、释义）"""
    data = request.get_json()
    word = data.get('word', '')
    category = data.get('category', '')
    
    if not word:
        return jsonify({'success': False, 'message': '请提供英文单词'})
    
    # 获取AI配置
    conn = get_db()
    settings = dict(conn.execute('SELECT * FROM ai_settings WHERE id = 1').fetchone())
    conn.close()
    
    if not settings.get('api_key'):
        return jsonify({'success': False, 'message': '请先在管理后台配置AI API Key'})
    
    try:
        api_url = settings['api_url']
        api_key = settings['api_key']
        model_name = settings['model_name'] or 'gpt-3.5-turbo'
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        # 构建prompt
        category_prompt = f'，这个单词属于"{category}"分类' if category else ''
        
        prompt = f"""请为单词 "{word}" 补全以下信息{category_prompt}：
1. 英式音标（使用IPA国际音标，用/ /包裹）
2. 美式音标（使用IPA国际音标，用/ /包裹）
3. 中文释义（包含中文术语和详细解释，格式："中文术语：详细解释说明"）

要求：
- 音标要准确，使用标准的IPA国际音标
- 中文释义要专业、准确，结合专业领域背景
- 释义格式："中文术语：详细解释说明"

返回格式：
{{
  "british_phonetic": "英式音标",
  "american_phonetic": "美式音标",
  "chinese_definition": "中文释义"
}}

只返回JSON，不要其他文字。"""
        
        messages = [
            {'role': 'system', 'content': '你是一个专业的英语词典编辑，擅长提供准确的音标和专业的中文释义。'},
            {'role': 'user', 'content': prompt}
        ]
        
        payload = {
            'model': model_name,
            'messages': messages,
            'temperature': 0.3
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        ai_content = result['choices'][0]['message']['content'].strip()
        
        # 解析JSON
        word_info = {}
        try:
            # 尝试直接解析
            word_info = json.loads(ai_content)
        except:
            # 尝试提取JSON对象
            import re
            match = re.search(r'\{.*\}', ai_content, re.DOTALL)
            if match:
                try:
                    word_info = json.loads(match.group())
                except:
                    pass
        
        if not word_info:
            return jsonify({
                'success': False, 
                'message': '解析AI返回结果失败',
                'raw': ai_content
            })
        
        # 记录操作日志
        add_log('ai_complete_word', f'AI补全单词 "{word}" 的信息')
        
        return jsonify({
            'success': True,
            'british_phonetic': word_info.get('british_phonetic', ''),
            'american_phonetic': word_info.get('american_phonetic', ''),
            'chinese_definition': word_info.get('chinese_definition', '')
        })
        
    except Exception as e:
        print(f'AI补全单词失败: {e}')
        return jsonify({'success': False, 'message': f'AI补全失败: {str(e)}'})


@app.route('/api/admin/ai-chat', methods=['POST'])
@login_required
def admin_ai_chat():
    """AI聊天接口 - 任务列表模式"""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'success': False, 'message': '消息不能为空'})
    
    # 保存用户消息
    conn = get_db()
    conn.execute('INSERT INTO ai_chat_history (role, content) VALUES (?, ?)', ('user', user_message))
    conn.commit()
    
    # 获取AI配置
    settings = dict(conn.execute('SELECT * FROM ai_settings WHERE id = 1').fetchone())
    conn.close()
    
    if not settings.get('api_key'):
        return jsonify({'success': False, 'message': '请先配置AI API Key'})
    
    task_list = []
    task_results = []
    final_summary = ''
    
    try:
        api_url = settings['api_url']
        api_key = settings['api_key']
        model_name = settings['model_name'] or 'gpt-3.5-turbo'
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        # ========== 阶段1：AI规划任务 ==========
        messages = [
            {'role': 'system', 'content': settings['system_prompt']},
            {'role': 'user', 'content': user_message}
        ]
        
        plan_messages = messages.copy()
        plan_messages.append({
            'role': 'user',
            'content': '请先分析我的需求，列出你需要执行的任务清单。\n\n任务类型说明：\n- query：查询数据，不修改任何内容\n- modify：修改数据（添加、修改、删除单词或分类）\n- analyze：分析数据，给出结论或建议，不修改数据\n\n重要：如果用户要求"重新分类"、"调整分类"、"修改"、"添加"、"删除"等需要改动数据的操作，请务必设为modify类型，不要设为analyze。\n\n返回JSON格式：{"action": "plan_tasks", "data": {"tasks": [{"id": 1, "name": "任务名称", "description": "任务描述", "type": "query/modify/analyze"}]}}。只返回JSON，不要其他文字。'
        })
        
        payload = {
            'model': model_name,
            'messages': plan_messages,
            'temperature': 0.7
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        plan_content = result['choices'][0]['message']['content'].strip()
        
        # 解析任务列表
        tasks = []
        try:
            plan_data = None
            # 1. 先尝试直接解析
            try:
                plan_data = json.loads(plan_content.strip())
            except:
                # 2. 找markdown代码块
                try:
                    import re
                    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', plan_content, re.DOTALL)
                    if json_match:
                        plan_data = json.loads(json_match.group(1).strip())
                except:
                    # 3. 括号深度匹配
                    json_start = plan_content.find('{')
                    if json_start >= 0:
                        depth = 0
                        json_end = -1
                        for i in range(json_start, len(plan_content)):
                            if plan_content[i] == '{':
                                depth += 1
                            elif plan_content[i] == '}':
                                depth -= 1
                                if depth == 0:
                                    json_end = i + 1
                                    break
                        if json_end > json_start:
                            json_str = plan_content[json_start:json_end]
                            plan_data = json.loads(json_str)
            
            if plan_data and plan_data.get('action') == 'plan_tasks':
                tasks = plan_data.get('data', {}).get('tasks', [])
        except:
            pass
        
        if not tasks:
            tasks = [
                {'id': 1, 'name': '分析需求', 'description': '分析用户需求', 'type': 'analyze'},
                {'id': 2, 'name': '执行操作', 'description': '执行相应的操作', 'type': 'modify'}
            ]
        
        task_list = tasks
        
        # ========== 阶段2：逐个执行任务 ==========
        current_messages = messages.copy()
        
        for task in tasks:
            task_name = task.get('name', '未知任务')
            task_type = task.get('type', 'query')
            task_desc = task.get('description', '')
            
            task_result = {
                'id': task.get('id'),
                'name': task_name,
                'description': task_desc,
                'type': task_type,
                'status': 'running',
                'result': ''
            }
            
            try:
                if task_type == 'query':
                    # 查询类任务
                    query_msg = f'执行任务：{task_name}。请返回具体的查询操作，JSON格式。'
                    current_messages.append({'role': 'user', 'content': query_msg})
                    
                    payload = {'model': model_name, 'messages': current_messages, 'temperature': 0.7}
                    response = requests.post(api_url, headers=headers, json=payload, timeout=60)
                    response.raise_for_status()
                    ai_content = response.json()['choices'][0]['message']['content'].strip()
                    
                    # 解析查询操作
                    ai_data = None
                    try:
                        ai_data = json.loads(ai_content.strip())
                    except:
                        try:
                            import re
                            json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', ai_content, re.DOTALL)
                            if json_match:
                                ai_data = json.loads(json_match.group(1).strip())
                        except:
                            try:
                                json_start = ai_content.find('{')
                                if json_start >= 0:
                                    depth = 0
                                    json_end = -1
                                    for i in range(json_start, len(ai_content)):
                                        if ai_content[i] == '{':
                                            depth += 1
                                        elif ai_content[i] == '}':
                                            depth -= 1
                                            if depth == 0:
                                                json_end = i + 1
                                                break
                                    if json_end > json_start:
                                        ai_data = json.loads(ai_content[json_start:json_end])
                            except:
                                pass
                    
                    if ai_data and ai_data.get('action', '').startswith('query_'):
                        action = ai_data.get('action')
                        action_data = ai_data.get('data', {})
                        action_result = execute_ai_action(action, action_data)
                        
                        if action_result['success']:
                            task_result['status'] = 'success'
                            task_result['result'] = action_result.get('message', '查询成功')
                            # 把完整的查询结果加入上下文，AI需要详细数据才能进行后续分析
                            current_messages.append({'role': 'assistant', 'content': json.dumps(ai_data, ensure_ascii=False)})
                            current_messages.append({'role': 'user', 'content': json.dumps(action_result, ensure_ascii=False)})
                        else:
                            task_result['status'] = 'failed'
                            task_result['result'] = action_result.get('message', '查询失败')
                            current_messages.append({'role': 'assistant', 'content': ai_content})
                            current_messages.append({'role': 'user', 'content': action_result.get('message', '查询失败')})
                    else:
                        task_result['status'] = 'failed'
                        task_result['result'] = '未找到有效的查询操作'
                        current_messages.append({'role': 'assistant', 'content': ai_content})
                elif task_type == 'modify':
                    # 修改类任务（支持多轮修改）
                    modify_msg = '执行任务：' + task_name + '。你必须返回JSON格式的修改操作，我会立即执行。\n\n严格要求：\n1. 绝对不能用自然语言描述你要做什么，必须直接返回JSON\n2. 每次只返回一个操作\n3. 必须执行完所有修改后，才能用chat操作返回总结\n4. 如果你直接返回chat而不执行任何修改，任务会失败\n\n格式：{"action": "update_word", "data": {"english_word": "xxx", "category_name": "xxx"}}'
                    current_messages.append({'role': 'user', 'content': modify_msg})
                    
                    modify_count = 0
                    modified_count = 0
                    max_rounds = 50  # 最多50轮
                    
                    while modify_count < max_rounds:
                        modify_count += 1
                        
                        # 发送请求
                        payload = {'model': model_name, 'messages': current_messages, 'temperature': 0.7}
                        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
                        response.raise_for_status()
                        ai_content = response.json()['choices'][0]['message']['content'].strip()
                        
                        # 解析JSON
                        ai_data = None
                        try:
                            ai_data = json.loads(ai_content.strip())
                        except:
                            try:
                                import re
                                json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', ai_content, re.DOTALL)
                                if json_match:
                                    ai_data = json.loads(json_match.group(1).strip())
                            except:
                                try:
                                    json_start = ai_content.find('{')
                                    if json_start >= 0:
                                        depth = 0
                                        json_end = -1
                                        for i in range(json_start, len(ai_content)):
                                            if ai_content[i] == '{':
                                                depth += 1
                                            elif ai_content[i] == '}':
                                                depth -= 1
                                                if depth == 0:
                                                    json_end = i + 1
                                                    break
                                        if json_end > json_start:
                                            ai_data = json.loads(ai_content[json_start:json_end])
                                except:
                                    pass
                        
                        if ai_data:
                            action = ai_data.get('action', '')
                            action_data = ai_data.get('data', {})
                            
                            if action in ['add_word', 'update_word', 'delete_word', 'add_category', 'update_category', 'delete_category', 'merge_categories', 'batch_add_words', 'batch_delete_words']:
                                # 执行修改操作
                                action_result = execute_ai_action(action, action_data)
                                if action_result['success']:
                                    modified_count += 1
                                
                                # 只把操作结果加入上下文，不加入完整的AI回复（减少冗余）
                                current_messages.append({'role': 'assistant', 'content': json.dumps(ai_data, ensure_ascii=False)})
                                current_messages.append({'role': 'user', 'content': action_result['message']})
                                continue
                            
                            elif action == 'chat':
                                # 完成了，记录总结
                                task_result['result'] = action_data.get('message', ai_content)
                                current_messages.append({'role': 'assistant', 'content': ai_content})
                                break
                            
                            elif action.startswith('query_'):
                                # 查询操作，也执行
                                action_result = execute_ai_action(action, action_data)
                                current_messages.append({'role': 'assistant', 'content': json.dumps(ai_data, ensure_ascii=False)})
                                current_messages.append({'role': 'user', 'content': json.dumps(action_result, ensure_ascii=False)})
                                continue
                            
                            else:
                                # 未知操作，提示AI重新返回
                                current_messages.append({'role': 'assistant', 'content': ai_content})
                                current_messages.append({'role': 'user', 'content': '请返回正确的JSON操作格式，只返回JSON，不要其他文字。'})
                                continue
                        else:
                            # 解析失败，提示AI重新返回
                            current_messages.append({'role': 'assistant', 'content': ai_content})
                            current_messages.append({'role': 'user', 'content': '解析失败，请返回纯JSON格式，不要包含解释文字。格式：{"action": "操作类型", "data": {参数}}'})
                            continue
                    
                    task_result['status'] = 'success'
                    if modified_count > 0:
                        task_result['result'] = f'已完成 {modified_count} 项修改操作'
                    else:
                        task_result['result'] = '任务完成'
                elif task_type == 'analyze':
                    # 分析类任务
                    analyze_msg = f'执行任务：{task_name}。请根据已有信息进行分析，给出分析结论。'
                    current_messages.append({'role': 'user', 'content': analyze_msg})
                    
                    payload = {'model': model_name, 'messages': current_messages, 'temperature': 0.7}
                    response = requests.post(api_url, headers=headers, json=payload, timeout=60)
                    response.raise_for_status()
                    ai_content = response.json()['choices'][0]['message']['content'].strip()
                    
                    task_result['status'] = 'success'
                    task_result['result'] = ai_content[:500]
                    current_messages.append({'role': 'assistant', 'content': ai_content})
                
                else:
                    current_messages.append({'role': 'user', 'content': f'执行任务：{task_name}'})
                    payload = {'model': model_name, 'messages': current_messages, 'temperature': 0.7}
                    response = requests.post(api_url, headers=headers, json=payload, timeout=60)
                    response.raise_for_status()
                    ai_content = response.json()['choices'][0]['message']['content'].strip()
                    
                    task_result['status'] = 'success'
                    task_result['result'] = ai_content[:300]
                    current_messages.append({'role': 'assistant', 'content': ai_content})
            
            except Exception as e:
                task_result['status'] = 'failed'
                task_result['result'] = f'执行失败：{str(e)}'
            
            task_results.append(task_result)
        
        # ========== 阶段3：生成总结 ==========
        try:
            current_messages.append({'role': 'user', 'content': '所有任务已执行完毕，请用自然语言生成一个总结，告诉用户完成了什么。'})
            payload = {'model': model_name, 'messages': current_messages, 'temperature': 0.7}
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            final_summary = response.json()['choices'][0]['message']['content'].strip()
        except:
            final_summary = '任务执行完成。'
        
        # ========== 构建最终回复 ==========
        reply_parts = []
        
        # 任务清单
        reply_parts.append('📋 **任务清单**')
        for task in task_list:
            status_icon = '⏳'
            for tr in task_results:
                if tr['id'] == task['id']:
                    if tr['status'] == 'success':
                        status_icon = '✅'
                    elif tr['status'] == 'failed':
                        status_icon = '❌'
                    break
            desc = task.get('description', '')
            if desc:
                reply_parts.append(f'{status_icon} {task["id"]}. {task["name"]} - {desc}')
            else:
                reply_parts.append(f'{status_icon} {task["id"]}. {task["name"]}')
        
        reply_parts.append('')
        
        # 执行详情
        reply_parts.append('📝 **执行详情**')
        for tr in task_results:
            icon = '✅' if tr['status'] == 'success' else ('❌' if tr['status'] == 'failed' else '⏳')
            reply_parts.append(f'{icon} **{tr["name"]}**')
            if tr['result']:
                result_text = tr['result']
                if len(result_text) > 300:
                    result_text = result_text[:300] + '...'
                reply_parts.append(f'   {result_text}')
            reply_parts.append('')
        
        # 总结
        reply_parts.append('📊 **总结**')
        reply_parts.append(final_summary)
        
        reply_message = chr(10).join(reply_parts)
        
    except requests.exceptions.RequestException as e:
        reply_message = f'❌ API调用失败：{str(e)}'
    except Exception as e:
        reply_message = f'❌ 处理请求时出错：{str(e)}'
    
    # 保存AI回复
    conn = get_db()
    conn.execute('INSERT INTO ai_chat_history (role, content) VALUES (?, ?)', ('assistant', reply_message))
    conn.commit()
    conn.close()
    
    add_log('ai_chat', f'用户消息：{user_message[:100]}')
    
    return jsonify({
        'success': True,
        'message': reply_message,
        'reply': reply_message,
        'task_list': task_list,
        'task_results': task_results,
        'summary': final_summary
    })


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
