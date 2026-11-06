using System.Diagnostics;
using System.IO;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// N3: a process the core started can keep the core's stdout open after the core is gone. The App does not wait for the end
/// of that pipe to know: the exit is told by the process itself, and stopping the sidecar is bounded.
/// </summary>
[TestFixture]
public sealed class SidecarHeldOutputTests
{
    private const string Script = """
        $s=New-Object System.Diagnostics.ProcessStartInfo 'powershell.exe','-NonInteractive -NoProfile -Command Start-Sleep -Seconds 40'
        $s.UseShellExecute=$false;$s.CreateNoWindow=$true;$s.WorkingDirectory=$env:SystemRoot
        [void][System.Diagnostics.Process]::Start($s)
        exit 65
        """;

    [Test]
    public async Task ASidecarWhoseOutputAChildHoldsIsStillSeenToExitAndStops()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-sidecar-held-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        string script = Path.Combine(folder, "core.ps1");
        await File.WriteAllTextAsync(script, Script);
        string shell = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0", "powershell.exe");
        LocalJsonlSidecarProcess sidecar = LocalJsonlSidecarProcess.Start(new LocalJsonlSidecarDefinition(
            "core", shell, folder, ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script]));
        var exited = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        sidecar.Process.Exited += (_, _) => exited.TrySetResult();
        try
        {
            if (sidecar.Process.HasExited)
                exited.TrySetResult();
            await exited.Task.WaitAsync(TimeSpan.FromSeconds(30));
            Assert.That(sidecar.Process.ExitCode, Is.EqualTo(65));

            var clock = Stopwatch.StartNew();
            await sidecar.StopAsync().WaitAsync(TimeSpan.FromSeconds(30));

            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(20)), "the held pipe does not hold the stop");
        }
        finally
        {
            await sidecar.DisposeAsync();
            Directory.Delete(folder, recursive: true);
        }
    }
}
