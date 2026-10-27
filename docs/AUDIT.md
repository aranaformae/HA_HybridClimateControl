# Audit and phase report — 0.5.0-beta.1 proposal

## Baseline

Reviewed every source/configuration file and the full commit history (initial
commit through `831dcbd`, including v0.3.x climate-attribute fixes and v0.4.0
simulation additions). Repository started with no tests, CI or Options Flow.
Reviewed official Home Assistant documentation for config-entry lifecycle, Options
Flow and ClimateEntity, and exercised APIs with HA 2026.2.3 test fixtures.

## Phase 1 findings and resolution

| Finding in v0.4.0 | Severity / resolution |
| --- | --- |
| Room state change calls `_control()` while OFF, which lowers Plugwise target and disables AC | High: no physical actuation in this test build; OFF is advisory only |
| `simulation_mode` false permits real calls; old flags carry into upgrades | High: old flags cannot unlock physical control |
| Dry run still requires real AC/Plugwise availability | Virtual tests could fail before producing advice: decoupled pure planner from physical devices |
| AC mode/setpoint share a timer; setting HEAT updates timer before target check | Target may not be sent; no actuator executor retained in beta; independent acknowledgement/timers required before reintroduction |
| OFF AC commands bypass minimum run time; startup timers assume long idle | Potential cycling: no physical executor; timer design is phase-3 prerequisite |
| Stale sensor path leaves existing Plugwise demand unresolved | Cannot establish safe residual state: advice becomes unavailable, no live fallback claimed |
| Broad exception swallowing and busy flag can lose a newer request | Synchronous side-effect-free evaluation avoids overlapping command tasks |
| Options Flow absent, no options merge/update listener | Added options, reload listener, entry-owned state, unload cleanup |
| Unknown/unavailable climate state could expose cached current_temperature | Reject unavailable, nonfinite, stale and non-Celsius inputs |
| Simulated calls inconsistent with actuator timers; no persistent explanation history | Replaced with declarative advisory decisions and bounded session log |
| README out of date, incomplete translations/codeowners, no CI/tests | Updated README, EN/NL forms, manifest, HACS metadata and validation jobs |

## Phase 2 delivery

Dry Run and Virtual select, eight adjustable scenario numbers, advisory thermostat,
13 diagnostic sensors, grouped device, downloaded diagnostics, session log (50),
measured/scenario distinction, target-only restoration and OFF on mode/reload.
The original AC-first hysteresis is retained as a pure planner. Old unsafe actuator
implementation is recoverable from Git history but cannot execute in this branch.
This deliberate temporary compatibility break follows the request to validate
simulation before physical heating. Pump settings remain in old entries but do
not grant ownership. No bathroom or whole-boiler commands exist.

## Validation scope

Automated tests cover pure decision boundaries, invalid/NaN/infinite inputs,
legacy live/pump flags, dry/virtual no-call invariant, UI service entrypoints,
independent virtual operation, unavailable/non-Celsius/stale readings, re-reported
unchanged readings, log bounds, config/options/duplicate zones and reload/unload.
The test dependency pins HA 2026.2.3; this is not a claim of testing an October
2026 Home Assistant release. GitHub Hassfest/HACS results are separate CI checks.
No hardware tests, energy savings, overshoot improvement or hydraulic safety claims.

## Next gate

Run the PR checks and test manually in an HA test instance. Exercise cold room,
at/above target, lost sensor, restart and mode changes. Confirm Daikin, Plugwise,
bathroom and pump remain unchanged. Before live control, design source-specific
minimum timers, coalesced serialized actuation, state acknowledgement, capability
bounds, demand ownership/release and external safety/zone arbitration. Learned
model, energy optimization and MPC remain future phases.

Official references:
- https://developers.home-assistant.io/docs/config_entries_index/
- https://developers.home-assistant.io/docs/config_entries_options_flow_handler/
- https://developers.home-assistant.io/docs/core/entity/climate/
