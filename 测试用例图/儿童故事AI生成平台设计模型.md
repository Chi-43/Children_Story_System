# 儿童故事AI生成平台设计模型

## 1. 系统架构设计

### 1.1 分层架构设计

<img src="D:\Download\Edge\deepseek_mermaid_20250701_ac3dbd.png" alt="deepseek_mermaid_20250701_ac3dbd" style="zoom: 33%;" />

### 1.2 组件交互设计

## 2. 核心领域模型

### 2.1 类图设计

<img src="D:\Download\Edge\deepseek_mermaid_20250701_0603bc.png" alt="deepseek_mermaid_20250701_0603bc" style="zoom: 25%;" />

### 2.3 服务层设计

<img src="D:\Download\Edge\deepseek_mermaid_20250701_82170e.png" alt="deepseek_mermaid_20250701_82170e" style="zoom: 25%;" />

## 3. 关键流程设计

### 3.1 故事生成序列图

<img src="D:\Download\Edge\deepseek_mermaid_20250701_281075.png" alt="deepseek_mermaid_20250701_281075" style="zoom: 25%;" />



### 3.2 情感分析状态图

<img src="D:\Download\Edge\deepseek_mermaid_20250701_840be6.png" alt="deepseek_mermaid_20250701_840be6" style="zoom: 33%;" />

## 4. 数据库设计模型

### 4.1 实体关系图

<img src="D:\Download\Edge\deepseek_mermaid_20250701_f5301d.png" alt="deepseek_mermaid_20250701_f5301d" style="zoom: 25%;" />



### 4.2 数据字典

| 表名      | 字段          | 类型        | 描述         |
| :-------- | :------------ | :---------- | :----------- |
| users     | id            | UUID        | 用户唯一标识 |
|           | username      | VARCHAR(50) | 登录用户名   |
|           | password_hash | TEXT        | 密码哈希值   |
| stories   | id            | UUID        | 故事唯一标识 |
|           | user_id       | UUID        | 关联用户ID   |
|           | content       | TEXT        | 故事完整内容 |
|           | target_age    | INTEGER     | 目标儿童年龄 |
| materials | id            | UUID        | 素材唯一标识 |
|           | file_path     | TEXT        | 文件存储路径 |
|           | file_type     | VARCHAR(10) | 文件类型     |
| sentiment | story_id      | UUID        | 关联故事ID   |
|           | primary       | VARCHAR(10) | 主要情感倾向 |

## 5. 安全设计模型

### 5.1 认证授权矩阵

| 资源路径           | 方法 | 认证要求 | 角色权限 |
| :----------------- | :--- | :------- | :------- |
| /api/auth/register | POST | 无       | 任何用户 |
| /api/auth/login    | POST | 无       | 任何用户 |
| /api/stories       | GET  | JWT      | 普通用户 |
| /api/stories       | POST | JWT      | 普通用户 |
| /api/materials     | POST | JWT      | 普通用户 |
| /api/admin/users   | GET  | JWT+RBAC | 管理员   |

### 5.2 数据流安全

<img src="D:\Download\Edge\deepseek_mermaid_20250701_f775eb.png" alt="deepseek_mermaid_20250701_f775eb" style="zoom: 25%;" />

## 6. 部署架构设计

### 6.1 容器化部署

dockerfile

```
# 前端服务
FROM node:16 as frontend-builder
WORKDIR /app
COPY frontend/ .
RUN npm install && npm run build

# 后端服务
FROM python:3.9-slim
WORKDIR /app
COPY backend/ .
RUN pip install -r requirements.txt
COPY --from=frontend-builder /app/dist /app/static

ENV FLASK_ENV=production
EXPOSE 5000
CMD ["gunicorn", "-w 4", "-b :5000", "app:app"]
```

本设计模型完整覆盖了儿童故事AI生成平台的各个方面，从系统架构到详细实现，确保了系统的功能性、可靠性、安全性和可扩展性。