from fastapi.testclient import TestClient
from app.main import app

def test_website_and_assets():
    client=TestClient(app)
    assert client.get('/').status_code==200
    assert 'FlowForge AI' in client.get('/').text
    assert client.get('/static/style.css').status_code==200
    assert client.get('/health').json()=={'status':'ok'}
