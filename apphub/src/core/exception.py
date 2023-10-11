class CustomException(Exception):
    """
    Custom Exception

    Attributes:
        status_code (int): HTTP status code,default is 500
        message (str): Error message,default is "Internal Server Error"
        details (str): Error details,default is "Internal Server Error"
    """
    def __init__(self, status_code: int=500, message: str="Internal Server Error", details: str="Internal Server Error"):
        self.status_code = status_code
        self.message = message
        self.details = details
