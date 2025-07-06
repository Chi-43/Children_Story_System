from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
from dotenv import load_dotenv
import requests
import json
import jwt as pyjwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
import time
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import Tongyi
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader

load_dotenv()

app = Flask(__name__)
CORS(app)

# 通义千问API配置
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET') or 'your-secret-key'
app.config['TONGYI_API_KEY'] = os.getenv('DASHSCOPE_API_KEY')
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
DASHSCOPE_API_URL = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation'


# 初始化LangChain组件
llm = Tongyi(
    dashscope_api_key=app.config['TONGYI_API_KEY'],
    model_name="qwen-turbo",
    temperature=0.7
)

# 故事生成模板
story_template = """#角色
-你是一个儿童心理大师兼职儿童故事专家，懂得很多儿童心理知识，很会做心理分析，能根据儿童的描述来评估他们的心理状态，并且能够在对儿童完成心理分析后给他们讲述故事。
-你的主体是讲述儿童故事，情绪分析只是你为讲故事而做的必要准备

#技能
-你会接收用户的对话
-你会根据儿童对话中的要求来为他们讲故事
-你会根据用户对话或者对故事评价中的语气及描述来评判用户的心理情绪并总结后输出
-你会根据之前对用户的心理情绪评估来为他们讲述合适的故事

#限制
-不得违反事实或者造假
-遵守版权和知识产权法规
-你的用户对象是12岁以下的儿童,请不要输出儿童不宜的内容。

# 思维链要求
要求你给出思考过程 之后再生成故事
思考过程与故事之间用'-' 分割 eg. - 思考过程 - 故事
要求思考步骤清晰,明确

用户输入：{message}
"""

story_prompt = PromptTemplate(
    input_variables=["age", "theme", "requirements", "length"],
    template=story_template
)

story_chain = story_prompt | llm

# 文本分割器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

import mysql.connector.pooling

# MySQL 连接池配置
dbconfig = {
    "host": os.getenv('MYSQL_HOST', 'localhost'),
    "port": int(os.getenv('MYSQL_PORT', 3306)),
    "user": os.getenv('MYSQL_USER', 'root'),
    "password": os.getenv('MYSQL_PASSWORD'),
    "database": os.getenv('MYSQL_DB', 'story_app'),
    "pool_name": "story_pool",
    "pool_size": 5,
    "autocommit": True,
    "connect_timeout": 5
}

connection_pool = mysql.connector.pooling.MySQLConnectionPool(**dbconfig)

def get_mysql_connection():
    max_retries = 3
    last_error = None
    conn = None
    
    for attempt in range(max_retries):
        try:
            conn = connection_pool.get_connection()
            # 验证连接是否有效
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchall()  # 确保读取所有结果
            
            # 检查连接是否超过1小时未使用
            if hasattr(conn, '_creation_time'):
                if time.time() - conn._creation_time > 3600:
                    conn.reconnect()
            else:
                conn._creation_time = time.time()
            return conn
            
        except mysql.connector.Error as err:
            last_error = err
            app.logger.error(f"数据库连接尝试 {attempt + 1}/{max_retries} 失败: {err}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 等待1秒后重试
            if conn and conn.is_connected():
                conn.close()
    
    # 所有重试都失败后抛出最后一个错误
    raise mysql.connector.PoolError(f"无法获取数据库连接: {last_error}")

# 初始化数据库
def init_db():
    try:
        # 测试数据库连接是否可用
        try:
            conn = get_mysql_connection()
            if conn is None:
                raise mysql.connector.PoolError("无法获取数据库连接")
        except mysql.connector.Error as e:
            app.logger.error(f"数据库连接测试失败: {str(e)}")
            raise

        try:
            with conn.cursor() as cursor:
                # 创建users表（必须先创建，因为其他表引用它）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(255) UNIQUE NOT NULL,
                        password VARCHAR(255) NOT NULL
                    )
                """)

                # 创建conversations表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)

                # 创建chat_history表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        role ENUM('user', 'assistant') NOT NULL,
                        content TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        conversation_id INT,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                    )
                """)

                # 创建story_history表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS story_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        input_prompt TEXT,
                        thinking TEXT,
                        story TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
        except Error as e:
            app.logger.error(f"数据库初始化失败: {str(e)}")
            raise
        conn.commit()
    except Error as e:
        app.logger.error(f"数据库初始化失败: {str(e)}")
        raise
    finally:
        if conn and conn.is_connected():
            conn.close()

