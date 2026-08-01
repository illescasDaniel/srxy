# Architecture

srxy is organized as a **hexagonal (ports & adapters)** package:

```
src/srxy/
├── domain/          # Pure models, FileQ, progress DTOs
├── ports/           # Protocol contracts (inbound + outbound)
├── application/     # Use cases, matching, SearchSession, launch
├── adapters/
│   ├── inbound/     # CLI, Textual TUI, PySide6 GUI
│   └── outbound/    # Documents, OCR, whisper, CLIP, cache, OS, worker
├── bootstrap.py     # Simple DI factories
└── __main__.py      # Entry dispatch
```

| Layer | Rule |
|-------|------|
| domain | stdlib only |
| ports | domain + `Protocol` |
| application | domain, ports, matching libs — not UI frameworks |
| adapters | concrete I/O and UIs |

Public API (`from srxy import magic_file_search, FileQ, …`) is the contract in [`src/srxy/__init__.py`](../src/srxy/__init__.py) (`__all__`). Everything under `adapters/`, `ports/`, `bootstrap`, and application UI helpers is internal. Generated reference: [api-reference.md](api-reference.md).

## Launch modes

| Mode | When |
|------|------|
| **GUI** | Default when a display and PySide6 are available |
| **TUI** | `--tui`, or fallthrough when GUI cannot start (TTY) |
| **CLI** | `--cli`, `--json`, `--format flat`, `-o`, `CI=true`, or no TTY |
