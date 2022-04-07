"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020

   Root module for all REST API apps
"""

from .iwebapp import IWebApp, WebAppManager

__all__ = ["IWebApp", "WebAppManager"]
# import sub modules
# these submodules need the two classes above declared before being imported
# consider importing those 2 classes from an external file (need naming)
