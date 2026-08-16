---
name: winget-update
description: Update all installed Windows apps via winget in one command
triggers: [actualizar, update, upgrade, apps, programas, winget, actualizaciones, windows update apps]
requires: {bins: [winget]}
emoji: 🔄
source: builtin
---
# Winget Update Skill

Use winget to manage and update Windows apps.

## Update everything (non-interactive)
```
winget upgrade --all --accept-source-agreements --accept-package-agreements
```

## List available updates
```
winget upgrade
```

## Update specific app
```
winget upgrade "Google Chrome"
winget upgrade --id Google.Chrome
```

## Install an app
```
winget install "Visual Studio Code"
winget install --id Microsoft.VisualStudioCode
```

## Search for apps
```
winget search "discord"
```

## Uninstall
```
winget uninstall "App Name"
```

## Tips
- Run via run_command with args: ["winget", "upgrade", "--all", "--accept-source-agreements", "--accept-package-agreements"]
- timeout should be 120+ seconds for full upgrades
- Use --source winget to restrict to the main repo
