from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
from dotenv import load_dotenv
import requests
import json
import jwt as pyjwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
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

# 初始化数据库
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     username TEXT UNIQUE NOT NULL,
                     password TEXT NOT NULL
                 )''')
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

@app.route('/api/generate_story', methods=['POST'])
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
    if not data or 'prompt' not in data:
        return jsonify({'error': '缺少prompt参数'}), 400

    try:
        print(f"调用通义千问API生成故事(流式)，用户输入: {data['prompt']}")

        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {app.config['TONGYI_API_KEY']}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "enable"
        }

        # 使用模板格式化用户输入
        prompt_content = story_template.format(message=data['prompt'])

        payload = {
            "model": "qwen-turbo",
            "input": {
                "messages": [{
                    "role": "user",
                    "content": prompt_content
                }]
            },
            "parameters": {
                "incremental_output": True,
                "temperature": 0.8,
                "top_p": 0.9
            }
        }

        def generate():
            try:
                with requests.post(url, json=payload, headers=headers, stream=True, timeout=30) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith('data:'):
                                try:
                                    data_chunk = json.loads(decoded_line[5:])
                                    if 'output' in data_chunk and 'text' in data_chunk['output']:
                                        yield f"data: {json.dumps({'text': data_chunk['output']['text']})}\n\n"
                                except json.JSONDecodeError as e:
                                    app.logger.error(f"JSON解析错误: {str(e)}")
                                    continue
            except Exception as e:
                app.logger.error(f"流式请求过程中出错: {str(e)}")
                yield f"data: {json.dumps({'error': '故事生成中断'})}\n\n"

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

if __name__ == '__main__':
    app.run(port=5000, debug=True)