---
name: weather
description: Current weather and forecasts via wttr.in — no API key needed
triggers: [weather, clima, tiempo, temperatura, lluvia, pronóstico, forecast, rain, sunny, temperature]
requires: {bins: [curl]}
emoji: ☔
source: builtin
---
# Weather Skill

Use `curl` to query wttr.in. No API key required.

## Current weather
```
curl "wttr.in/Santiago?format=3"
```
Returns: `Santiago, Chile: ⛅  +18°C`

## Full forecast (3 days)
```
curl "wttr.in/Santiago?format=v2"
```

## One-line for any city
```
curl "wttr.in/Madrid?format=%l:+%c+%t+%h+%w"
```
Fields: %l=location, %c=icon, %t=temp, %h=humidity, %w=wind

## JSON output
```
curl "wttr.in/Santiago?format=j1"
```

## Tips
- City names with spaces: use + or %20: `wttr.in/New+York`
- Can also use coordinates: `wttr.in/-33.45,-70.67`
- Always run via run_command with args ["curl", "wttr.in/<city>?format=3"]
