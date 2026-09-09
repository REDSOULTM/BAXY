from pathlib import Path
root = Path(__file__).resolve().parents[1]
for name in ['tests/Baxy.Integration.Tests/GpuSystemStatusHandlerTests.cs', 'tests/Baxy.Integration.Tests/SystemStatusHandlerTests.cs', 'tests/Baxy.Providers.Windows.Tests/SystemStatus/WindowsSystemStatusProviderTests.cs']:
    path = root / name
    text = path.read_text(encoding='utf-8-sig')
    text = text.replace('26100, "x64", true)', '26100, "x64", true, "Microsoft Windows 11 Pro")')
    text = text.replace('26100, "x64", false)', '26100, "x64", false, "Microsoft Windows Server 2025 Standard")')
    if 'WindowsSystemStatusProviderTests' in name:
        text = text.replace('public OperatingSystemReading ReadOperatingSystem()', 'public ValueTask<OperatingSystemReading> ReadOperatingSystemAsync(CancellationToken cancellationToken)')
        text = text.replace('return OperatingSystem;', 'return ValueTask.FromResult(OperatingSystem);')
    path.write_text(text, encoding='utf-8')
