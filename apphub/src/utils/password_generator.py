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
        special_symbols = "!#"                        # all special symbols

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
    
    @staticmethod
    def generate_random_string_with_rules(min_length:int=8):
        """
        Generate a random string with at least two uppercase letters, and a mix of lowercase letters and digits.

        Args:
            min_length (int, optional): Minimum length of the string. Defaults to 8.

        Returns:
            str: A random string with the specified rules.
        """
        # At least two uppercase letters
        uppercase_chars = ''.join(random.choices(string.ascii_uppercase, k=2))

        # At least one lowercase letter
        lowercase_char = random.choice(string.ascii_lowercase)

        # At least one digit
        digit_char = random.choice(string.digits)

        # Ensure the total length is met, subtract 3 for the mandatory characters
        remaining_length = max(min_length - 3, 1)  # Ensure there's room for additional characters

        # The rest can be a mix of uppercase, lowercase, and digits
        other_chars = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=remaining_length))

        # Combine and shuffle
        password_list = list(uppercase_chars + lowercase_char + digit_char + other_chars)
        random.shuffle(password_list)

        # Convert list to string
        return ''.join(password_list)
