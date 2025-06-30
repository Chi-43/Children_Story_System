from flask import Flask, request, jsonify, Response
import json
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
        print(f"成功注册用户: {username}, ID: {user_id}")
        
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

# 故事生成API
@app.route('/api/generate_story', methods=['GET', 'POST'])
def generate_story():
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
        print(f"调用通义千问API生成故事(流式)，参数: {data}")
        
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {app.config['TONGYI_API_KEY']}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "enable"
        }
        payload = {
            "model": "qwen-turbo",
            "input": {
                "messages": [{
                    "role": "user",
                    "content": story_template.format(
                        age=data['age'],
                        theme=data['theme'],
                        requirements=data['requirements'],
                        length=data['length']
                    )
                }]
            },
            "parameters": {
                "incremental_output": True
            }
        }
        
        def generate():
            with requests.post(url, json=payload, headers=headers, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            data = json.loads(decoded_line[5:])
                            if 'output' in data and 'text' in data['output']:
                                yield f"data: {json.dumps({'text': data['output']['text']})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print(f"故事生成失败，详细错误: {str(e)}")
        app.logger.error(f"故事生成失败: {str(e)}")
        return jsonify({'error': f'故事生成失败: {str(e)}'}), 500

# 加载故事素材
@app.route('/api/load_stories', methods=['POST'])
def load_stories():
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
        text = request.json['text']
        print(f"开始情感分析: {text[:50]}...")
        
        # 文本分块处理(每块500字符)
        chunk_size = 500
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        results = []
        for chunk in chunks:
            try:
                print(f"正在分析文本块: {chunk[:50]}...")
                chunk_result = sentiment_analyzer(chunk)
                print(f"原始分析结果: {chunk_result}")
                
                # 处理返回结果
                if isinstance(chunk_result, list):
                    if len(chunk_result) > 0:
                        if isinstance(chunk_result[0], dict) and 'label' in chunk_result[0]:
                            results.extend(chunk_result)
                        elif isinstance(chunk_result[0], list):
                            results.extend([item for sublist in chunk_result for item in sublist])
            
            except Exception as e:
                print(f"分析文本块时出错: {str(e)}")
                continue
                
        if not results:
            raise ValueError("情感分析未返回有效结果")
        
        print(f"最终结果集: {results}")
            
        # 计算整体情感
        avg_scores = {}
        label_mapping = {'POS': 'POSITIVE', 'NEU': 'NEUTRAL', 'NEG': 'NEGATIVE'}
        for orig_label, mapped_label in label_mapping.items():
            scores = [r['score'] for r in results if r.get('label') == orig_label]
            avg_scores[mapped_label] = sum(scores)/len(scores) if scores else 0
            
        primary_sentiment = max(avg_scores, key=avg_scores.get)
        primary_score = avg_scores[primary_sentiment]
        
        # 生成详细建议
        recommendations = {
            'POSITIVE': '内容积极向上，适合继续阅读类似故事',
            'NEUTRAL': '内容情感中性，可以尝试更有趣的主题',
            'NEGATIVE': '检测到负面情绪，建议阅读积极内容调节心情'
        }
        
        return jsonify({
            'analysis': results,
            'primary_sentiment': primary_sentiment,
            'primary_score': primary_score,
            'recommendation': recommendations[primary_sentiment],
            'detail': f"分析了{len(chunks)}个文本块，综合评估情感为{primary_sentiment}"
        })
    except Exception as e:
        print(f"情感分析处理失败: {str(e)}")
        return jsonify({'error': f'情感分析失败: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
