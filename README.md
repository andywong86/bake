# Bake

Bootstrap project-local Pi configuration from bundled templates. Python 3.10+
and standard library only; no package installation required.

## Usage

Run from your project directory:

```bash
python3 /path/to/bake/main.py
```

Or choose an existing project directory, similar to `create/main.py -C`:

```bash
uv run /path/to/bake/main.py -C /path/to/project --type dev
```

Preview without writing:

```bash
python3 /path/to/bake/main.py -C /path/to/project --dry-run
```

All template destinations are checked before any files are written. If any
existing file differs from its template, the entire operation aborts and lists
conflicts, including with `--dry-run`. Identical files are skipped; missing files
are added only when there are no conflicts. Files are never merged.

To explicitly override this conflict check and replace matching files:

```bash
python3 /path/to/bake/main.py -C /path/to/project --force
```

Only template files are replaced; unrelated files, memories, and sessions remain
untouched. Symlink destinations are rejected. Project directory must already exist.

## Dev template

Copies these files unchanged from `dev/` into the project's `.pi/` directory:

| File | Purpose |
| --- | --- |
| `APPEND_SYSTEM.md` | Instructions for using the memory MCP server |
| `mcp.json` | Git MCP server via `uvx`; memory MCP server via `npx` |
| `settings.json` | Store sessions in `.pi/sessions` |

Unlike `create`, Bake does not create a project, initialize Git, install
dependencies, or start Pi/MCP servers. Templates remain unchanged.

Start Pi from the project root after bootstrapping. Grant project trust when
prompted so Pi can load project instructions and MCP servers. For an existing
session, run `/reload`. MCP servers need `uvx` and `npx` available; first use
may download their packages. The memory path uses `${PWD}`, so start Pi from
the project root with `PWD` set correctly.

Consider ignoring these runtime files in the project's `.gitignore`:

```gitignore
.pi/sessions/
.pi/mcp-server-memory.jsonl
```

Bake does not edit `.gitignore`. Memory and sessions may contain private data.

## Tests

```bash
cd /path/to/bake
python3 -m unittest discover -s tests -v
```
