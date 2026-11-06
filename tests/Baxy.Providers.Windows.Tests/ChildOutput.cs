using System.Diagnostics;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// What a test's child process wrote, within a limit. N3 (the suite stopped once with no CPU, 2026-11-04):
/// <c>process.StandardOutput.ReadToEnd()</c> returns only when every holder of the pipe has closed it, so the
/// <c>WaitForExit(60_000)</c> after it never ran for a script stuck on a window that does not answer, or for a grandchild
/// that inherited the pipe and outlived its parent. A child past the limit ends with its tree and fails its own test.
/// </summary>
internal static class ChildOutput
{
    // The longest test of the suite takes 14 s on a loaded PC (2026-11-04), and a stuck one must end before vstest's
    // own hang detection (tests/hang.runsettings) aborts the whole run.
    internal static readonly TimeSpan Limit = TimeSpan.FromMinutes(2);

    internal static string Read(Process process) => Read(process, Limit);

    internal static string Read(Process process, TimeSpan limit)
    {
        ArgumentNullException.ThrowIfNull(process);
        Task<string> reading = process.StandardOutput.ReadToEndAsync();
        if (reading.Wait(limit))
            return reading.Result;
        bool exited = process.HasExited;
        if (!exited)
            process.Kill(entireProcessTree: true);
        Assert.Fail(exited
            ? $"the child exited, but a process it started still holds its output after {limit.TotalSeconds:0} s"
            : $"the child did not end within {limit.TotalSeconds:0} s");
        return string.Empty;
    }
}
