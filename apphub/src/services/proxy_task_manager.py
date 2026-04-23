import threading
import uuid
from typing import Callable, Optional

from src.core.exception import CustomException
from src.services.app_manager import AppManger
from src.services.proxy_manager import ProxyManager


class ProxyTaskManager:
    _tasks: dict[str, dict] = {}
    _lock = threading.Lock()

    def submit_create_task(
        self,
        app_id: str,
        domain_names: list[str],
        certificate_id: Optional[int],
        endpoint_id: Optional[int],
    ) -> str:
        return self._submit_task(
            lambda: AppManger().create_proxy_by_app(app_id, domain_names, endpoint_id, certificate_id)
        )

    def submit_update_task(
        self,
        proxy_id: int,
        domain_names: list[str],
        certificate_id: Optional[int],
        endpoint_id: Optional[int],
    ) -> str:
        return self._submit_task(
            lambda: AppManger().update_proxy_by_app(proxy_id, domain_names, endpoint_id, certificate_id)
        )

    def get_task(self, task_id: str) -> dict:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise CustomException(
                    status_code=404,
                    message="Not Found",
                    details=f"Proxy task:{task_id} Not Found",
                )
            return dict(task)

    def _submit_task(self, worker: Callable[[], dict]) -> str:
        task_id = str(uuid.uuid4())
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "status": "pending",
                "proxy_host": None,
                "error": None,
            }

        threading.Thread(target=self._run_task, args=(task_id, worker), daemon=True).start()
        return task_id

    def _run_task(self, task_id: str, worker: Callable[[], dict]) -> None:
        self._update_task(task_id, status="running")
        try:
            proxy_host = worker()
            self._update_task(
                task_id,
                status="completed",
                proxy_host=ProxyManager.to_proxy_host_response(proxy_host),
            )
        except CustomException as exc:
            self._update_task(task_id, status="failed", error=exc.details or exc.message)
        except Exception as exc:
            self._update_task(task_id, status="failed", error=str(exc))

    def _update_task(
        self,
        task_id: str,
        *,
        status: str,
        proxy_host: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task["status"] = status
            task["proxy_host"] = proxy_host
            task["error"] = error