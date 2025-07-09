# 儿童故事AI生成平台数据建模文档

## 1. 数据模型概述

本项目采用关系型数据模型，基于SQLite数据库实现。数据模型设计遵循第三范式(3NF)，确保数据完整性和最小冗余。主要实体包括用户、故事生成记录、素材库和情感分析结果等。

## 2. 核心实体关系图

<img src="C:\Users\27852\Desktop\deepseek_mermaid_20250701_8eac50.png" style="zoom:25%;" />



## 3. 详细数据表设计

### 3.1 用户表 (users)

| 字段名        | 类型     | 约束                      | 描述         |
| :------------ | :------- | :------------------------ | :----------- |
| id            | INTEGER  | PRIMARY KEY AUTOINCREMENT | 用户唯一标识 |
| username      | TEXT     | UNIQUE NOT NULL           | 用户名(唯一) |
| password_hash | TEXT     | NOT NULL                  | 密码哈希值   |
| created_at    | DATETIME | DEFAULT CURRENT_TIMESTAMP | 账户创建时间 |
| last_login    | DATETIME | NULL                      | 最后登录时间 |

**索引**:

- 唯一索引: username

### 3.2 故事记录表 (stories)

| 字段名       | 类型     | 约束                             | 描述         |
| :----------- | :------- | :------------------------------- | :----------- |
| id           | INTEGER  | PRIMARY KEY AUTOINCREMENT        | 故事唯一标识 |
| user_id      | INTEGER  | FOREIGN KEY REFERENCES users(id) | 关联用户ID   |
| title        | TEXT     | NULL                             | 故事标题     |
| target_age   | INTEGER  | NOT NULL                         | 目标儿童年龄 |
| theme        | TEXT     | NOT NULL                         | 故事主题     |
| requirements | TEXT     | NOT NULL                         | 用户特殊要求 |
| length       | INTEGER  | NOT NULL                         | 故事长度(字) |
| created_at   | DATETIME | DEFAULT CURRENT_TIMESTAMP        | 创建时间     |
| full_content | TEXT     | NOT NULL                         | 完整故事内容 |
| ai_model     | TEXT     | DEFAULT 'qwen-turbo'             | 使用的AI模型 |

**索引**:

- 普通索引: user_id
- 普通索引: created_at

### 3.3 故事素材表 (story_materials)

| 字段名      | 类型     | 约束                             | 描述                |
| :---------- | :------- | :------------------------------- | :------------------ |
| id          | INTEGER  | PRIMARY KEY AUTOINCREMENT        | 素材唯一标识        |
| name        | TEXT     | NOT NULL                         | 素材名称            |
| file_path   | TEXT     | NOT NULL                         | 文件存储路径        |
| file_type   | TEXT     | NOT NULL                         | 文件类型(txt/pdf等) |
| uploaded_at | DATETIME | DEFAULT CURRENT_TIMESTAMP        | 上传时间            |
| uploader_id | INTEGER  | FOREIGN KEY REFERENCES users(id) | 上传用户ID          |
| is_public   | BOOLEAN  | DEFAULT 0                        | 是否公开素材        |

**索引**:

- 普通索引: uploader_id
- 普通索引: is_public

### 3.4 情感分析结果表 (sentiment_analyses)

| 字段名            | 类型     | 约束                             | 描述         |
| :---------------- | :------- | :------------------------------- | :----------- |
| id                | INTEGER  | PRIMARY KEY AUTOINCREMENT        | 分析记录ID   |
| user_id           | INTEGER  | FOREIGN KEY REFERENCES users(id) | 关联用户ID   |
| analyzed_text     | TEXT     | NOT NULL                         | 被分析文本   |
| primary_sentiment | TEXT     | NOT NULL                         | 主要情感倾向 |
| positive_score    | REAL     | NOT NULL                         | 积极情感得分 |
| neutral_score     | REAL     | NOT NULL                         | 中性情感得分 |
| negative_score    | REAL     | NOT NULL                         | 消极情感得分 |
| analyzed_at       | DATETIME | DEFAULT CURRENT_TIMESTAMP        | 分析时间     |
| recommendation    | TEXT     | NULL                             | 系统建议     |

**索引**:

- 普通索引: user_id
- 普通索引: analyzed_at

### 3.5 系统日志表 (system_logs)

| 字段名     | 类型     | 约束                      | 描述                      |
| :--------- | :------- | :------------------------ | :------------------------ |
| id         | INTEGER  | PRIMARY KEY AUTOINCREMENT | 日志ID                    |
| level      | TEXT     | NOT NULL                  | 日志级别(INFO/WARN/ERROR) |
| module     | TEXT     | NOT NULL                  | 模块名称                  |
| message    | TEXT     | NOT NULL                  | 日志内容                  |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 记录时间                  |
| user_id    | INTEGER  | NULL                      | 关联用户ID                |
| request_id | TEXT     | NULL                      | 请求跟踪ID                |

**索引**:

- 普通索引: created_at
- 普通索引: level

## 4. 数据库初始化SQL

sql

