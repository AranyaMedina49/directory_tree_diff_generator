"""Core implementation of the directory tree diff generator.

This module walks two directory trees, computes SHA-256 hashes of file contents,
and classifies each relative path as added, removed, or modified.

Design decisions:
- Files are compared by content hash, not by mtime or size, so the result is
  deterministic and independent of filesystem timestamps.
- Symbolic links are not followed; a symlink is treated as a file whose content
  is the link target string. This avoids cycles and keeps traversal bounded.
- Empty directories are ignored; only regular files (and symlinks) are compared.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class DirectoryTreeDiff:
    """Structured result of comparing two directory trees.

    Attributes:
        added: Relative paths present only in the right tree.
        removed: Relative paths present only in the left tree.
        modified: Relative paths present in both trees with different content.
        unchanged: Relative paths present in both trees with identical content.
    """

    added: Tuple[str, ...] = ()
    removed: Tuple[str, ...] = ()
    modified: Tuple[str, ...] = ()
    unchanged: Tuple[str, ...] = ()

    def is_empty(self) -> bool:
        """Return True if there are no differences (added, removed, modified)."""
        return not (self.added or self.removed or self.modified)

    def as_dict(self) -> Dict[str, List[str]]:
        """Return a plain dict suitable for JSON serialization."""
        return {
            "added": list(self.added),
            "removed": list(self.removed),
            "modified": list(self.modified),
            "unchanged": list(self.unchanged),
        }


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's content.

    Symlinks are hashed by their target string so that a symlink to a file
    with the same content is not reported as modified just because the link
    target differs. This is a deliberate choice: the diff is about content,
    not about link topology.
    """
    h = hashlib.sha256()
    if path.is_symlink():
        target = os.readlink(path)
        h.update(target.encode("utf-8", "surrogateescape"))
        return h.hexdigest()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk_files(root: Path) -> Dict[str, str]:
    """Walk *root* and return a mapping of relative path -> content hash.

    Only regular files and symlinks are included. Directories are not entries.
    The relative path uses forward slashes regardless of platform.
    """
    result: Dict[str, str] = {}
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Sort for deterministic traversal order.
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            try:
                result[rel] = _hash_file(full)
            except OSError:
                # Unreadable files are skipped rather than crashing the diff.
                continue
    return result


def diff_directories(
    left: os.PathLike | str,
    right: os.PathLike | str,
    *,
    include_unchanged: bool = False,
) -> DirectoryTreeDiff:
    """Compare two directory trees and return a :class:`DirectoryTreeDiff`.

    Args:
        left: Path to the reference directory.
        right: Path to the directory to compare against.
        include_unchanged: If True, the ``unchanged`` tuple is populated.
            Default is False to keep the common case small.

    Returns:
        A ``DirectoryTreeDiff`` with sorted tuples of relative paths.

    Raises:
        NotADirectoryError: If either path does not exist or is not a directory.
    """
    left_path = Path(left)
    right_path = Path(right)

    if not left_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {left_path}")
    if not right_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {right_path}")

    left_files = _walk_files(left_path)
    right_files = _walk_files(right_path)

    left_keys = set(left_files)
    right_keys = set(right_files)

    added = sorted(right_keys - left_keys)
    removed = sorted(left_keys - right_keys)
    common = left_keys & right_keys

    modified: List[str] = []
    unchanged: List[str] = []
    for rel in sorted(common):
        if left_files[rel] != right_files[rel]:
            modified.append(rel)
        else:
            unchanged.append(rel)

    return DirectoryTreeDiff(
        added=tuple(added),
        removed=tuple(removed),
        modified=tuple(modified),
        unchanged=tuple(unchanged) if include_unchanged else (),
    )
