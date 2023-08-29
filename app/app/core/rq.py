# 删除错误任务
def delete_app_failedjob(job_id):
    myLogger.info_logger("delete_app_failedjob")
    failed = FailedJobRegistry(queue=q)
    failed.remove(job_id, delete_job=True)

