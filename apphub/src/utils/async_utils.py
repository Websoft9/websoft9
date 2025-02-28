# utils/async_utils.py
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

from src.core.exception import CustomException

class AsyncWrapper:
    _executor = ThreadPoolExecutor(max_workers=5)  # 全局线程池

    @classmethod
    def run_sync(
        cls,
        sync_func: Callable,
        *args,
        timeout: float = 30.0,
        **kwargs
    ) -> asyncio.Future:
        """
        将同步方法包装为异步任务
        
        :param sync_func: 需要异步化的同步方法
        :param timeout: 超时时间(秒)
        :return: 异步Future对象
        """
        loop = asyncio.get_event_loop()
        # 使用partial绑定参数
        bound_func = partial(cls._execute_sync, sync_func, *args,**kwargs)
        # 提交到线程池执行
        future = loop.run_in_executor(cls._executor, bound_func)
        # 添加超时控制
        return asyncio.wait_for(future, timeout=timeout)

    @staticmethod
    def _execute_sync(
        sync_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        实际执行同步方法并处理异常
        """
        try:
            return sync_func(*args, **kwargs)
        except CustomException as e:
            # 保留原有CustomException
            raise e
        except Exception as e:
            # 将其他异常转换为CustomException
            raise CustomException(
                status_code=500,
                message="Internal Server Error",
                details=str(e)
            )