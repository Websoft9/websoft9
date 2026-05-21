import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException
from src.schemas.appRuntimeInstall import RuntimeInstallRequest
from src.services.runtime_install import build_runtime_installation


def test_php_runtime_install_maps_to_php_template():
    payload = RuntimeInstallRequest(
        runtime_key="php",
        app_id="phpsite",
        version="8.3-apache",
        host_port=9011,
        domain=None,
        fallback_host="127.0.0.1",
    )

    install_payload, validation_payload = build_runtime_installation(payload)

    assert install_payload.app_name == "php"
    assert install_payload.edition.version == "8.3-apache"
    assert install_payload.settings == {
        "W9_HTTP_PORT_SET": "9011",
        "W9_HTTP_PORT": "80",
        "W9_URL": "127.0.0.1",
        "W9_NETWORK": "websoft9",
        "W9_URL_REPLACE": "true",
    }
    assert validation_payload.template_app_name == "php"
    assert validation_payload.proxy_enabled is False
    assert validation_payload.domain_names == ["127.0.0.1"]
    assert validation_payload.app_port == 80


def test_php_runtime_install_maps_to_php_fpm_nginx_template():
    payload = RuntimeInstallRequest(
        runtime_key="php",
        template_app_name="phpfpmnginx",
        app_id="phpsite",
        version="8.3-fpm",
        host_port=9011,
        domain=None,
        fallback_host="127.0.0.1",
    )

    install_payload, validation_payload = build_runtime_installation(payload)

    assert install_payload.app_name == "phpfpmnginx"
    assert install_payload.edition.version == "8.3-fpm"
    assert validation_payload.template_app_name == "phpfpmnginx"


def test_php_runtime_install_accepts_legacy_apache_version_from_product_metadata():
    payload = RuntimeInstallRequest(
        runtime_key="php",
        template_app_name="php",
        app_id="phplegacy",
        version="8.0-apache",
        host_port=9025,
        domain=None,
        fallback_host="127.0.0.1",
    )

    install_payload, validation_payload = build_runtime_installation(payload)

    assert install_payload.app_name == "php"
    assert install_payload.edition.version == "8.0-apache"
    assert validation_payload.template_app_name == "php"


def test_nodejs_runtime_requires_application_port():
    try:
        RuntimeInstallRequest(
            runtime_key="nodejs",
            app_id="nodeapp",
            version="24",
            host_port=9012,
            fallback_host="127.0.0.1",
        )
    except CustomException as exc:
        assert exc.status_code == 400
        assert exc.details == "The selected runtime requires an internal application port."
    else:
        raise AssertionError("Expected nodejs runtime install validation to require an internal application port")


def test_java_runtime_maps_to_tomcat_template():
    payload = RuntimeInstallRequest(
        runtime_key="java",
        app_id="javaapp",
        version="10-jdk21-temurin",
        host_port=8088,
        domain="java.example.com",
        fallback_host="127.0.0.1",
    )

    install_payload, validation_payload = build_runtime_installation(payload)

    assert install_payload.app_name == "tomcat"
    assert install_payload.proxy_enabled is True
    assert install_payload.domain_names == ["java.example.com"]
    assert validation_payload.runtime_label == "Java Runtime (Tomcat)"
    assert install_payload.settings == {
        "W9_HTTP_PORT_SET": "8088",
        "W9_HTTP_PORT": "8080",
        "W9_URL": "java.example.com",
        "W9_NETWORK": "websoft9",
    }


def test_runtime_install_accepts_runtime_specific_advanced_settings():
    payload = RuntimeInstallRequest(
        runtime_key="nodejs",
        app_id="nodeapp",
        version="24",
        host_port=9012,
        app_port=3000,
        runtime_url="runtime.example.internal",
        network_name="custom-network",
        url_replace=False,
        fallback_host="127.0.0.1",
    )

    install_payload, validation_payload = build_runtime_installation(payload)

    assert install_payload.settings == {
        "W9_HTTP_PORT_SET": "9012",
        "W9_HTTP_PORT": "3000",
        "W9_URL": "runtime.example.internal",
        "W9_NETWORK": "custom-network",
        "W9_URL_REPLACE": "false",
    }
    assert validation_payload.runtime_url == "runtime.example.internal"
    assert validation_payload.network_name == "custom-network"
    assert validation_payload.url_replace is False


def test_runtime_install_rejects_unsupported_version():
    payload = RuntimeInstallRequest(
        runtime_key="python",
        app_id="pyapp",
        version="3.14",
        host_port=9013,
        app_port=8080,
        fallback_host="127.0.0.1",
    )

    try:
        build_runtime_installation(payload)
    except CustomException as exc:
        assert exc.status_code == 400
        assert exc.details == "Unsupported version '3.14' for runtime 'python'."
    else:
        raise AssertionError("Expected runtime install validation to reject unsupported versions")