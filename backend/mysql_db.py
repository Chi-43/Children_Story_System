import mysql.connector
from mysql.connector import pooling
import os
from dotenv import load_dotenv

# 明确指定.env文件路径
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
print(f"正在从 {env_path} 加载环境变量")
load_dotenv(env_path)

# 临时调试 - 打印环境变量
print("加载的环境变量:")
print(f"MYSQL_HOST: {os.getenv('MYSQL_HOST')}")
print(f"MYSQL_USER: {os.getenv('MYSQL_USER')}")
print(f"MYSQL_PASSWORD: {'*' * len(os.getenv('MYSQL_PASSWORD', ''))}")
print(f"MYSQL_DB: {os.getenv('MYSQL_DB')}")
print(f"MYSQL_PORT: {os.getenv('MYSQL_PORT')}")

# 数据库连接池配置
db_config = {
    "host": os.getenv('MYSQL_HOST', 'localhost'),
    "user": os.getenv('MYSQL_USER', 'root'),
    "password": os.getenv('MYSQL_PASSWORD', ''),
    "database": os.getenv('MYSQL_DB', 'kids_story'),
    "port": os.getenv('MYSQL_PORT', 3306),
    "charset": 'utf8mb4'
}

# 创建连接池
connection_pool = pooling.MySQLConnectionPool(
    pool_name="kids_story_pool",
    pool_size=5,
    **db_config
)

def get_connection():
    return connection_pool.get_connection()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 创建表
    tables = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            conversation_id INT NOT NULL,
            role ENUM('user', 'ai') NOT NULL,
            content TEXT,
            sentiment JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            INDEX idx_conversation_id (conversation_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    ]
    
    for table in tables:
        cursor.execute(table)
    
    conn.commit()
    cursor.close()
    conn.close()