init_db()

# JWT
def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return pyjwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

# 保存消息与故事
def save_chat_message(user_id, role, content, conversation_id=None):
    conn = get_mysql_connection()
    cursor = conn.cursor()
    if conversation_id:
        cursor.execute(
            "INSERT INTO chat_history (user_id, role, content, conversation_id) VALUES (%s, %s, %s, %s)",
            (user_id, role, content, conversation_id)
        )
    else:
        cursor.execute(
            "INSERT INTO chat_history (user_id, role, content) VALUES (%s, %s, %s)",
            (user_id, role, content)
        )
    conn.commit()
    conn.close()

def save_story_history(user_id, input_prompt, thinking, story):
    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO story_history (user_id, input_prompt, thinking, story) VALUES (%s, %s, %s, %s)",
        (user_id, input_prompt, thinking, story)
    )
    conn.commit()
    conn.close()


# 注册接口
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    hashed_password = generate_password_hash(password)
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            return jsonify({'error': 'REGISTER_ERROR', 'message': '用户名已存在', 'action': 'redirect_to_login'}), 400
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        token = create_token(user_id)
        return jsonify({'token': token, 'user_id': user_id}), 201
    except Error as e:
        return jsonify({'error': '数据库错误', 'message': str(e)}), 500

# 登录接口
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        conn.close()
        if not user or not check_password_hash(user[1], password):
            return jsonify({'error': 'LOGIN_ERROR', 'message': '用户名或密码错误'}), 401
        token = create_token(user[0])
        return jsonify({'token': token, 'user_id': user[0]})
    except Error as e:
        return jsonify({'error': '数据库错误', 'message': str(e)}), 500

# 调用通义千问API
@app.route('/api/ask', methods=['POST'])
def ask_question():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401

    token = auth_header.split(' ')[1]

    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    except pyjwt.ExpiredSignatureError:
        return jsonify({'error': 'token已过期'}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效的token'}), 401

    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({'error': '缺少问题参数'}), 400

    question = data['question']

    try:
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {app.config['TONGYI_API_KEY']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "qwen-turbo",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": question
                    }
                ]
            }
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        result = response.json()
        if 'output' not in result or 'text' not in result['output']:
            raise ValueError('无效的API响应格式')

        return jsonify({
            'answer': result['output']['text'],
            'request_id': result.get('request_id', '')
        })

    except requests.exceptions.RequestException as e:
        app.logger.error(f'调用通义千问API失败: {str(e)}')
        return jsonify({'error': f'调用AI服务失败: {str(e)}'}), 500
    except ValueError as e:
        app.logger.error(f'API响应解析失败: {str(e)}')
        return jsonify({'error': str(e)}), 500

# 故事生成接口（流式）
@app.route('/api/generate_story', methods=['POST'])
def generate_story():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401
    token = auth_header.split(' ')[1]
    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
    except pyjwt.ExpiredSignatureError:
        return jsonify({'error': 'token已过期'}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效的token'}), 401

    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({'error': '缺少prompt参数'}), 400

    prompt_content = story_template.format(message=data['prompt'])
    save_chat_message(user_id, 'user', data['prompt'])

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-SSE": "enable"
    }
    payload_post = {
        "model": "qwen-turbo",
        "input": {
            "messages": [{"role": "user", "content": prompt_content}]
        },
        "parameters": {
            "incremental_output": True,
            "temperature": 0.8,
            "top_p": 0.9
        }
    }

    result_buffer = []

    def generate():
        try:
            with requests.post(DASHSCOPE_API_URL, json=payload_post, headers=headers, stream=True, timeout=30) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            try:
                                data_chunk = json.loads(decoded_line[5:])
                                text = data_chunk['output'].get('text', '')
                                result_buffer.append(text)
                                yield f"data: {json.dumps({'text': text})}\n\n"
                            except Exception:
                                continue
        except Exception as e:
            yield f"data: {json.dumps({'error': '生成中断'})}\n\n"

    def finalize():
        full_text = ''.join(result_buffer)
        thinking, story = ('', full_text)
        if '-' in full_text:
            parts = full_text.split('-', 1)
            if len(parts) == 2:
                thinking, story = parts
        save_story_history(user_id, data['prompt'], thinking.strip(), story.strip())
        save_chat_message(user_id, 'assistant', story.strip())

    def generate_with_finalization():
        for chunk in generate():
            yield chunk
        finalize()

    return Response(generate_with_finalization(), mimetype='text/event-stream')


