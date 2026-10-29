"""Bootstrap project-local Pi configuration from bundled templates."""

import argparse
import shutil
from pathlib import Path


TEMPLATE_TYPES = {"dev": "Development settings with Git and memory MCP servers"}
TEMPLATE_FILES = ("APPEND_SYSTEM.md", "mcp.json", "settings.json")


def template_files(template_dir: Path) -> list[Path]:
    """List required config files and optional skill files without following links."""
    files = [Path(filename) for filename in TEMPLATE_FILES]

    def collect(directory: Path) -> None:
        for source in sorted(directory.iterdir()):
            if source.is_symlink():
                raise ValueError(f"Refusing symlink template: {source}")
            if source.is_dir():
                collect(source)
            elif source.is_file():
                files.append(source.relative_to(template_dir))
            else:
                raise ValueError(f"Template is not a regular file: {source}")

    skills = template_dir / "skills"
    if skills.is_symlink():
        raise ValueError(f"Refusing symlink template: {skills}")
    if skills.exists():
        if not skills.is_dir():
            raise ValueError(f"Template is not a directory: {skills}")
        collect(skills)
    return files


def bootstrap(
    project_dir: Path,
    template_dir: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """Copy Pi templates only after checking every destination for conflicts."""
    project_dir = project_dir.expanduser().resolve()
    template_dir = template_dir.resolve()
    if not project_dir.is_dir():
        raise ValueError(f"Project directory does not exist: {project_dir}")

    destination = project_dir / ".pi"
    if destination.is_symlink():
        raise ValueError(f"Refusing symlink destination: {destination}")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Destination is not a directory: {destination}")
    if destination.resolve() == template_dir:
        raise ValueError("Destination cannot be the template directory")

    # Validate every path and collect conflicts before writing anything.
    files = template_files(template_dir)
    conflicts: list[Path] = []
    for filename in files:
        source = template_dir / filename
        target = destination / filename
        if source.is_symlink():
            raise ValueError(f"Refusing symlink template: {source}")
        if not source.is_file():
            raise ValueError(f"Template file does not exist: {source}")
        parent = destination
        for part in filename.parts[:-1]:
            parent = parent / part
            if parent.is_symlink():
                raise ValueError(f"Refusing symlink destination: {parent}")
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"Destination is not a directory: {parent}")
        if target.is_symlink():
            raise ValueError(f"Refusing symlink destination: {target}")
        if target.exists() and not target.is_file():
            raise ValueError(f"Destination is not a file: {target}")
        if target.exists() and not force and target.read_bytes() != source.read_bytes():
            conflicts.append(target)

    if conflicts:
        paths = "\n".join(f"  {path}" for path in conflicts)
        raise ValueError(
            f"Conflicting files; no files written:\n{paths}\n"
            "Use --force to overwrite."
        )

    if not dry_run:
        destination.mkdir(exist_ok=True)

    for filename in files:
        source = template_dir / filename
        target = destination / filename
        if target.exists() and not force:
            print(f"Skipping identical file: {target}")
            continue
        action = "Overwrite" if target.exists() else "Create"
        if dry_run:
            print(f"Would {action.lower()}: {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            print(f"{action}: {target}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap Pi files in an existing project's .pi directory."
    )
    parser.add_argument(
        "--directory", "-C", type=Path, default=Path.cwd(),
        help="Existing project directory (default: current directory)",
    )
    parser.add_argument(
        "--type", "-t", dest="template_type", choices=TEMPLATE_TYPES, default="dev",
        help="Template type (default: dev)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing template files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing files"
    )
    args = parser.parse_args()
    template_dir = Path(__file__).resolve().parent / args.template_type
    try:
        bootstrap(
            args.directory, template_dir, force=args.force, dry_run=args.dry_run
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
