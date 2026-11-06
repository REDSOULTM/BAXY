using System.Diagnostics;
using System.Globalization;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// uso-108 C12, on real processes of a helper of the tests. A process that ends on a crash code is said; one that ends
/// cleanly or on another code says nothing (the launcher's control); nothing is said while one of them runs.
/// </summary>
[TestFixture]
public sealed class LaunchWatchTests
{
    private static Process Start(params string[] arguments)
    {
        var start = new ProcessStartInfo(StallingWindow.ProgramPath)
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            CreateNoWindow = true,
        };
        foreach (string argument in arguments)
            start.ArgumentList.Add(argument);
        return Process.Start(start) ?? throw new InvalidOperationException("the helper did not start");
    }

    // Reads as the opening does, one every 100 ms, up to the bound; the first code seen.
    private static async Task<uint?> ReadUntilAsync(LaunchWatch watch, int boundMs)
    {
        var bound = Stopwatch.StartNew();
        while (bound.ElapsedMilliseconds < boundMs)
        {
            if (watch.CrashCode() is { } code)
                return code;
            await Task.Delay(100);
        }

        return null;
    }

    [TestCase("C0000135", 0xC0000135u)]
    [TestCase("C0000005", 0xC0000005u)]
    public async Task AProcessThatDiedSaysItsCode(string code, uint expected)
    {
        int? started = null;
        using var watch = new LaunchWatch(() => started is { } id ? [id] : []);
        using Process process = Start("--exit", code, "400");
        started = process.Id;
        var took = Stopwatch.StartNew();

        uint? read = await ReadUntilAsync(watch, 6000);

        Assert.Multiple(() =>
        {
            Assert.That(read, Is.EqualTo(expected));
            Assert.That(took.ElapsedMilliseconds, Is.LessThan(4000));
        });
    }

    // explorer.exe ends with 1 with its window in the shell that runs; 259 is STILL_ACTIVE as a real exit code.
    [TestCase("0")]
    [TestCase("1")]
    [TestCase("103")]
    public async Task AProcessThatEndedOnAnotherCodeSaysNothing(string code)
    {
        int? started = null;
        using var watch = new LaunchWatch(() => started is { } id ? [id] : []);
        using Process process = Start("--exit", code, "200");
        started = process.Id;

        Assert.That(await ReadUntilAsync(watch, 2000), Is.Null);
    }

    // The control: a launcher ended cleanly while the process it started owns the window.
    [Test]
    public async Task ALauncherThatEndedCleanlySaysNothing()
    {
        int? started = null;
        using var watch = new LaunchWatch(() => started is { } id ? [id] : []);
        using Process launcher = Start("--launcher", "Ventana del hijo", "10", "10", "200", "200", "0", "0", "0", "BaxyVentanaDelHijo", "hold");
        started = launcher.Id;
        string line = await launcher.StandardOutput.ReadLineAsync() ?? string.Empty;
        using Process child = Process.GetProcessById(int.Parse(line, CultureInfo.InvariantCulture));
        try
        {
            uint? read = await ReadUntilAsync(watch, 2000);
            Assert.Multiple(() =>
            {
                Assert.That(launcher.HasExited, Is.True);
                Assert.That(launcher.ExitCode, Is.Zero);
                Assert.That(child.HasExited, Is.False);
                Assert.That(read, Is.Null);
            });
        }
        finally
        {
            child.Kill(entireProcessTree: false);
        }
    }

    // While another process of the launch runs (the same program's child), a crash says nothing yet.
    [Test]
    public async Task ACrashWithAProcessOfTheLaunchRunningSaysNothingYet()
    {
        var started = new List<int>();
        using var watch = new LaunchWatch(() => started);
        using Process crashed = Start("--exit", "C0000135", "100");
        using Process running = Start("--exit", "0", "1800");
        started.Add(crashed.Id);
        started.Add(running.Id);

        uint? during = await ReadUntilAsync(watch, 1500);

        Assert.That(during, Is.Null);
    }

    // A process there before the launch is not the launch's.
    [Test]
    public async Task AProcessThatWasThereBeforeTheWatchIsNotTheLaunchs()
    {
        using Process before = Start("--exit", "C0000135", "400");
        using var watch = new LaunchWatch(() => [before.Id]);

        Assert.That(await ReadUntilAsync(watch, 2000), Is.Null);
    }
}
