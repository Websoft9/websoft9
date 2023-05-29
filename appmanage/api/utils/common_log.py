import logging
import os
from logging import handlers

class MyLogging():
    # init logging
    def __init__(self):
        # the file of log
        logPath = 'logs/'
        if not os.path.exists(logPath):
            os.makedirs(logPath)
        logName = 'app_manage.log'
        logFile = logPath + logName
        formatter = logging.Formatter('%(asctime)s %(levelname)s:  %(message)s')
        # handler
        time_rotating_file_handler = handlers.TimedRotatingFileHandler(filename=logFile, when="MIDNIGHT", interval=1, encoding='utf-8')
        time_rotating_file_handler.setLevel(logging.DEBUG)
        time_rotating_file_handler.setFormatter(formatter)
        # config
        logging.basicConfig(
            level= logging.DEBUG,
            handlers= [time_rotating_file_handler],
            datefmt='%Y-%m-%d %H:%M:%S',
            format='%(asctime)s %(levelname)s:  %(message)s'
        )

    def info_logger(self, content):
        logging.info(content)

    def error_logger(self, content):
        logging.error(content)

    def debug_logger(self, content):
        logging.debug(content)

    def warning_logger(self, content):
        logging.warning(content)


myLogger = MyLogging()

