import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.app_access_manager import AppAccessManager


def test_build_candidates_supports_multi_container_and_multi_port_compose_layout():
    manager = AppAccessManager()

    containers = [
        {
            "Names": ["/gateway"],
            "Ports": [
                {"PrivatePort": 80, "PublicPort": 18080},
                {"PrivatePort": 443, "PublicPort": 18443},
                {"PrivatePort": 9001, "PublicPort": 19001},
            ],
        },
        {
            "Names": ["/app"],
            "Ports": [
                {"PrivatePort": 8080, "PublicPort": 18081},
            ],
        },
        {
            "Names": ["/redis"],
            "Ports": [
                {"PrivatePort": 6379},
            ],
        },
    ]

    candidates = manager._build_candidates(containers)

    assert [(candidate.container_name, candidate.forward_port) for candidate in candidates] == [
        ("gateway", 80),
        ("gateway", 443),
        ("gateway", 9001),
        ("app", 8080),
        ("redis", 6379),
    ]
    assert candidates[0].published_ports == ["18080:80", "18443:443", "19001:9001"]
    assert candidates[3].published_ports == ["18081:8080"]
