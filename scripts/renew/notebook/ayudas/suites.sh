#!/usr/bin/env bash
# The 4 .NET suites and pytest of the lot candidate d7a76adf1 on the notebook.
set -u
W="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-lote"; S="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay/logs"
DOTNET="$HOME/.dotnet/dotnet.exe"; [ -x "$DOTNET" ] || DOTNET=dotnet
cd "$W" || exit 1
echo "HEAD $(git log --oneline -1 | cut -c1-40) $(date +%H:%M)"
unset BAXY_AYUDAS
for p in Kernel Contracts Setup Providers.Windows; do
  "$DOTNET" test "tests/Baxy.$p.Tests" -c Release --nologo -v q > "$S/suite-$p.log" 2>&1
  echo "$p exit $? $(date +%H:%M): $(grep -aE 'Passed!|Failed!|Correcto|Con error|Total tests|Superado|Error:' "$S/suite-$p.log" | tail -3 | tr '\n' ' ')"
done
py -3.12 -m pytest -q tests > "$S/suite-pytest.log" 2>&1
echo "pytest exit $? $(date +%H:%M): $(tail -1 "$S/suite-pytest.log")"
echo SUITES-DONE