```
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

-- 故事记录表
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT,
    target_age INTEGER NOT NULL,
    theme TEXT NOT NULL,
    requirements TEXT NOT NULL,
    length INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    full_content TEXT NOT NULL,
    ai_model TEXT DEFAULT 'qwen-turbo',
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 故事素材表
CREATE TABLE IF NOT EXISTS story_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    uploader_id INTEGER NOT NULL,
    is_public BOOLEAN DEFAULT 0,
    FOREIGN KEY (uploader_id) REFERENCES users(id)
);

-- 情感分析结果表
CREATE TABLE IF NOT EXISTS sentiment_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    analyzed_text TEXT NOT NULL,
    primary_sentiment TEXT NOT NULL,
    positive_score REAL NOT NULL,
    neutral_score REAL NOT NULL,
    negative_score REAL NOT NULL,
    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    recommendation TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 系统日志表
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    module TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    request_id TEXT
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_stories_user ON stories(user_id);
CREATE INDEX IF NOT EXISTS idx_stories_created ON stories(created_at);
CREATE INDEX IF NOT EXISTS idx_materials_uploader ON story_materials(uploader_id);
CREATE INDEX IF NOT EXISTS idx_sentiments_user ON sentiment_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs(created_at);
```

## 5. 数据访问层设计

### 5.1 用户模块

python

```
class UserRepository:
    @staticmethod
    def create_user(username: str, password: str) -> User:
        """创建新用户并返回用户对象"""
        hashed_pw = generate_password_hash(password)
        conn = sqlite3.connect('database.db')
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hashed_pw)
            )
            user_id = cursor.lastrowid
            conn.commit()
            return User(id=user_id, username=username)
        except sqlite3.IntegrityError:
            raise ValueError("用户名已存在")
        finally:
            conn.close()

    @staticmethod
    def get_user_by_credentials(username: str, password: str) -> Optional[User]:
        """验证用户凭证并返回用户对象"""
        conn = sqlite3.connect('database.db')
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            if row and check_password_hash(row[1], password):
                return User(id=row[0], username=username)
            return None
        finally:
            conn.close()
```

### 5.2 故事管理模块

python

```
class StoryRepository:
    @staticmethod
    def save_story_generation(
        user_id: int,
        params: dict,
        content: str
    ) -> StoryRecord:
        """保存故事生成记录"""
        conn = sqlite3.connect('database.db')
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO stories 
                (user_id, target_age, theme, requirements, length, full_content)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    params['age'],
                    params['theme'],
                    params['requirements'],
                    params['length'],
                    content
                )
            )
            story_id = cursor.lastrowid
            conn.commit()
            return StoryRecord(id=story_id, user_id=user_id, content=content)
        finally:
            conn.close()

    @staticmethod
    def get_user_stories(user_id: int, limit: int = 10) -> List[StoryRecord]:
        """获取用户最近生成的故事列表"""
        conn = sqlite3.connect('database.db')
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, target_age, theme, created_at 
                FROM stories 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?""",
                (user_id, limit)
            )
            return [
                StoryRecord(
                    id=row[0],
                    user_id=user_id,
                    target_age=row[1],
                    theme=row[2],
                    created_at=row[3]
                ) for row in cursor.fetchall()
            ]
        finally:
            conn.close()
```

## 6. 数据模型验证

### 6.1 Pydantic模型示例

python

```
from pydantic import BaseModel, validator

class StoryGenerationParams(BaseModel):
    age: int
    theme: str
    requirements: str
    length: int
    
    @validator('age')
    def validate_age(cls, v):
        if not 3 <= v <= 12:
            raise ValueError('目标年龄应在3-12岁之间')
        return v
        
    @validator('length')
    def validate_length(cls, v):
        if not 100 <= v <= 1000:
            raise ValueError('故事长度应在100-1000字之间')
        return v

class SentimentAnalysisResult(BaseModel):
    primary_sentiment: str
    positive_score: float
    neutral_score: float
    negative_score: float
    
    @validator('primary_sentiment')
    def validate_sentiment(cls, v):
        if v not in ['POSITIVE', 'NEUTRAL', 'NEGATIVE']:
            raise ValueError('无效的情感类型')
        return v
```

## 7. 数据迁移策略

### 7.1 版本控制

使用Alembic进行数据库迁移管理：

text

```
migrations/
├── versions/
│   ├── 001_initial_schema.py
│   └── 002_add_ai_model_field.py
└── env.py
```

### 7.2 示例迁移脚本

python

```
# 002_add_ai_model_field.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('stories', 
        sa.Column('ai_model', sa.String(), nullable=False, server_default='qwen-turbo')
    
def downgrade():
    op.drop_column('stories', 'ai_model')
```

## 8. 性能优化建议

1. **查询优化**：
   - 对常用查询条件建立适当索引
   - 对大文本字段(content)考虑分表存储
2. **缓存策略**：
   - 对热门故事内容使用Redis缓存
   - 实现查询结果缓存机制
3. **连接管理**：
   - 使用连接池管理数据库连接
   - 实现连接健康检查机制
4. **归档策略**：
   - 对历史数据实现自动归档
   - 建立冷热数据分离存储机制