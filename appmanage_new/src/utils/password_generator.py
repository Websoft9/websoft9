import string
import random

def generate_strong_password():
    lowercase_letters = string.ascii_lowercase      # all lowercase letters
    uppercase_letters = string.ascii_uppercase      # all uppercase letters
    digits = string.digits                          # all digits
    special_symbols = "`$%()[]{},.*+-:;<>?_~/|\""   # all special symbols

    # get 4 random characters from each category
    password = [
        random.choice(lowercase_letters),
        random.choice(uppercase_letters),
        random.choice(digits),
        random.choice(special_symbols)
    ]

    # get 12 random characters from all categories
    all_characters = lowercase_letters + uppercase_letters + digits + special_symbols
    for i in range(12):  # 12 characters
        password.append(random.choice(all_characters)) # get a random character from all characters

    # shuffle the password list
    random.shuffle(password)

    # convert the list to a string
    password = ''.join(password)

    return password

if __name__ == "__main__":
    print(generate_strong_password())
