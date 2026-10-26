using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The window's start (src/Baxy.App/ShellStartupSequence.cs): the view, the engine and the --ui-probe check.</summary>
[TestFixture]
public sealed class ShellStartupSequenceTests
{
    // Revisión de calidad (2026-10-25): the probe is what ends a --ui-probe run (its finally exits BAXY); a view that failed
    // to start never ran it, and the run stayed in the tray holding the single-instance mutex, its launcher waiting.
    [Test]
    public void AViewThatFailedToStartStillRunsTheProbeThatEndsTheRun()
    {
        bool probed = false;
        Assert.ThrowsAsync<InvalidOperationException>(() => ShellStartupSequence.RunAsync(
            static () => Task.CompletedTask,
            static () => throw new InvalidOperationException("WebView2"),
            () =>
            {
                probed = true;
                return Task.CompletedTask;
            }));

        Assert.That(probed, Is.True);
    }

    [Test]
    public async Task AViewThatStartedRunsTheProbeOnce()
    {
        int probes = 0;
        await ShellStartupSequence.RunAsync(
            static () => Task.CompletedTask,
            static () => Task.CompletedTask,
            () =>
            {
                probes++;
                return Task.CompletedTask;
            });

        Assert.That(probes, Is.EqualTo(1));
    }
}
