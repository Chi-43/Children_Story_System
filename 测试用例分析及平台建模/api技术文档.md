# 儿童心理分析与故事生成系统 API 文档

## 1. 用户认证模块

### 1.1 用户注册
- **路径**: `/api/register`
- **方法**: POST
- **请求头**: `Content-Type: application/json`
- **请求参数**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **响应**:
  ```json
  {
    "token": "string",
    "user_id": "int"
  }
  ```
- **说明**: 注册新用户并返回JWT token
- **代码片段**:
  ```python
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
  ```

### 1.2 用户登录
- **路径**: `/api/login`
- **方法**: POST
- **请求头**: `Content-Type: application/json`
- **请求参数**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **响应**:
  ```json
  {
    "token": "string",
    "user_id": "int"
  }
  ```
- **说明**: 用户登录并获取JWT token
- **代码片段**:
  ```python
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
  ```

## 2. 故事生成模块

### 2.1 生成故事(流式)
- **路径**: `/api/generate_story`
- **方法**: POST
- **请求头**: 
  - `Content-Type: application/json`
  - `Authorization: Bearer <token>`
- **请求参数**:
  ```json
  {
    "prompt": "string"
  }
  ```
- **响应**: 流式响应(SSE)
- **说明**: 根据用户输入生成儿童故事，使用流式响应
- **代码片段**:
  ```python
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

    # 获取请求数据
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({'error': '缺少prompt参数'}), 400

    # 保存用户输入
    save_chat_message(user_id, 'user', data['prompt'])

    # 使用RAG检索相关素材
    try:
        rag_docs = rag.search(data['prompt']) if rag else []
        context = "\n---\n".join([d.page_content for d in rag_docs])

        # 构建增强提示词
        enhanced_prompt = f"{story_template}\n\n相关素材参考:\n{context}".format(
            message=data['prompt']
        )
    except Exception as e:
        # RAG检索失败时回退到原始提示词
        enhanced_prompt = story_template.format(message=data['prompt'])
        app.logger.error(f"RAG检索失败: {str(e)}")

    # 准备API请求
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-SSE": "enable"
    }
    payload = {
        "model": "qwen-turbo",
        "input": {
            "messages": [{
                "role": "user",
                "content": enhanced_prompt
            }]
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
            with requests.post(DASHSCOPE_API_URL, json=payload, headers=headers, stream=True, timeout=30) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            try:
                                data_chunk = json.loads(decoded_line[5:])
                                if 'output' in data_chunk and 'text' in data_chunk['output']:
                                    text = data_chunk['output']['text']
                                    result_buffer.append(text)
                                    yield f"data: {json.dumps({'text': text})}\n\n"
                            except (json.JSONDecodeError, KeyError) as e:
                                app.logger.error(f"流数据解析错误: {str(e)}")
                                continue
        except Exception as e:
            app.logger.error(f"流式请求失败: {str(e)}")
            yield f"data: {json.dumps({'error': '故事生成中断'})}\n\n"

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
  ```

### 2.2 获取故事历史
- **路径**: `/api/story_history`
- **方法**: GET
- **请求头**: `Authorization: Bearer <token>`
- **响应**:
  ```json
  [
    {
      "id": "int",
      "input_prompt": "string",
      "thinking": "string",
      "story": "string",
      "timestamp": "datetime"
    }
  ]
  ```
- **说明**: 获取用户生成的故事历史记录
- **代码片段**:
  ```python
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
  ```

## 3. 聊天记录模块

### 3.1 保存聊天消息
- **路径**: `/api/save_chat`
- **方法**: POST
- **请求头**: 
  - `Content-Type: application/json`
  - `Authorization: Bearer <token>`
- **请求参数**:
  ```json
  {
    "content": "string",
    "role": "string",
    "conversation_id": "int"
  }
  ```
- **响应**:
  ```json
  {
    "id": "int",
    "message": "string"
  }
  ```
- **说明**: 保存用户聊天消息
- **代码片段**:
  ```python
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
                  VALUES (%s, %s, %s, %s) \
                  """
            params = (user_id, data['role'], data['content'], conversation_id)
        else:
            sql = """
                  INSERT INTO chat_history
                      (user_id, role, content)
                  VALUES (%s, %s, %s) \
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
  ```

### 3.2 获取聊天历史
- **路径**: `/api/chat_history`
- **方法**: GET
- **请求头**: `Authorization: Bearer <token>`
- **响应**:
  ```json
  [
    {
      "id": "int",
      "role": "string",
      "content": "string",
      "timestamp": "datetime"
    }
  ]
  ```
- **说明**: 获取用户聊天历史记录
- **代码片段**:
  ```python
  @app.route('/api/chat_history', methods=['GET'])
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
  ```

## 4. 情感分析模块

### 4.1 情感分析
- **路径**: `/api/analyze_sentiment2`
- **方法**: POST
- **请求头**: 
  - `Content-Type: application/json`
  - `Authorization: Bearer <token>`
- **请求参数**:
  ```json
  {
    "messages": [
      {
        "role": "string",
        "content": "string",
        "timestamp": "datetime"
      }
    ]
  }
  ```
- **响应**:
  ```json
  {
    "overall": {
      "label": "string",
      "score": "float",
      "recommendation": "string"
    },
    "daily": [
      {
        "date": "string",
        "label": "string",
        "score": "float"
      }
    ],
    "samples": [
      {
        "content": "string",
        "sentiment": {
          "label": "string",
          "score": "float"
        }
      }
    ]
  }
  ```
- **说明**: 分析对话中的情感倾向
- **代码片段**:
  ```python
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
  ```

## 5. 系统状态模块

### 5.1 RAG状态
- **路径**: `/api/rag_status`
- **方法**: GET
- **响应**:
  ```json
  {
    "status": "string",
    "chunk_count": "int",
    "file_count": "int"
  }
  ```
- **说明**: 获取RAG系统状态
- **代码片段**:
  ```python
  @app.route('/api/rag_status', methods=['GET'])
  def rag_status():
      return jsonify(rag.get_status())
  ```

### 5.2 数据库状态
- **路径**: `/api/db_status`
- **方法**: GET
- **响应**:
  ```json
  {
    "status": "string",
    "pool_size": "int",
    "active_connections": "int"
  }
  ```
- **说明**: 获取数据库连接池状态
- **代码片段**:
  ```python
  @app.route('/api/db_status', methods=['GET'])
  def db_status():
      return jsonify({
          'status': 'healthy',
          'pool_size': connection_pool.pool_size
      })
  ```

## 技术说明

1. **认证机制**: 所有API(除注册/登录)都需要在请求头中添加`Authorization: Bearer <token>`
2. **数据库**: 使用MySQL连接池管理数据库连接
3. **AI服务**: 集成阿里云通义千问API进行故事生成和情感分析
4. **RAG系统**: 使用Chroma向量数据库和BM25混合检索
5. **流式响应**: 故事生成API使用Server-Sent Events(SSE)实现流式响应
