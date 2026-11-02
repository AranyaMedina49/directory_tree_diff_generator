import os
import tempfile
import unittest
from pathlib import Path

from directory_tree_diff_generator import DirectoryTreeDiff, diff_directories


class TestDiffDirectories(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.left = self.root / "left"
        self.right = self.root / "right"
        self.left.mkdir()
        self.right.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, base: Path, rel: str, content: str) -> None:
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def test_identical_trees(self) -> None:
        self.write(self.left, "a.txt", "hello")
        self.write(self.right, "a.txt", "hello")
        diff = diff_directories(self.left, self.right)
        self.assertEqual(diff.added, ())
        self.assertEqual(diff.removed, ())
        self.assertEqual(diff.modified, ())
        self.assertTrue(diff.is_empty())

    def test_added_and_removed(self) -> None:
        self.write(self.left, "keep.txt", "same")
        self.write(self.left, "gone.txt", "bye")
        self.write(self.right, "keep.txt", "same")
        self.write(self.right, "new.txt", "hi")
        diff = diff_directories(self.left, self.right)
        self.assertEqual(diff.added, ("new.txt",))
        self.assertEqual(diff.removed, ("gone.txt",))
        self.assertEqual(diff.modified, ())

    def test_modified_content(self) -> None:
        self.write(self.left, "f.txt", "one")
        self.write(self.right, "f.txt", "two")
        diff = diff_directories(self.left, self.right)
        self.assertEqual(diff.added, ())
        self.assertEqual(diff.removed, ())
        self.assertEqual(diff.modified, ("f.txt",))

    def test_nested_paths(self) -> None:
        self.write(self.left, "a/b/c.txt", "x")
        self.write(self.right, "a/b/c.txt", "y")
        self.write(self.left, "a/b/d.txt", "keep")
        self.write(self.right, "a/b/d.txt", "keep")
        diff = diff_directories(self.left, self.right)
        self.assertEqual(diff.modified, ("a/b/c.txt",))
        self.assertEqual(diff.added, ())
        self.assertEqual(diff.removed, ())

    def test_include_unchanged(self) -> None:
        self.write(self.left, "same.txt", "same")
        self.write(self.right, "same.txt", "same")
        diff = diff_directories(self.left, self.right, include_unchanged=True)
        self.assertEqual(diff.unchanged, ("same.txt",))
        # Without the flag the tuple is empty.
        diff2 = diff_directories(self.left, self.right)
        self.assertEqual(diff2.unchanged, ())

    def test_sorted_output(self) -> None:
        for name in ["z.txt", "a.txt", "m.txt"]:
            self.write(self.left, name, "x")
        for name in ["z.txt", "a.txt", "m.txt"]:
            self.write(self.right, name, "y")
        diff = diff_directories(self.left, self.right)
        self.assertEqual(diff.modified, ("a.txt", "m.txt", "z.txt"))

    def test_not_a_directory(self) -> None:
        missing = self.root / "nope"
        with self.assertRaises(NotADirectoryError):
            diff_directories(missing, self.right)
        with self.assertRaises(NotADirectoryError):
            diff_directories(self.left, missing)

    def test_empty_directories_ignored(self) -> None:
        (self.left / "emptydir").mkdir()
        (self.right / "emptydir").mkdir()
        diff = diff_directories(self.left, self.right)
        self.assertTrue(diff.is_empty())

    def test_symlink_content(self) -> None:
        target = self.left / "target.txt"
        target.write_text("data", encoding="utf-8")
        link = self.left / "link.txt"
        os.symlink("target.txt", link)
        # Right tree has a regular file with the same content as the symlink target string.
        self.write(self.right, "link.txt", "target.txt")
        diff = diff_directories(self.left, self.right)
        # The symlink hash is of the target string, so it matches the regular file.
        self.assertEqual(diff.modified, ())

    def test_as_dict(self) -> None:
        self.write(self.left, "a.txt", "1")
        self.write(self.right, "a.txt", "2")
        self.write(self.right, "b.txt", "3")
        diff = diff_directories(self.left, self.right)
        d = diff.as_dict()
        self.assertEqual(d["added"], ["b.txt"])
        self.assertEqual(d["removed"], [])
        self.assertEqual(d["modified"], ["a.txt"])
        self.assertEqual(d["unchanged"], [])

    def test_unreadable_file_skipped(self) -> None:
        self.write(self.left, "ok.txt", "ok")
        self.write(self.right, "ok.txt", "ok")
        # Create an unreadable file on the left.
        bad = self.left / "bad.txt"
        bad.write_text("secret", encoding="utf-8")
        bad.chmod(0o000)
        try:
            diff = diff_directories(self.left, self.right)
            # The unreadable file is skipped, so it does not appear as removed.
            self.assertEqual(diff.removed, ())
            self.assertEqual(diff.modified, ())
        finally:
            bad.chmod(0o644)


if __name__ == "__main__":
    unittest.main()
