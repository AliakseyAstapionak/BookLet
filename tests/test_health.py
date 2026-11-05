from main import app
from fastapi.testclient import TestClient


def test_dbhealth(client: TestClient):
    response = client.get("/dbping") 

    assert response.status_code == 200
    assert response.json() == {"ok": True} 

def test_redis(client: TestClient):
    response = client.get('/redisping')

    assert response.status_code == 200
    assert response.json() == {'success': True} 

def test_app(client: TestClient):
    response = client.get('/ping')

    assert response.status_code == 200
    assert response.json() == {'ok': True}



    