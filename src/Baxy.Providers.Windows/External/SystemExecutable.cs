namespace Baxy.Providers.Windows.External;

/// <summary>
/// Uso-108 (agent-desktop crates/windows/src/system/launch_live_tests.rs; Microsoft's CreateProcessW documentation, on a
/// null lpApplicationName: the application's folder and the parent's current directory are searched before the system
/// folders): a bare <c>powershell.exe</c> started by the Core runs a file of that name planted where it runs from, and
/// that process reads every screen. A bare name resolves here to its full path: the system's folder, then the absolute
/// folders of PATH (winget's alias lives in one); never the current directory nor a relative PATH entry.
/// </summary>
internal static class SystemExecutable
{
    internal static string PowerShell { get; } =
        Path.Combine(Environment.SystemDirectory, "WindowsPowerShell", "v1.0", "powershell.exe");

    /// <summary>
    /// The same file for a scheduled task's command: Task Scheduler expands the variable when the task runs, as 68 of the
    /// 75 Microsoft tasks of this machine write theirs (%windir% or %SystemRoot%; 4 name a drive), so the definition holds
    /// no machine's path. A task registered with the bare name stays as it is, and nothing reads a command back.
    /// </summary>
    internal const string PowerShellInTask = @"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe";

    /// <summary>The full path of <paramref name="executable"/>; one already with a folder stays as it is. One found
    /// nowhere names the system folder, so starting it fails as a missing file, never finding another.</summary>
    internal static string Resolve(string executable) =>
        Resolve(executable, Environment.GetEnvironmentVariable("PATH"));

    internal static string Resolve(string executable, string? searchPath)
    {
        if (Path.IsPathRooted(executable) || executable.Contains('\\') || executable.Contains('/'))
            return executable;
        if (string.Equals(executable, "powershell.exe", StringComparison.OrdinalIgnoreCase))
            return PowerShell;
        string system = Path.Combine(Environment.SystemDirectory, executable);
        if (File.Exists(system))
            return system;
        foreach (string folder in (searchPath ?? string.Empty).Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!Path.IsPathFullyQualified(folder))
                continue;
            string candidate = Path.Combine(folder, executable);
            if (File.Exists(candidate))
                return candidate;
        }

        return system;
    }
}