@app.route('/api/save_chat', methods=['POST'])
def save_chat():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        app.logger.error('未提供token')
        return jsonify({'error': '未提供token'}), 401
        
    token = auth_header.split(' ')[1]
    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
    except pyjwt.InvalidTokenError as e:
        app.logger.error(f'无效token: {str(e)}')
        return jsonify({'error': '无效token'}), 401

    data = request.get_json()
    if not data or 'content' not in data or 'role' not in data:
        app.logger.error('缺少必要参数')
        return jsonify({'error': '缺少必要参数'}), 400

    conn = None
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        
        # 检查conversation_id是否存在
        conversation_id = data.get('conversation_id')
        if conversation_id:
            # 验证conversation_id属于当前用户
            cursor.execute("SELECT id FROM conversations WHERE id=%s AND user_id=%s", 
                          (conversation_id, user_id))
            if not cursor.fetchone():
                app.logger.error(f'无效的conversation_id: {conversation_id}')
                return jsonify({'error': '无效的对话ID'}), 400
            
            sql = """
                INSERT INTO chat_history 
                (user_id, role, content, conversation_id) 
                VALUES (%s, %s, %s, %s)
            """
            params = (user_id, data['role'], data['content'], conversation_id)
        else:
            sql = """
                INSERT INTO chat_history 
                (user_id, role, content) 
                VALUES (%s, %s, %s)
            """
            params = (user_id, data['role'], data['content'])

        cursor.execute(sql, params)
        conn.commit()
        message_id = cursor.lastrowid
        
        return jsonify({
            'id': message_id,
            'message': '保存成功',
            'conversation_id': conversation_id
        }), 201
        
    except Error as e:
        app.logger.error(f'数据库错误: {str(e)}')
        return jsonify({
            'error': '数据库错误', 
            'message': str(e),
            'sql': sql,
            'params': params
        }), 500
    finally:
        if conn and conn.is_connected():
            conn.close()


# 查询故事历史
@app.route('/api/story_history', methods=['GET'])
def story_history():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供token'}), 401
    token = auth_header.split(' ')[1]
    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效token'}), 401

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM story_history WHERE user_id=%s ORDER BY timestamp DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

# 查询聊天历史
@app.route('/api/chat_history', methods=['GET'])
def chat_history():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供token'}), 401
    token = auth_header.split(' ')[1]
    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效token'}), 401

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM chat_history WHERE user_id=%s ORDER BY timestamp DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

# 创建新对话
@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供token'}), 401
    token = auth_header.split(' ')[1]
    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效token'}), 401

    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({'error': '缺少title参数'}), 400

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (user_id, title) VALUES (%s, %s)",
            (user_id, data['title'])
        )
        conn.commit()
        conversation_id = cursor.lastrowid
        conn.close()
        return jsonify({
            'id': conversation_id,
            'title': data['title'],
            'created_at': datetime.datetime.now().isoformat()
        }), 201
    except Error as e:
        return jsonify({'error': '数据库错误', 'message': str(e)}), 500

# 获取用户所有对话
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供token'}), 401
    token = auth_header.split(' ')[1]
    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效token'}), 401

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.id, c.title, c.created_at, 
               COUNT(m.id) as message_count,
               MAX(m.timestamp) as last_updated
        FROM conversations c
        LEFT JOIN chat_history m ON c.id = m.conversation_id
        WHERE c.user_id = %s
        GROUP BY c.id
        ORDER BY last_updated DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/api/delete_chat', methods=['DELETE'])
def delete_chat():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供token'}), 401
    token = auth_header.split(' ')[1]
    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效token'}), 401

    data = request.get_json()
    if not data or 'message_id' not in data:
        return jsonify({'error': '缺少message_id参数'}), 400

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chat_history WHERE id=%s AND user_id=%s",
            (data['message_id'], user_id)
        )
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()

        if affected_rows == 0:
            return jsonify({'error': '未找到消息或无权删除'}), 404
        return jsonify({'success': True}), 200
    except Error as e:
        return jsonify({'error': '数据库错误', 'message': str(e)}), 500


