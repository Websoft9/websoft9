class FileHelper:
    """
    Helper class for file operations.

    Methods:
        read_file(file_path): Read a file and return its contents.
        write_file(file_path, content): Write given content to a file.
    """
    @staticmethod
    def read_file(file_path):
        """
        Read a file and return its contents.

        Args:
            file_path (str): The path to the file.

        Returns:
            str: The contents of the file.
        """
        
        with open(file_path, 'r') as f:
            content = f.read()
            
        return content

    @staticmethod
    def write_file(file_path, content):
        """
         Write given content to a file.

         Args:
             file_path (str): The path to the file.
             content (str): The content to be written.
         """

        with open(file_path, 'w') as f:
             f.write(content)
