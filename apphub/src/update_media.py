import schedule
import time
import os

def job():
    os.system("echo 'start to test schedule'")

schedule.every(5).seconds.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
