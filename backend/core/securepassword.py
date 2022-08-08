"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Erez Zomer  (erez@mov.ai) - 2022
"""
from curses.ascii import isascii
import hashlib
import os
import binascii
from movai_core_shared.logger import Log
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
from backend.core.vault import JWT_SECRET_KEY
from movai_core_shared.exceptions import PasswordASCIIFormatError


def password_checker(func):
    """This is function decorator for validating the password
    is in the correct type.

    Args:
        func (callable): The function to be decorated
    """
    def inner(*args, **kwargs):
        """This function is encapsulates the decorated function and
        add the validation of the password.

        Raises:
            PasswordASCIIFormatError: in case the password contains non-ASCII
            characters.

        Returns:
            callable: a decorated function.
        """
        password = args[0]
        for letter in password:
            if not isascii(letter):
                error_msg = "The supplied password is not in the ascii format."
                Log.get_logger().error(error_msg)
                raise PasswordASCIIFormatError(error_msg)
        return func(*args, **kwargs)
    return inner


class SecurePassword:
    """A class for securing password by encryption or hashing.
    """

    def __init__(self, secret: str = JWT_SECRET_KEY) -> None:
        key = urlsafe_b64encode(secret[:32].encode('ascii'))
        self.cipher_suite = Fernet(key)

    def encrypt_password(self, plain_text: str) -> bytes:
        """Encrypts the given text using the AES algorithm.

        Args:
            plain_text (str): The password to be encrypted.

        Returns:
            bytes: the cipher text of the encrypted password.
        """
        cipher_text = self.cipher_suite.encrypt(plain_text.encode('ascii'))
        return cipher_text

    def decrypt_password(self, cipher_text: bytes) -> str:
        """Decrypts the given hash using the AES algorithm.

        Args:
            cipher_text (str): The encrypted password to be decrypted.

        Returns:
            string: A plain text of the encrypted password.
        """
        plain_text = self.cipher_suite.decrypt(cipher_text)
        return plain_text.decode('ascii')

    @staticmethod
    def create_salt() -> str:
        """This function creat a random salt using SHA256 algorithm.

        Returns:
            str: a string representing the secure hash of the salt.
        """
        salt = hashlib.sha256(os.urandom(60)).hexdigest().encode("ascii")
        return salt

    @staticmethod
    def extract_salt(combined_hash: bytes):
        salt = combined_hash[:64].encode("ascii")
        return salt

    @staticmethod
    @password_checker
    def create_hash(password: str, salt: str) -> bytes:
        """This function creates a SHA256 hash of the password.

        Args:
            password (str): The password to be hashed.
            salt (str): An input parameter for the hashing algorithm which is
                reuired for maintaining uniqueness of the hash.

        Returns:
            bytes: a secure hash (message digest) of the password.
        """
        hash = binascii.hexlify(
            hashlib.pbkdf2_hmac("sha256",
                                password.encode("ascii"),
                                salt,
                                100000))
        return hash

    @staticmethod
    @password_checker
    def create_salted_hash(password: str) -> str:
        """This function uses sha256 algorithm to store a password secured.

        Args:
            password (str): the password to hash.

        Returns:
            str: the hash of the password
        """
        salt = SecurePassword.create_salt()
        pwdhash = SecurePassword.create_hash(password, salt)
        return (salt + pwdhash).decode("ascii")

    @staticmethod
    def extract_hash(combined_hash: bytes):
        hash = combined_hash[64:].encode("utf-8")
        return hash

    @staticmethod
    @password_checker
    def verify_password(password: str, combined_hash: bytes) -> bool:
        """Verify a password against an hash

        Args:
            password (str): the password of the user.
            combined_hash

        Returns:
            bool: True if password validation succeeds, False otherwise.
        """
        current_salt = SecurePassword.extract_salt(combined_hash)
        current_hash = SecurePassword.extract_hash(combined_hash)
        pwd_hash = SecurePassword.create_hash(password, current_salt)
        return pwd_hash == current_hash
