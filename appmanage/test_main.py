from unittest.mock import patch

from fastapi.testclient import TestClient


from .main import app

client = TestClient(app)

# current not used, because the project layout is not right.

@patch("api.v1.routers.apps.manage")
def test_app_update_list(manage):
    manage.get_update_list.return_value = {'date': '', 'content': ''}
    response = client.get("/AppUpdateList")
    assert response.status_code == 200
