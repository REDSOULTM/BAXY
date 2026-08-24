using Microsoft.Win32;

namespace Baxy.App;

/// <summary>
/// Arranque con Windows: una sola entrada en el Run del usuario actual,
/// apuntando al mismo Baxy.exe que está corriendo, con <c>--tray</c>.
/// </summary>
internal static class WindowsAutostart
{
    internal const string ValueName = "BAXY";
    internal const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
    internal const string TrayArgument = "--tray";

    internal static string CommandFor(string executable)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(executable);
        return "\"" + executable + "\" " + TrayArgument;
    }

    internal static void EnsureRegistered(string executable, string? runKeyPath = null)
    {
        string command = CommandFor(executable);
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(runKeyPath ?? RunKeyPath)
            ?? throw new InvalidOperationException("No pude abrir el arranque de Windows.");
        key.SetValue(ValueName, command, RegistryValueKind.String);
    }

    internal static string? ReadCommand(string? runKeyPath = null)
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(runKeyPath ?? RunKeyPath);
        return key?.GetValue(ValueName) as string;
    }

    internal static bool IsRegistered(string executable, string? runKeyPath = null)
    {
        string? stored = ReadCommand(runKeyPath);
        return string.Equals(stored, CommandFor(executable), StringComparison.OrdinalIgnoreCase);
    }

    internal static void Unregister(string? runKeyPath = null)
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(
            runKeyPath ?? RunKeyPath,
            writable: true);
        key?.DeleteValue(ValueName, throwOnMissingValue: false);
    }
}
