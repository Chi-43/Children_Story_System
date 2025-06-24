from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt as pyjwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from dotenv import load_dotenv
import requests
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import Tongyi
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from transformers import pipeline

# 加载环境变量
load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET') or 'your-secret-key'
app.config['TONGYI_API_KEY'] = os.getenv('DASHSCOPE_API_KEY')

# 初始化LangChain组件
llm = Tongyi(
    dashscope_api_key=app.config['TONGYI_API_KEY'],
    model_name="qwen-turbo",
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
    sentiment_analyzer = pipeline(
        "text-classification",
        model="bert-base-chinese",
        tokenizer="bert-base-chinese",
        device="cpu",  # 使用CPU运行
        timeout=30  # 增加超时时间
    )
except Exception as e:
    print(f"初始化情感分析模型失败: {str(e)}")
    sentiment_analyzer = None


# 初始化数据库
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    conn.commit()
    conn.close()

init_db()


# JWT工具函数
def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return pyjwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

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
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        # 先检查用户是否已存在
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if c.fetchone():
            return jsonify({
                'error': 'REGISTER_ERROR',
                'message': '用户名已存在',
                'action': 'redirect_to_login'
            }), 400
            
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                 (username, hashed_password))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        print(f"成功注册用户: {username}, ID: {user_id}")  # 添加调试日志
        
        token = create_token(user_id)
        return jsonify({'token': token, 'user_id': user_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({
            'error': 'REGISTER_ERROR',
            'message': '用户名已存在',
            'action': 'redirect_to_login'
        }), 400

# 用户登录
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    
    if not user or not check_password_hash(user[1], password):
        return jsonify({
            'error': 'LOGIN_ERROR', 
            'message': '用户名或密码错误'
        }), 401
    
    token = create_token(user[0])
    return jsonify({'token': token, 'user_id': user[0]})

# 调用通义千问API
@app.route('/api/ask', methods=['POST'])
def ask_question():
    # 验证JWT
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
        # 调用通义千问API
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


# 故事生成API
@app.route('/api/generate_story', methods=['POST'])
def generate_story():
    # 验证JWT
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
    required_fields = ['age', 'theme', 'requirements', 'length']
    if not all(field in data for field in required_fields):
        return jsonify({'error': '缺少必要参数'}), 400
    
    try:
        print(f"调用通义千问API生成故事，参数: {data}")
        result = story_chain.invoke({
            'age': data['age'],
            'theme': data['theme'],
            'requirements': data['requirements'],
            'length': data['length']
        })
        print("故事生成成功")
        return jsonify({'story': result})
    except Exception as e:
        print(f"故事生成失败，详细错误: {str(e)}")
        app.logger.error(f"故事生成失败: {str(e)}")
        return jsonify({'error': f'故事生成失败: {str(e)}'}), 500

# 加载故事素材
@app.route('/api/load_stories', methods=['POST'])
def load_stories():
    # 验证JWT
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
    
    if 'file_path' not in request.json:
        return jsonify({'error': '缺少文件路径参数'}), 400
    
    try:
        loader = TextLoader(request.json['file_path'])
        documents = loader.load()
        chunks = text_splitter.split_documents(documents)
        return jsonify({
            'chunks': [chunk.page_content for chunk in chunks],
            'count': len(chunks)
        })
    except Exception as e:
        return jsonify({'error': f'加载故事失败: {str(e)}'}), 500

# 情感分析API
@app.route('/api/analyze_sentiment', methods=['POST'])
def analyze_sentiment():
    # 验证JWT
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
    
    if 'text' not in request.json:
        return jsonify({'error': '缺少文本参数'}), 400
    
    if not sentiment_analyzer:
        return jsonify({'error': '情感分析服务暂不可用，请稍后再试'}), 503
        
    try:
        result = sentiment_analyzer(request.json['text'])
        return jsonify({
            'sentiment': result[0]['label'],
            'score': result[0]['score']
        })
    except Exception as e:
        return jsonify({'error': f'情感分析失败: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
