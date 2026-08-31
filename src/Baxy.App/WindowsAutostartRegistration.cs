using System.Diagnostics;
using System.IO;
using Microsoft.Win32;

namespace Baxy.App;

/// <summary>
/// HKCU Run registration that makes BAXY start with Windows. Tests inject
/// <see cref="IWindowsRunKey"/> so they never write the live Run key.
/// </summary>
internal sealed class WindowsAutostartRegistration
{
    private readonly IWindowsRunKey _runKey;
    private readonly Func<string> _executablePath;

    internal WindowsAutostartRegistration(
        IWindowsRunKey runKey,
        Func<string>? executablePath = null)
    {
        _runKey = runKey ?? throw new ArgumentNullException(nameof(runKey));
        _executablePath = executablePath ?? ResolveCurrentExecutable;
    }

    internal static WindowsAutostartRegistration CreateDefault() =>
        new(new CurrentUserRunKey());

    internal static string BuildCommand(string executablePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(executablePath);
        string full = Path.GetFullPath(executablePath);
        if (!Path.IsPathFullyQualified(full)
            || !string.Equals(
                Path.GetExtension(full),
                ".exe",
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(
                "Autostart must point at an existing BAXY executable.");
        }

        return "\"" + full + "\" " + PresenceLimits.FromWindowsStartArgument;
    }

    internal static bool IsStartHidden(IReadOnlyList<string> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        foreach (string argument in arguments)
        {
            if (string.Equals(
                    argument,
                    PresenceLimits.FromWindowsStartArgument,
                    StringComparison.OrdinalIgnoreCase)
                || string.Equals(
                    argument,
                    PresenceLimits.TrayArgument,
                    StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    internal string EnsureRegistered()
    {
        string command = BuildCommand(_executablePath());
        string? current = _runKey.Read(PresenceLimits.AutostartValueName);
        if (!string.Equals(current, command, StringComparison.OrdinalIgnoreCase))
        {
            _runKey.Write(PresenceLimits.AutostartValueName, command);
        }

        return command;
    }

    internal string? ReadRegisteredCommand() =>
        _runKey.Read(PresenceLimits.AutostartValueName);

    internal bool IsRegistered()
    {
        string? command = ReadRegisteredCommand();
        return !string.IsNullOrWhiteSpace(command)
            && string.Equals(
                command,
                BuildCommand(_executablePath()),
                StringComparison.OrdinalIgnoreCase);
    }

    internal static string ResolveCurrentExecutable()
    {
        string? processPath = Environment.ProcessPath;
        if (!string.IsNullOrWhiteSpace(processPath) && File.Exists(processPath))
        {
            return Path.GetFullPath(processPath);
        }

        using Process current = Process.GetCurrentProcess();
        string? module = current.MainModule?.FileName;
        if (string.IsNullOrWhiteSpace(module) || !File.Exists(module))
        {
            throw new InvalidOperationException("BAXY could not resolve its executable path.");
        }

        return Path.GetFullPath(module);
    }

    private sealed class CurrentUserRunKey : IWindowsRunKey
    {
        private const string RunSubKey =
            @"Software\Microsoft\Windows\CurrentVersion\Run";

        public string? Read(string name)
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(RunSubKey, writable: false);
            object? value = key?.GetValue(name);
            return value as string;
        }

        public void Write(string name, string value)
        {
            using RegistryKey key = Registry.CurrentUser.CreateSubKey(RunSubKey, writable: true)
                ?? throw new InvalidOperationException("Windows refused the HKCU Run key.");
            key.SetValue(name, value, RegistryValueKind.String);
        }

        public void Delete(string name)
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(RunSubKey, writable: true);
            key?.DeleteValue(name, throwOnMissingValue: false);
        }
    }
}
