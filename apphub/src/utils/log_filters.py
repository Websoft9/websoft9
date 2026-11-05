import logging
import re


class IgnoreSpecificRequestsFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        return not re.search(r"GET\s+/api/apps\s", message)
