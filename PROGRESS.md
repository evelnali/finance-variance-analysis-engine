# Progress log

One line per session: what was done, and the single next thing to do.

## 2026-09-08
- Done: M1 chunk 1-4. Toolchain installed, repo published to GitHub,
venv + pinned dependencies, first Python script running (scratch.py).
- Next: chunk 5. Write config.py to read settings.yml.

## 2026-09-09
- Done: M1 complete. config.py loads validates settings.yml, logger.py writes timestamped run log
to console and file, run.py is the entry point with --period. 
Caught a %-format bug turning 5% into 500%
- Next M2 - assumptions.yml and the driver model. 