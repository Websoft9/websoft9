class CommandException(Exception):
    def __init__(self, code, message, detail):
        self.code = code
        self.message = message
        self.detail = detail