@app.route('/api/analyze_sentiment2', methods=['POST'])
def analyze_sentiment2():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401

    token = auth_header.split(' ')[1]

    try:
        payload = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    except pyjwt.ExpiredSignatureError:
        return jsonify({'error': 'token已过期'}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效的token'}), 401

    try:
        data = request.get_json()
        messages = data.get('messages', [])
        
        if not messages:
            return jsonify({'error': '没有提供消息内容'}), 400

        # 收集所有消息的时间戳
        timestamps = []
        for msg in messages:
            timestamp = msg.get('timestamp')
            # 确保时间戳是有效的日期格式
            if timestamp and isinstance(timestamp, str) and 'T' in timestamp:
                try:
                    # 验证并标准化时间格式
                    dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamps.append(dt.isoformat())
                except ValueError:
                    timestamps.append(datetime.datetime.now().isoformat())
            else:
                # 没有时间戳或格式无效，使用当前时间
                timestamps.append(datetime.datetime.now().isoformat())
        
        # 改进的提示词，确保返回正确的JSON格式
        prompt = f"""请分析以下对话的情感倾向,严格按照要求返回JSON格式数据:
        {{
            "overall": {{
                "label": "负面/中性/正面", 
                "score": 0.85,  // 0-1之间的小数
                "recommendation": "建议内容"
            }},
            "daily": [
                {{
                    "date": "YYYY-MM-DD",  // 仅日期部分，不要时间
                    "label": "负面/中性/正面", 
                    "score": 0.75  // 0-1之间的小数
                }}
            ],
            "samples": [
                {{
                    "content": "消息内容", 
                    "sentiment": {{
                        "label": "负面/中性/正面", 
                        "score": 0.9  // 0-1之间的小数
                    }}
                }}
            ]
        }}
        
        重要说明：
        1. 所有score必须是0-1之间的小数
        2. label只能使用"负面"、"中性"、"正面"三种值
        3. 样本消息从原始对话中选取最具代表性的3-5条
        4. 每日情感变化按日期分组分析
        5. 日期格式必须为YYYY-MM-DD(不要时间部分)
        
        对话记录:
        {chr(10).join([f"{msg.get('timestamp', '未知时间')} {msg['role']}: {msg['content']}" for msg in messages])}"""

        headers = {
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "qwen-turbo",
            "input": {
                "messages": [{
                    "role": "user", 
                    "content": prompt
                }]
            }
        }
        
        response = requests.post(
            DASHSCOPE_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        if 'output' not in result or 'text' not in result['output']:
            raise ValueError('无效的API响应格式')
        
        try:
            analysis_result = json.loads(result['output']['text'])
            
            # 修正分数值
            def fix_scores(data):
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key == 'score' and isinstance(value, (int, float)) and value > 1:
                            data[key] = value / 100.0
                        elif key == 'date' and isinstance(value, str) and 'T' in value:
                            # 确保日期格式正确
                            data[key] = value.split('T')[0]
                        else:
                            fix_scores(value)
                elif isinstance(data, list):
                    for item in data:
                        fix_scores(item)
            
            fix_scores(analysis_result)
            
            # 添加时间戳到样本消息
            if 'samples' in analysis_result:
                for i, sample in enumerate(analysis_result['samples']):
                    if i < len(timestamps):
                        sample['timestamp'] = timestamps[i]
            
            # 确保daily日期格式正确
            for day in analysis_result.get('daily', []):
                if 'date' in day and isinstance(day['date'], str):
                    if 'T' in day['date']:
                        day['date'] = day['date'].split('T')[0]
                    elif len(day['date']) > 10:
                        day['date'] = day['date'][:10]
            
            return jsonify(analysis_result)
        except json.JSONDecodeError:
            return jsonify({
                'error': 'API返回格式不正确',
                'raw_response': result['output']['text']
            }), 500
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': '请求AI服务失败',
            'details': str(e)
        }), 500
    except Exception as e:
        import traceback
        return jsonify({
            'error': '情感分析失败',
            'details': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/db_status', methods=['GET'])
def db_status():
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        return jsonify({
            'status': 'healthy',
            'pool_size': connection_pool.pool_size,
            'active_connections': len(connection_pool._cnx_queue._queue)
        })
    except Error as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
