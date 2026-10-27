# HA Hybrid Climate Control

Experimental Home Assistant integration for a Daikin air-to-air heat pump and
Plugwise-controlled boiler/floor heating. **0.5.0-beta.1 is simulation-only.** It
cannot control physical heating, even if an older entry has
`simulation_mode: false` or `manage_pump: true`.

## Installation / HACS

Requires Home Assistant 2026.2 or later. Add
`https://github.com/aranaformae/HA_HybridClimateControl` as a custom **Integration**
repository in HACS. For development, select the development branch or a published
prerelease if available. A PR alone does not create a HACS release. Alternatively
copy `custom_components/hybrid_climate_controller` into `/config/custom_components/`,
restart HA and add **Hybrid Climate Controller** under Devices & Services.
Do not treat the proposed beta manifest version as an already published release.

## Configuration

Select a Celsius temperature sensor or climate entity; climate inputs use
`current_temperature`. Suggested installation:

| Setting | Entity |
| --- | --- |
| Room reference | `climate.woonkamer` (Plugwise) |
| Airco | `climate.daikin_woonkamer_room_temperature` |
| CV living-room zone | `climate.woonkamer` |
| Pump (informational, optional) | `switch.vloerverwarmingspomp` |
| Bathroom (independent, optional) | `climate.badkamer` |

These are UI configuration examples, not YAML configuration. The integration has
Config Flow and Options Flow; edit settings using **Configure** without removing
the integration. Options reload the entry. Existing version-4 entries remain
readable. Legacy pump and simulation flags are retained in entry data but cannot
enable physical control. Thermostat and measured-room sensor unique IDs remain
unchanged. New installations default to Dry Run and OFF.

## Safe simulation

- **dry_run**: reads the real room temperature and computes advisory decisions.
- **virtual**: uses scenario temperature and target, without needing connected devices.
- Change mode with the simulation-mode select. Mode changes reset advisory HEAT
  to OFF. Select HEAT on the virtual thermostat to start calculating heat demand.
- Adjust eight virtual number entities: room/outdoor/target temperatures,
  temperature trend, electricity price, gas price, COP and remaining floor heat.
- Only room temperature and target influence decisions in this phase. The other
  numbers are recorded scenario inputs for later model/energy work.
- Thermostat target is restored; enabled state is never restored. Virtual scenario
  numbers and mode changes are session-local and reset on reload to configuration
  defaults. Decision history is session-local too.

No climate or switch service calls, direct device calls, EMS access, pump control
or boiler blocking exist in this build. Existing Plugwise regulation, bathroom,
pump overrides and overrun automations remain in charge. The controller does not
provide freeze protection or keep heating running during a Home Assistant outage.
Installing this beta **stops the integration's former live-control functionality**;
it does not clear setpoints previously written by v0.4.0. Check those separately
in Plugwise/Daikin before upgrading a system that used live control.

## Diagnostics and decision log

One device groups the thermostat, numbers, select and diagnostic sensors:
active advisory source, temperature deficit, relative demand proxy (not kW),
proposed Daikin/Plugwise setpoints, simulated CV request, mode, status and reason.
Measured room temperature stays separate from virtual temperature. Trend and floor
heat are scenario values in Virtual and unknown in Dry Run; no measured or learned
estimate is invented. A decision-log sensor exposes up to 50 timestamped entries,
including scenario inputs, source, targets and reason in its `entries` attribute.
Changes to inputs or decisions create entries; identical periodic evaluations do
not flood history. Diagnostics download is available through Devices & Services.

Proposed setpoints are **intent**, not actuator feedback or proof of boiler activity.
They are not yet checked against a physical device's limits and must not be copied
into a live actuator without validation.

## Current algorithm and limitations

The retained baseline is AC-first hysteresis. CV advice starts at the configured
deficit (default 1 °C) and persists until the deficit falls to 0.35 °C. AC advice
starts above 0.25 °C deficit and persists until 0.15 °C above target. Proposed AC
target is target + 0.5 °C, limited to 16–25 °C. This does not fix real Daikin
overshoot yet: it is a reproducible baseline for evaluating a replacement strategy.
Missing, unavailable, invalid, nonfinite, non-Celsius or older-than-20-minute room
data produces no heating recommendation. Fresh identical reports are accepted.

Minimum run/off timers, actuator acknowledgement, device availability fallback,
capability/range checks and safe demand withdrawal must be validated before live
control returns. There is no proven thermal model, learning, weather forecast,
dynamic-tariff integration, economic selection or MPC. A simulated CV request never
means the boiler is running. Energy inputs use EUR/kWh electricity, EUR/m³ gas and
dimensionless COP. Future cost comparison uses electricity/COP versus
`gas / (9.77 × boiler_efficiency)`; fixed charges must not enter marginal costs.

## Development and validation

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
```

Tests use actual Home Assistant fixtures (HA 2026.2.3, Python 3.13), service
entrypoints, reload/unload and invalid-input scenarios. GitHub Actions also runs
Hassfest and HACS validation. Those external checks must pass before a release is
published. No stable release is created automatically. Hardware behavior and newer
HA versions need separate validation. See [audit and phase report](docs/AUDIT.md).

## Roadmap

1. Stabilization and safe simulation: this PR; complete CI and supervised HA testing.
2. Validate safe actuator arbitration, minimum switching times, independent zone
   behavior and device-specific capability checks before restoring live control.
3. Strategies: automatic, AC priority, comfort, economics and manual source selection.
4. Measured trends, floor inertia and conservative learning with confidence gates.
5. Frank tariffs, Ecowitt solar/outdoor inputs and weather forecasts, COP/cost model.
6. Optional MPC only after model validation; retain a conservative fallback.
