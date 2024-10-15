import logging
import re

class IgnoreSpecificRequestsFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        if re.search(r"GET\s+/api/apps\s", message):
            return False
        return True
