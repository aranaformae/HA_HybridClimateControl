# Changelog

## 0.5.0-beta.3

- Present the controller as a service integration with one explicitly registered device.
- Display controller model/version and preserve existing device/entity identifiers.
- Group virtual input controls as Configuration and status sensors as Diagnostics.
- Test registry linkage, reload identity and registration with disabled entities.

## 0.5.0-beta.2 (proposed; simulation-only)

- Configure Frank-compatible all-in electricity/gas tariff sensors and optional future price lists.
- Validate units, numeric values, freshness and timezone-aware hourly/quarter-hour slots.
- Add estimated COP/CV efficiency options, heat-cost diagnostics and cheapest-source advice.
- Include price changes in bounded decision history; keep all physical control disabled.
- Add tests for tariff parsing, availability, costs, listener updates and no hardware calls.

## 0.5.0-beta.1 (proposed; not a stable release)

- Restrict all installations to advisory Dry Run / Virtual; old live and managed
  pump flags cannot enable hardware calls. Review upgrade notes before installing.
- Extract the AC-first hysteresis planner and shared entry-owned runtime.
- Add virtual input numbers, mode select, diagnostic sensors and bounded log.
- Add Config/Options Flow, reload/unload cleanup and EN/NL configuration strings.
- Validate finite/current/Celsius sensor data and start OFF after reload/mode change.
- Add HA fixture tests, Ruff, syntax, Hassfest and HACS workflows.
- Document audit, known limitations and prerequisites for restoring live control.
