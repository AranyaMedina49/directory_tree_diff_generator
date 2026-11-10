# directory_tree_diff_generator

Compare two directory trees and get back structured lists of files added, removed, and modified.

```python
from directory_tree_diff_generator import diff_directories

# diff_directories walks two existing directories on disk.
# Create the directories first if they do not exist yet.
import os
os.makedirs("old_tree", exist_ok=True)
os.makedirs("new_tree", exist_ok=True)
with open("old_tree/old_file.txt", "w") as f:
    f.write("old")
with open("new_tree/new_file.txt", "w") as f:
    f.write("new")

diff = diff_directories("old_tree", "new_tree")
print(diff.added)     # ('new_file.txt',)
print(diff.removed)   # ('old_file.txt',)
print(diff.modified)  # ()
print(diff.is_empty())  # False

# Include unchanged files if you need them:
diff = diff_directories("old_tree", "new_tree", include_unchanged=True)
print(diff.unchanged)  # ()
```

## Why this exists

Tools like `diff -r` and `rsync --dry-run` are great for humans, but when you need to
programmatically decide what changed between two snapshots, parsing their output is fragile.
This library walks both trees directly and returns plain tuples of relative paths, so you can
feed the result into a deployment script, a test assertion, or a JSON response without
shelling out.

The trade-off: files are compared by SHA-256 content hash, not by size or modification time.
That makes the result deterministic and correct even when timestamps are unreliable (e.g.,
after a `git checkout`), but it means every file is read in full. For very large trees this
is slower than a metadata-only comparison. The library deliberately does not offer a
metadata-only mode, because that mode produces false positives that are hard to debug.

## Edge cases

- **Symbolic links** are not followed. A symlink is hashed by its target string. This avoids
  infinite loops and makes a symlink to `foo` compare equal to a regular file containing the
  text `foo`.
- **Empty directories** are ignored. Only regular files and symlinks are compared.
- **Unreadable files** are skipped rather than raising an error. The diff will not report them.
- **Path separators** in the output always use forward slashes, regardless of platform.
- **Missing or non-directory paths** raise `NotADirectoryError`.

## API

### `diff_directories(left, right, *, include_unchanged=False) -> DirectoryTreeDiff`

Walks `left` and `right` and returns a `DirectoryTreeDiff`. Raises `NotADirectoryError`
if either path is not an existing directory.

### `DirectoryTreeDiff`

A frozen dataclass with four tuples of relative paths: `added`, `removed`, `modified`,
and `unchanged`. All are sorted. `unchanged` is empty unless `include_unchanged=True`.

- `is_empty()` returns `True` when `added`, `removed`, and `modified` are all empty.
- `as_dict()` returns a plain dictionary with lists, suitable for `json.dumps`.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.

