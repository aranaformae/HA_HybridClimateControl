# Changelog

## 0.5.0-beta.1 (proposed; not a stable release)

- Restrict all installations to advisory Dry Run / Virtual; old live and managed
  pump flags cannot enable hardware calls. Review upgrade notes before installing.
- Extract the AC-first hysteresis planner and shared entry-owned runtime.
- Add virtual input numbers, mode select, diagnostic sensors and bounded log.
- Add Config/Options Flow, reload/unload cleanup and EN/NL configuration strings.
- Validate finite/current/Celsius sensor data and start OFF after reload/mode change.
- Add HA fixture tests, Ruff, syntax, Hassfest and HACS workflows.
- Document audit, known limitations and prerequisites for restoring live control.
