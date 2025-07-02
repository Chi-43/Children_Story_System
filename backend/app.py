from flask import Flask, request, jsonify, Response
import json
from flask_cors import CORS
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
import requests
from mysql_db import get_connection
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatCoze
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from transformers import pipeline

# 加载环境变量
load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET') or 'your-secret-key'
app.config['COZE_API_KEY'] = os.getenv('COZE_API_KEY')

# 初始化LangChain组件
llm = ChatCoze(
    coze_api_key=app.config['COZE_API_KEY'],
    model="coze-chat-pro",
    temperature=0.7
)

# 故事生成模板
story_template = """你是一个儿童故事创作专家，请根据以下要求创作一个适合{age}岁儿童的故事：
主题：{theme}
故事要求：{requirements}
故事长度：约{length}字
请创作一个富有教育意义、积极向上的故事，避免任何暴力或不适宜内容。"""

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

# 情感分析模型
try:
    print("正在初始化情感分析模型...")
    sentiment_analyzer = pipeline(
        "text-classification",
        model="finiteautomata/bertweet-base-sentiment-analysis",
        tokenizer="finiteautomata/bertweet-base-sentiment-analysis",
        device="cpu",
        return_all_scores=True
    )
    print("情感分析模型初始化成功")
except Exception as e:
    print(f"初始化情感分析模型失败: {str(e)}")
    sentiment_analyzer = None

# 初始化数据库
from mysql_db import init_db
init_db()

# JWT工具函数
def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

# 用户注册
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    hashed_password = generate_password_hash(password)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({
                'error': 'REGISTER_ERROR',
                'message': '用户名已存在',
                'action': 'redirect_to_login'
            }), 400
            
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", 
                 (username, hashed_password))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        token = create_token(user_id)
        return jsonify({'token': token, 'user_id': user_id}), 201
    except Exception as e:
        return jsonify({
            'error': 'REGISTER_ERROR',
            'message': str(e)
        }), 500

# 用户登录
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user or not check_password_hash(user[1], password):
            return jsonify({
                'error': 'LOGIN_ERROR', 
                'message': '用户名或密码错误'
            }), 401
        
        token = create_token(user[0])
        return jsonify({'token': token, 'user_id': user[0]})
    except Exception as e:
        return jsonify({
            'error': 'LOGIN_ERROR',
            'message': str(e)
        }), 500

# 对话历史API
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401
    
    token = auth_header.split(' ')[1]
    
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, title, created_at 
            FROM conversations 
            WHERE user_id=%s 
            ORDER BY created_at DESC
        """, (user_id,))
        conversations = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify(conversations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 获取对话详情
@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401
    
    token = auth_header.split(' ')[1]
    
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 验证对话属于当前用户
        cursor.execute("""
            SELECT id FROM conversations 
            WHERE id=%s AND user_id=%s
        """, (conversation_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': '对话不存在或无权访问'}), 404
            
        # 获取对话消息
        cursor.execute("""
            SELECT id, role, content, sentiment, created_at
            FROM messages
            WHERE conversation_id=%s
            ORDER BY created_at ASC
        """, (conversation_id,))
        messages = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify(messages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 创建新对话
@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401
    
    token = auth_header.split(' ')[1]
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({'error': '缺少对话标题'}), 400
    
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversations (user_id, title)
            VALUES (%s, %s)
        """, (user_id, data['title']))
        conn.commit()
        conversation_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({
            'id': conversation_id,
            'title': data['title'],
            'created_at': datetime.datetime.now().isoformat()
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 保存消息
@app.route('/api/messages', methods=['POST'])
def save_message():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401
    
    token = auth_header.split(' ')[1]
    data = request.get_json()
    
    required_fields = ['conversation_id', 'role', 'content']
    if not all(field in data for field in required_fields):
        return jsonify({'error': '缺少必要参数'}), 400
    
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # 验证对话属于当前用户
        cursor.execute("""
            SELECT id FROM conversations 
            WHERE id=%s AND user_id=%s
        """, (data['conversation_id'], user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': '对话不存在或无权访问'}), 404
            
        # 保存消息
        cursor.execute("""
            INSERT INTO messages (conversation_id, role, content, sentiment)
            VALUES (%s, %s, %s, %s)
        """, (
            data['conversation_id'],
            data['role'],
            data['content'],
            json.dumps(data.get('sentiment')) if 'sentiment' in data else None
        ))
        conn.commit()
        message_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({
            'id': message_id,
            'conversation_id': data['conversation_id'],
            'created_at': datetime.datetime.now().isoformat()
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 删除对话(增强版)
@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401
    
    token = auth_header.split(' ')[1]
    
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # 验证对话是否存在且属于当前用户
        cursor.execute("""
            SELECT id FROM conversations 
            WHERE id=%s AND user_id=%s
        """, (conversation_id, user_id))
        conversation = cursor.fetchone()
        
        if not conversation:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': '对话不存在或无权访问',
                'conversation_id': conversation_id
            }), 404
            
        # 先删除关联消息(确保外键约束)
        cursor.execute("DELETE FROM messages WHERE conversation_id=%s", (conversation_id,))
        
        # 再删除对话
        cursor.execute("DELETE FROM conversations WHERE id=%s", (conversation_id,))
        
        # 验证删除是否成功
        cursor.execute("SELECT id FROM conversations WHERE id=%s", (conversation_id,))
        if cursor.fetchone():
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': '删除对话失败',
                'conversation_id': conversation_id
            }), 500
            
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '对话删除成功',
            'conversation_id': conversation_id
        }), 200
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return jsonify({
            'success': False,
            'error': str(e),
            'conversation_id': conversation_id
        }), 500

# 问答API
@app.route('/api/ask_question', methods=['POST'])
def ask_question():
    data = request.get_json()
    question = data.get('question')
    conversation_id = data.get('conversation_id')
    
    # 这里添加问答逻辑
    answer = f"这是关于'{question}'的回答"
    
    return jsonify({
        'success': True,
        'answer': answer,
        'conversation_id': conversation_id
    })

# 故事生成API (SSE流式响应)
@app.route('/api/generate_story', methods=['GET'])
def generate_story():
    age = request.args.get('age', type=int)
    theme = request.args.get('theme', '')
    requirements = request.args.get('requirements', '')
    length = request.args.get('length', type=int)
    
    def generate():
        try:
            if not app.config['COZE_API_KEY']:
                raise ValueError("未配置Coze API密钥")
                
            # 使用Coze API流式生成
            response = llm.stream(story_template.format(
                age=age,
                theme=theme,
                requirements=requirements,
                length=length
            ))
            for chunk in response:
                yield f"data: {json.dumps({'text': chunk.content})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

# 加载故事API
@app.route('/api/load_stories', methods=['GET'])
def load_stories():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM stories ORDER BY created_at DESC")
        stories = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(stories)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 情感分析API
@app.route('/api/analyze_sentiment', methods=['POST'])
def analyze_sentiment():
    if not sentiment_analyzer:
        return jsonify({'error': '情感分析模型未初始化'}), 500
        
    text = request.json.get('text')
    if not text:
        return jsonify({'error': '缺少文本内容'}), 400
        
    try:
        result = sentiment_analyzer(text)
        return jsonify({
            'sentiment': result[0]['label'],
            'score': result[0]['score']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
