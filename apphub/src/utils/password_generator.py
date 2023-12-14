import string
import random

class PasswordGenerator:
    """
    A class that generates a strong password.
    """
    @staticmethod
    def generate_strong_password(length:int=16):
        lowercase_letters = string.ascii_lowercase      # all lowercase letters
        uppercase_letters = string.ascii_uppercase      # all uppercase letters
        digits = string.digits                          # all digits
        special_symbols = "[]*+?~"                      # all special symbols

        # get 4 random characters from each category
        password = [
            random.choice(lowercase_letters),
            random.choice(uppercase_letters),
            random.choice(digits),
            random.choice(special_symbols)
        ]

        # get random characters from all categories
        all_characters = lowercase_letters + uppercase_letters + digits + special_symbols
        for i in range(length-4):
            password.append(random.choice(all_characters)) # get a random character from all characters

        # shuffle the password list
        random.shuffle(password)

        # convert the list to a string
        password = ''.join(password)

        return password


    @staticmethod
    def generate_random_string(length:int=8):
        """
        Generate a weak password.

        Args:
            length (int, optional): Length of the password. Defaults to 8.

        Returns:
            str: A weak password.
        """
        characters = string.ascii_lowercase + string.digits
        return ''.join(random.choice(characters) for _ in range(length))