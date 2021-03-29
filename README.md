# home-assistant-qubino-wire-pilot

Home Assistant Component for Qubino Wire Pilot

## Introduction

The Qubino ZMNHJD1 is not recognized as a thermostat in Home Assistant but as a light.
The light percentage is mapped to a mode.

| Value            | Min | Max  |
| :--------------- | :-- | :--- |
| Off              | 0%  | 10%  |
| Frost protection | 11% | 20%  |
| Eco              | 21% | 30%  |
| Comfort -2       | 31% | 40%  |
| Comfort -1       | 41% | 50%  |
| Comfort          | 51% | 100% |

This component create a `climate` entity using the `light` entity.

The climate will have 2 modes :

- `heat` - splitted into 3 or 5 presets :
  - `comfort` - mapped qubino "Comfort" mode
  - `comfort-1` - mapped qubino "Comfort -1" mode (optional)
  - `comfort-2` - mapped qubino "Comfort -2" mode (optional)
  - `eco` - mapped qubino "Eco" mode
  - `away` - mapped qubino "Frost protection" mode
- `off` - mapped qubino "Off" mode :

:warning: "Comfort -1" and "Comfort -2" are not available by default because home assistant doesn't have comfort-1 and comfort-2 preset. If you want to support these modes, add `6_order: true` in your configuration.

## Configuration

| Key        | Type    | Required | Description                                            |
| :--------- | :------ | :------- | :----------------------------------------------------- |
| `platform` | string  | yes      | Platform name                                          |
| `name`     | string  | yes      | Name of the entity                                     |
| `heater`   | string  | yes      | Light entity                                           |
| `sensor`   | string  | no       | Temperature sensor (for display)                       |
| `6_order`  | boolean | no       | 6-order support (add Comfort -1 and Comfort -2 preset) |

## Example

```yaml
climate:
  - platform: qubino_wire_pilot
    name: thermostat_living_room
    heater: light.heater_living_room_dimmer
```

with 6 order

```yaml
climate:
  - platform: qubino_wire_pilot
    name: thermostat_living_room
    heater: light.heater_living_room_dimmer
    6_order: true
```

with optional sensor

```yaml
climate:
  - platform: qubino_wire_pilot
    name: thermostat_living_room
    heater: light.heater_living_room_dimmer
    sensor: sensor.temperature_living_room
```
