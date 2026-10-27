# HA Hybrid Climate Control — v0.3.0 (experimental)

Home Assistant custom integration for Daikin primary heating and Plugwise Adam/Emma living-room heating demand.

## Your setup
- Daikin: `climate.daikin_woonkamer_room_temperature`
- Plugwise living room: `climate.woonkamer`
- Bathroom: `climate.badkamer` (untouched)
- Floor pump: `switch.vloerverwarmingspomp`
- Room temperature: **select a real temperature sensor** (Plugwise room temperature may only be a climate attribute; if so expose it as a template sensor).

## Important: pump ownership
Default **manage_pump=false**. Existing Plugwise pump control and your existing pump overrun automation remain authoritative. The integration NEVER issues pump switch commands in this mode. Avoid two controllers writing to the same switch. The optional `manage_pump=true` mode is experimental and only starts the pump; it never switches it off automatically. Do not enable without checking the hydraulic safeguards.

## Installation
Copy `custom_components/hybrid_climate_controller` to Home Assistant `/config/custom_components/`, restart, then add Hybrid Climate Controller in Devices & Services. Start with HVAC OFF and test under supervision.

## Limitations / warnings
- No COP-based optimization, MPC or reliable floor thermal model yet.
- This is **not** a tested boiler safety controller. Plugwise and boiler protections remain independent.
- In OFF mode, the controller may lower the Plugwise living-room target; do not enable while other automations also own that setpoint.
- A stale temperature sensor cannot safely establish boiler or pump state.
- The controller must not be relied upon to manage pump overrun, freeze protection or hot-water safety.
- This release has been uploaded to GitHub but not functionally tested in Home Assistant.
