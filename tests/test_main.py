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
        files = main.template_files(self.templates)
        self.assertEqual(
            {path.relative_to(destination) for path in destination.rglob("*")
             if path.is_file()}, set(files)
        )
        for filename in files:
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

    def use_nested_templates(self) -> Path:
        templates = self.root / "templates"
        templates.mkdir()
        for filename in main.TEMPLATE_FILES:
            (templates / filename).write_bytes((self.templates / filename).read_bytes())
        self.templates = templates
        relative = Path("skills/example/assets/nested/data.bin")
        source = templates / relative
        source.parent.mkdir(parents=True)
        source.write_bytes(b"\x00\xffasset")
        skill = templates / "skills/example/SKILL.md"
        skill.write_text("---\nname: example\ndescription: Example workflow.\n---\n", encoding="utf-8")
        return relative

    def test_nested_skills_copied_exactly_and_identical_files_skipped(self) -> None:
        relative = self.use_nested_templates()
        self.bootstrap()
        target = self.project / ".pi" / relative
        self.assertEqual(target.read_bytes(), b"\x00\xffasset")
        modified = target.stat().st_mtime_ns
        self.assertIn("Skipping identical file:", self.bootstrap())
        self.assertEqual(target.stat().st_mtime_ns, modified)

    def test_nested_skill_conflicts_abort_before_config_writes(self) -> None:
        relative = self.use_nested_templates()
        target = self.project / ".pi" / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(b"custom")
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                with self.assertRaisesRegex(ValueError, "Conflicting files; no files written"):
                    self.bootstrap(dry_run=dry_run)
                self.assertEqual(target.read_bytes(), b"custom")
                self.assertFalse((self.project / ".pi/settings.json").exists())

    def test_force_preserves_unrelated_skills_and_extra_files(self) -> None:
        relative = self.use_nested_templates()
        self.bootstrap()
        destination = self.project / ".pi"
        target = destination / relative
        target.write_bytes(b"custom")
        extras = [destination / "skills/other/SKILL.md",
                  destination / "skills/example/custom.txt"]
        for extra in extras:
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("keep", encoding="utf-8")
        self.bootstrap(force=True, dry_run=True)
        self.assertEqual(target.read_bytes(), b"custom")
        self.bootstrap(force=True)
        self.assertEqual(target.read_bytes(), b"\x00\xffasset")
        for extra in extras:
            self.assertEqual(extra.read_text(), "keep")

    def test_nested_dry_run_creates_nothing(self) -> None:
        relative = self.use_nested_templates()
        self.assertIn(str(relative), self.bootstrap(dry_run=True))
        self.assertFalse((self.project / ".pi").exists())

    def test_skill_destination_symlinks_rejected(self) -> None:
        relative = self.use_nested_templates()
        destination = self.project / ".pi"
        external = self.root / "external"
        external.mkdir()
        # Cover every parent component, a file link, and a dangling link.
        for linked in [Path("skills"), Path("skills/example"),
                       Path("skills/example/assets"),
                       Path("skills/example/assets/nested"), relative]:
            for dangling in (False, True):
                with self.subTest(linked=linked, dangling=dangling):
                    target = destination / linked
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(self.root / "missing" if dangling else external)
                    for force in (False, True):
                        with self.assertRaisesRegex(ValueError, "Refusing symlink destination"):
                            self.bootstrap(force=force)
                    target.unlink()
                    self.assertFalse((destination / "settings.json").exists())
        self.assertEqual(list(external.iterdir()), [])

    def test_skill_parent_file_and_target_directory_rejected(self) -> None:
        relative = self.use_nested_templates()
        destination = self.project / ".pi"
        destination.mkdir()
        parent = destination / "skills"
        parent.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Destination is not a directory"):
            self.bootstrap(force=True)
        parent.unlink()
        (destination / relative).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "Destination is not a file"):
            self.bootstrap(force=True)
        self.assertFalse((destination / "settings.json").exists())

    def test_source_skill_symlinks_rejected(self) -> None:
        self.use_nested_templates()
        external = self.root / "external"
        external.mkdir()
        for relative in [Path("skills"), Path("skills/link"), Path("skills/link.md")]:
            with self.subTest(relative=relative):
                link = self.templates / relative
                if relative == Path("skills"):
                    link.rename(self.templates / "saved-skills")
                link.symlink_to(external)
                with self.assertRaisesRegex(ValueError, "Refusing symlink template"):
                    self.bootstrap(force=True)
                self.assertFalse((self.project / ".pi").exists())
                link.unlink()
                if relative == Path("skills"):
                    (self.templates / "saved-skills").rename(link)

    def test_templates_without_skills_supported(self) -> None:
        self.use_nested_templates()
        (self.templates / "skills").rename(self.templates / "unused-skills")
        self.bootstrap()
        self.assertFalse((self.project / ".pi/skills").exists())

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
