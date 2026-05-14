import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException
from src.schemas.appComposeInstall import ComposeValidationRequest
from src.services.compose_install import validate_compose_installation


def test_compose_validation_accepts_valid_compose():
    payload = ComposeValidationRequest(
        app_id="mycompose",
        display_name="My Compose App",
        compose_content="services:\n  web:\n    image: nginx:latest\n",
        env=[{"key": "APP_ENV", "value": "prod"}],
    )

    response = validate_compose_installation(payload)

    assert response.valid is True
    assert response.services == ["web"]
    assert response.environment_keys == ["APP_ENV"]


def test_compose_validation_rejects_invalid_yaml():
    payload = ComposeValidationRequest(
        app_id="mycompose",
        display_name="My Compose App",
        compose_content="services:\n  web: [broken\n",
        env=[],
    )

    try:
        validate_compose_installation(payload)
    except CustomException as exc:
        assert exc.status_code == 400
        assert "Compose syntax is invalid" in exc.details
    else:
        raise AssertionError("Expected compose validation to reject invalid YAML")


def test_compose_validation_requires_services():
    payload = ComposeValidationRequest(
        app_id="mycompose",
        display_name="My Compose App",
        compose_content="version: '3.9'\nnetworks:\n  default: {}\n",
        env=[],
    )

    try:
        validate_compose_installation(payload)
    except CustomException as exc:
        assert exc.status_code == 400
        assert exc.details == "Compose content must define at least one service."
    else:
        raise AssertionError("Expected compose validation to require services")
