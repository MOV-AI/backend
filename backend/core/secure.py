"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Erez Zomer  (erez@mov.ai) - 2022
"""
import secrets


def generate_secret_bytes(length: int=32) -> bytes:
    """The function generates a unique secret in bytes format,

    Args:
        length (int, optional): the length of the secret. Defaults to 32.

    Returns:
        bytes: the generated secret.
    """
    return secrets.token_bytes(length)


def generate_secret_string(length: int=32) -> bytes:
    """The function generates a unique secret in bytes format,

    Args:
        length (int, optional): the length of the secret. Defaults to 32.

    Returns:
        bytes: the generated secret.
    """
    return secrets.token_urlsafe(length)