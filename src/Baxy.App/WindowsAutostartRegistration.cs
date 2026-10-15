using System.Diagnostics;
using System.IO;
using Microsoft.Win32;

namespace Baxy.App;

/// <summary>
/// HKCU Run registration that makes BAXY start with Windows. Tests inject
/// <see cref="IWindowsRunKey"/> so they never write the live Run key.
/// Only the owner's own BAXY registers (auditoría de estabilidad r19, hallazgo 5):
/// the installed binary, or the build of the owner's own checkout (the folder whose
/// <c>.git</c> is the repository itself), on the default profile. A linked git
/// worktree (its <c>.git</c> is a file), a binary anywhere else, a UI probe, the
/// conductor or a test profile (<c>BAXY_DATA_DIR</c>) never does, because at the
/// next sign-in Windows would start that binary on the default profile, load the
/// model and hold the single instance. Such a run leaves the registration of an
/// existing binary alone and removes only one that cannot start anything any more
/// (its binary is gone) or that a worktree build left behind.
/// </summary>
internal sealed class WindowsAutostartRegistration
{
    private readonly IWindowsRunKey _runKey;
    private readonly Func<string> _executablePath;
    private readonly string _installationRoot;
    private readonly string _defaultDataRoot;
    private readonly Func<string?> _configuredDataRoot;

    internal WindowsAutostartRegistration(
        IWindowsRunKey runKey,
        Func<string>? executablePath = null,
        string? installationRoot = null,
        string? defaultDataRoot = null,
        Func<string?>? configuredDataRoot = null)
    {
        _runKey = runKey ?? throw new ArgumentNullException(nameof(runKey));
        _executablePath = executablePath ?? ResolveCurrentExecutable;
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        _installationRoot = NormalizeDirectory(
            installationRoot ?? Path.Combine(localAppData, "Programs", "BAXY"));
        _defaultDataRoot = NormalizeDirectory(
            defaultDataRoot ?? Path.Combine(localAppData, "BAXY", "1"));
        _configuredDataRoot = configuredDataRoot
            ?? (static () => Environment.GetEnvironmentVariable("BAXY_DATA_DIR"));
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

    /// <summary>
    /// Registers this executable when it may own the sign-in start; otherwise
    /// writes nothing, removes only a dead or worktree entry and returns null.
    /// </summary>
    internal string? EnsureRegistered(IReadOnlyList<string> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        string executable = _executablePath();
        if (!MayRegister(executable, arguments))
        {
            string? registered = _runKey.Read(PresenceLimits.AutostartValueName);
            if (!string.IsNullOrWhiteSpace(registered) && IsStale(ExecutableOf(registered)))
            {
                _runKey.Delete(PresenceLimits.AutostartValueName);
            }

            return null;
        }

        string command = BuildCommand(executable);
        string? current = _runKey.Read(PresenceLimits.AutostartValueName);
        if (!string.Equals(current, command, StringComparison.OrdinalIgnoreCase))
        {
            _runKey.Write(PresenceLimits.AutostartValueName, command);
        }

        return command;
    }

    internal bool MayRegister(string executable, IReadOnlyList<string> arguments)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(executable);
        ArgumentNullException.ThrowIfNull(arguments);
        return LocationOf(executable) is BuildLocation.Installed or BuildLocation.OwnerCheckout
            && UsesDefaultProfile()
            && !FieldUiProbe.IsRequested(arguments)
            && !ProductConductorHost.IsRequested(arguments);
    }

    private bool UsesDefaultProfile()
    {
        string? configured = _configuredDataRoot();
        return string.IsNullOrWhiteSpace(configured)
            || string.Equals(
                NormalizeDirectory(configured),
                _defaultDataRoot,
                StringComparison.OrdinalIgnoreCase);
    }

    private bool IsUnderInstallationRoot(string? executable)
    {
        if (string.IsNullOrWhiteSpace(executable) || !Path.IsPathFullyQualified(executable))
        {
            return false;
        }

        return Path.GetFullPath(executable).StartsWith(
            _installationRoot + Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase);
    }

    // An entry nothing may keep: one whose binary is gone (or cannot be read from
    // the command), or one a worktree build wrote. The installed binary's entry is
    // the installer's to manage, and an existing binary elsewhere is not ours to judge.
    private bool IsStale(string? registeredExecutable)
    {
        if (string.IsNullOrWhiteSpace(registeredExecutable)
            || !Path.IsPathFullyQualified(registeredExecutable))
        {
            return true;
        }

        return LocationOf(registeredExecutable) switch
        {
            BuildLocation.Installed => false,
            BuildLocation.Worktree => true,
            _ => !File.Exists(registeredExecutable),
        };
    }

    private enum BuildLocation
    {
        Installed,
        OwnerCheckout,
        Worktree,
        Elsewhere,
    }

    // The nearest .git above the binary says whose build it is: a directory is the
    // repository's own checkout, a file is a linked worktree pointing back at it.
    private BuildLocation LocationOf(string executable)
    {
        if (IsUnderInstallationRoot(executable))
        {
            return BuildLocation.Installed;
        }

        if (!Path.IsPathFullyQualified(executable))
        {
            return BuildLocation.Elsewhere;
        }

        for (DirectoryInfo? directory = new FileInfo(Path.GetFullPath(executable)).Directory;
             directory is not null;
             directory = directory.Parent)
        {
            string marker = Path.Combine(directory.FullName, ".git");
            if (Directory.Exists(marker))
            {
                return BuildLocation.OwnerCheckout;
            }

            if (File.Exists(marker))
            {
                return BuildLocation.Worktree;
            }
        }

        return BuildLocation.Elsewhere;
    }

    // The executable a Run command starts: the quoted path BuildCommand writes,
    // or the command up to its first space when it carries no quotes.
    private static string? ExecutableOf(string command)
    {
        string trimmed = command.Trim();
        if (trimmed.StartsWith('"'))
        {
            int close = trimmed.IndexOf('"', 1);
            return close > 1 ? trimmed[1..close] : null;
        }

        int space = trimmed.IndexOf(' ');
        return space < 0 ? trimmed : trimmed[..space];
    }

    private static string NormalizeDirectory(string path) =>
        Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));

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
