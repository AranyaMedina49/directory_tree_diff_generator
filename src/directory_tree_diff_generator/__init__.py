"""Directory Tree Diff Generator.

This package compares two directory trees and reports files added, removed,
and modified. It uses only the Python standard library.
"""

from .core import DirectoryTreeDiff, diff_directories

__all__ = ["DirectoryTreeDiff", "diff_directories"]
