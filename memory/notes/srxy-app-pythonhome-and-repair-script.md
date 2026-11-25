---
name: srxy-app-pythonhome-and-repair-script
description: Bake PYTHONHOME (resolved sys.base_prefix) into the Mach-O launcher; repair script uses Path(os.environ["SRXY_HOME"]) + heredoc and clean-env --help…
type: decision
date: 2026-09-10
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** In-bundle ``SrxyPython`` failed at startup (``Could not find platform independent libraries`` / prefix ``/install``) so Finder/Dock opened nothing. ``repair-prefix-gui.sh`` used ``Path($(printf '%q' "$PREFIX"))`` → ``Path(/Users/…)`` SyntaxError. Help body lacked a ScrollView; Filters sheet was oversized (520–640).
- **Decision:** Bake ``PYTHONHOME`` (resolved ``sys.base_prefix``) into the Mach-O launcher; repair script uses ``Path(os.environ["SRXY_HOME"])`` + heredoc and clean-env ``--help`` smoke; help content always in ``ScrollView``; Filters height ~340–420.
- **Rationale:** Relocating the interpreter changes argv[0]; PYTHONHOME is required. Quoting via env avoids shell/Python string bugs. ScrollView + shorter Filters match normal dialog UX.
