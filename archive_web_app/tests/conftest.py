"""
Make the archive_web_app package importable from the tests directory.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
