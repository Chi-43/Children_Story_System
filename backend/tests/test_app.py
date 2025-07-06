import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_register(client):
    """测试注册接口"""
    response = client.post('/register', json={
        'username': 'testuser',
        'password': 'testpass'
    })
    assert response.status_code in [200, 201, 400]
    assert '成功' in response.get_data(as_text=True) or '存在' in response.get_data(as_text=True)

def test_login(client):
    """测试登录接口"""
    response = client.post('/login', json={
        'username': 'testuser',
        'password': 'testpass'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert 'token' in data

def test_ai_ask(client):
    """测试AI提问接口"""
    response = client.post('/ai/ask', json={
        'question': '小猫为什么会叫？'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert 'answer' in data

def test_generate_story(client):
    """测试生成故事接口"""
    response = client.post('/ai/story', json={
        'age': 6,
        'theme': '勇敢',
        'length': 200
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert 'story' in data

def test_sentiment_analysis(client):
    """测试情感分析接口"""
    response = client.post('/ai/sentiment', json={
        'text': '今天很开心'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert 'sentiment' in data 