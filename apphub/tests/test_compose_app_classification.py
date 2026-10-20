from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def classification(monkeypatch):
    from src.services import compose_app_manager

    manager = Mock()
    module = ModuleType("src.services.app_manager")
    module.AppManger = Mock(return_value=manager)
    monkeypatch.setitem(sys.modules, "src.services.app_manager", module)
    portainer = Mock()
    portainer.get_stack_by_name.return_value = {"Id": 9, "Status": 2, "GitConfig": {"URL": "fixture"}}
    portainer.get_containers_by_stack_name.return_value = []
    return SimpleNamespace(service=compose_app_manager, manager=manager, portainer=portainer)


@pytest.mark.parametrize("status", [1, 2])
@pytest.mark.parametrize("is_compose", [False, True])
def test_compose_classification_uses_shared_type_for_active_and_retained_apps(classification, status, is_compose):
    classification.portainer.get_stack_by_name.return_value["Status"] = status
    if status == 1:
        classification.portainer.get_containers_by_stack_name.return_value = [{"Names": ["/demo"], "State": "running"}]
    classification.manager.get_app_by_id.return_value = SimpleNamespace(is_compose_app=is_compose)
    assert classification.service._is_compose_app(classification.portainer, "demo", 7) is is_compose
    classification.manager.get_app_by_id.assert_called_once_with(
        "demo", 7, reconcile_stale=False, readonly_install_state=True, strict_exists=True,
    )


def test_retained_compose_app_is_accepted_without_runtime_containers(classification):
    app = SimpleNamespace(is_compose_app=True)
    classification.manager.get_app_by_id.return_value = app
    assert classification.service._require_compose_app(classification.portainer, "demo", 7) is app


def test_marketplace_rejection_is_explicit_not_an_undefined_name(classification):
    from src.core.exception import CustomException

    classification.manager.get_app_by_id.return_value = SimpleNamespace(is_compose_app=False)
    with pytest.raises(CustomException) as caught:
        classification.service._require_compose_app(classification.portainer, "demo", 7)
    assert caught.value.status_code == 400
    assert "not a custom compose" in caught.value.details


def test_type_lookup_propagates_backend_failure(classification):
    from src.core.exception import CustomException

    classification.manager.get_app_by_id.side_effect = CustomException(503, "Unavailable", "fixture dependency")
    with pytest.raises(CustomException) as caught:
        classification.service._is_compose_app(classification.portainer, "demo", 7)
    assert caught.value.status_code == 503
