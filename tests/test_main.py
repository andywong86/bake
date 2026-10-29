import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import main


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.templates = Path(main.__file__).resolve().parent / "dev"

    def bootstrap(self, **kwargs: bool) -> str:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main.bootstrap(self.project, self.templates, **kwargs)
        return output.getvalue()

    def test_copies_templates_exactly(self) -> None:
        self.bootstrap()
        destination = self.project / ".pi"
        self.assertEqual(
            {path.name for path in destination.iterdir()}, set(main.TEMPLATE_FILES)
        )
        for filename in main.TEMPLATE_FILES:
            self.assertEqual(
                (destination / filename).read_bytes(),
                (self.templates / filename).read_bytes(),
            )

    def test_conflict_aborts_without_writing_any_files(self) -> None:
        destination = self.project / ".pi"
        destination.mkdir()
        settings = destination / "settings.json"
        settings.write_text('{"theme": "dark"}', encoding="utf-8")
        memory = destination / "mcp-server-memory.jsonl"
        memory.write_text("existing memory", encoding="utf-8")
        before = {path.name: path.read_bytes() for path in destination.iterdir()}
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                with self.assertRaisesRegex(ValueError, "Conflicting files; no files written"):
                    self.bootstrap(dry_run=dry_run)
                self.assertEqual(
                    {path.name: path.read_bytes() for path in destination.iterdir()},
                    before,
                )

    def test_identical_file_allows_missing_files_to_be_added(self) -> None:
        destination = self.project / ".pi"
        destination.mkdir()
        settings = destination / "settings.json"
        settings.write_bytes((self.templates / "settings.json").read_bytes())
        modified = settings.stat().st_mtime_ns
        self.assertIn("Skipping identical file:", self.bootstrap())
        self.assertEqual(settings.stat().st_mtime_ns, modified)
        self.assertTrue((destination / "mcp.json").is_file())

    def test_all_conflicts_reported(self) -> None:
        destination = self.project / ".pi"
        destination.mkdir()
        for filename in main.TEMPLATE_FILES:
            (destination / filename).write_text("custom", encoding="utf-8")
        with self.assertRaises(ValueError) as raised:
            self.bootstrap()
        for filename in main.TEMPLATE_FILES:
            self.assertIn(str(destination / filename), str(raised.exception))
            self.assertEqual((destination / filename).read_text(), "custom")

    def test_cli_conflict_exits_without_writes(self) -> None:
        destination = self.project / ".pi"
        destination.mkdir()
        (destination / "settings.json").write_text("custom", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(Path(main.__file__).resolve()), "-C", str(self.project)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Conflicting files; no files written", result.stderr)
        self.assertEqual({path.name for path in destination.iterdir()}, {"settings.json"})

    def test_force_overwrites_templates_only(self) -> None:
        self.bootstrap()
        destination = self.project / ".pi"
        settings = destination / "settings.json"
        settings.write_text("custom", encoding="utf-8")
        unrelated = destination / "custom.txt"
        unrelated.write_text("keep", encoding="utf-8")
        self.assertIn("Overwrite:", self.bootstrap(force=True))
        self.assertEqual(
            settings.read_bytes(), (self.templates / "settings.json").read_bytes()
        )
        self.assertEqual(unrelated.read_text(), "keep")

    def test_dry_run_creates_nothing(self) -> None:
        self.assertIn("Would create:", self.bootstrap(dry_run=True))
        self.assertFalse((self.project / ".pi").exists())

    def test_force_dry_run_does_not_overwrite(self) -> None:
        self.bootstrap()
        settings = self.project / ".pi" / "settings.json"
        settings.write_text("custom", encoding="utf-8")
        self.assertIn("Would overwrite:", self.bootstrap(force=True, dry_run=True))
        self.assertEqual(settings.read_text(), "custom")

    def test_missing_project_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Project directory does not exist"):
            main.bootstrap(self.root / "missing", self.templates)

    def test_missing_template_fails_before_writes(self) -> None:
        templates = self.root / "incomplete"
        templates.mkdir()
        (templates / main.TEMPLATE_FILES[0]).write_text("test", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Template file does not exist"):
            main.bootstrap(self.project, templates)
        self.assertFalse((self.project / ".pi").exists())

    def test_destination_file_rejected(self) -> None:
        (self.project / ".pi").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Destination is not a directory"):
            self.bootstrap()

    def test_destination_directory_conflict_preflight(self) -> None:
        destination = self.project / ".pi"
        destination.mkdir()
        (destination / "settings.json").mkdir()
        with self.assertRaisesRegex(ValueError, "Destination is not a file"):
            self.bootstrap(force=True)
        self.assertFalse((destination / "APPEND_SYSTEM.md").exists())

    def test_symlink_pi_directory_rejected(self) -> None:
        (self.project / ".pi").symlink_to(self.templates, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Refusing symlink destination"):
            self.bootstrap(force=True)

    def test_symlink_file_rejected(self) -> None:
        destination = self.project / ".pi"
        destination.mkdir()
        external = self.root / "external"
        external.write_text("keep", encoding="utf-8")
        (destination / "settings.json").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "Refusing symlink destination"):
            self.bootstrap(force=True)
        self.assertEqual(external.read_text(), "keep")
        self.assertFalse((destination / "APPEND_SYSTEM.md").exists())

    def test_cli_from_another_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, str(Path(main.__file__).resolve()),
             "-C", str(self.project), "-t", "dev"],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / ".pi" / "mcp.json").is_file())

    def test_cli_default_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, str(Path(main.__file__).resolve()), "--dry-run"],
            cwd=self.project, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.project / ".pi"), result.stdout)
        self.assertFalse((self.project / ".pi").exists())

    def test_cli_invalid_type(self) -> None:
        result = subprocess.run(
            [sys.executable, str(Path(main.__file__).resolve()), "-t", "unknown"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)

    def test_cli_missing_project(self) -> None:
        result = subprocess.run(
            [sys.executable, str(Path(main.__file__).resolve()),
             "-C", str(self.root / "missing")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Project directory does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
