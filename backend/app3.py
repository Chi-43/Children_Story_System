from flask import Flask, request, jsonify, Response
import json
from flask_cors import CORS
import jwt  # 统一使用 pyjwt 代替 jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
import requests
from mysql_db import get_connection
# 初始化数据库
from mysql_db import init_db
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import Tongyi
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from transformers import pipeline
import time  # 添加时间模块用于流式响应延迟

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

init_db()


# JWT工具函数 - 使用 pyjwt
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


# 调用通义千问API
@app.route('/api/ask', methods=['POST'])
def ask_question_endpoint():  # 避免与下面的函数名冲突
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401

    token = auth_header.split(' ')[1]

    try:
        # 使用 pyjwt 统一处理
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'token已过期'}), 401
    except jwt.InvalidTokenError:
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


# 对话历史API - 使用 pyjwt
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401

    token = auth_header.split(' ')[1]

    try:
        # 使用 pyjwt
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


# 获取对话详情 - 使用 pyjwt
@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401

    token = auth_header.split(' ')[1]

    try:
        # 使用 pyjwt
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


# 创建新对话 - 使用 pyjwt
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
        # 使用 pyjwt
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


# 保存消息 - 使用 pyjwt
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
        # 使用 pyjwt
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


# 删除对话(增强版) - 使用 pyjwt
@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': '未提供有效的认证token'}), 401

    token = auth_header.split(' ')[1]

    try:
        # 使用 pyjwt
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


# 删除原有的故事生成API，替换为以下修复版本
@app.route('/api/generate_story', methods=['GET'])
def generate_story():
    age = request.args.get('age', type=int)
    theme = request.args.get('theme', '')
    requirements = request.args.get('requirements', '')
    length = request.args.get('length', type=int)

    # 添加调试日志
    app.logger.info(f"收到故事生成请求: age={age}, theme={theme}, requirements={requirements}, length={length}")

    def generate():
        try:
            if not app.config['TONGYI_API_KEY']:
                error_msg = "错误: 未配置通义千问API密钥"
                app.logger.error(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 使用LangChain生成故事（一次性生成）
            response = story_chain.invoke({
                'age': age,
                'theme': theme,
                'requirements': requirements,
                'length': length
            })

            # 将故事分成句子，模拟流式输出
            # 注意：response可能是字符串，也可能是LangChain的响应对象，我们统一处理
            story_text = response if isinstance(response, str) else response.content
            sentences = story_text.split('。')

            app.logger.info(f"故事生成成功，共{len(sentences)}个句子")

            # 发送每个句子
            for sentence in sentences:
                if sentence.strip():  # 跳过空句子
                    # 每个句子作为一个事件发送
                    yield f"data: {json.dumps({'text': sentence + '。'})}\n\n"
                    time.sleep(0.05)  # 稍微延迟，模拟流式效果

            # 发送结束信号
            yield "data: [DONE]\n\n"

        except Exception as e:
            error_msg = f"生成故事失败: {str(e)}"
            app.logger.exception(error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


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
    # 配置日志
    import logging
    from logging.handlers import RotatingFileHandler

    # 创建日志目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 设置日志处理器
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=1024 * 1024 * 10,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

    app.run(debug=True, port=5000, threaded=True)