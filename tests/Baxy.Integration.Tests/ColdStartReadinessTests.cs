using System.Diagnostics;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Core;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Salud del arranque (ronda 19b, auditoría estab2 #2, #3 y #6): el saludo del
/// core no espera lo que no necesita, la muestra de presencia no ocupa el hilo
/// de la ventana y la traza marca «lista» cuando ocurre.
/// </summary>
[TestFixture]
public sealed class ColdStartReadinessTests
{
    [Test]
    public void TheHelloCatalogWaitFitsInsideTheAppHelloTimeout()
    {
        // Margin for the runtime's own start, the journal check and the write.
        Assert.That(
            CoreStartupBudget.HelloCatalogWait + TimeSpan.FromSeconds(3),
            Is.LessThanOrEqualTo(CoreStartupBudget.HelloTimeout));
    }

    [Test]
    public async Task AStuckCatalogReadDoesNotHoldTheHelloPastItsBudget()
    {
        var stuck = new TaskCompletionSource<InstalledApplicationCatalogSnapshot>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var timer = Stopwatch.StartNew();
        InstalledApplicationCatalogSnapshot snapshot = await HelloCatalogWait.WithinAsync(
            stuck.Task,
            CoreStartupBudget.HelloCatalogWait - TimeSpan.FromMilliseconds(200),
            CancellationToken.None);
        timer.Stop();

        Assert.Multiple(() =>
        {
            Assert.That(timer.Elapsed, Is.LessThan(TimeSpan.FromSeconds(3)));
            Assert.That(snapshot.Verified, Is.False);
            Assert.That(snapshot.Complete, Is.False);
            Assert.That(snapshot.Names, Is.Empty);
        });
        stuck.SetException(new InvalidOperationException("late failure stays observed"));
    }

    [Test]
    public async Task ACatalogAlreadyReadIsCarriedEvenPastTheBudget()
    {
        var read = Task.FromResult(new InstalledApplicationCatalogSnapshot(true, true, ["Notas"]));
        InstalledApplicationCatalogSnapshot snapshot = await HelloCatalogWait.WithinAsync(
            read,
            TimeSpan.FromSeconds(30),
            CancellationToken.None);

        Assert.That(snapshot.Verified, Is.True);
        Assert.That(snapshot.Names, Is.EqualTo(new[] { "Notas" }));
    }

    [Test]
    public async Task ACatalogThatAnswersInTimeIsWaitedFor()
    {
        var read = Task.Run(async () =>
        {
            await Task.Delay(300);
            return new InstalledApplicationCatalogSnapshot(true, true, ["Notas"]);
        });
        InstalledApplicationCatalogSnapshot snapshot = await HelloCatalogWait.WithinAsync(
            read,
            TimeSpan.Zero,
            CancellationToken.None);

        Assert.That(snapshot.Verified, Is.True);
    }

    [Test]
    public void TheHelloJournalWaitFitsInsideTheAppHelloTimeout()
    {
        Assert.That(
            CoreStartupBudget.HelloJournalWait + TimeSpan.FromSeconds(3),
            Is.LessThanOrEqualTo(CoreStartupBudget.HelloTimeout));
    }

    [Test]
    public async Task AJournalStillValidatingDoesNotHoldTheHelloPastItsBudget()
    {
        // 2026-10-09: 33 MB live + 50 MB sealed took 7.5 to 19.5 s to validate under
        // load, and every start missed the App's 10 s hello budget.
        var validating = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var timer = Stopwatch.StartNew();
        await HelloJournalWait.WithinAsync(
            validating.Task,
            CoreStartupBudget.HelloJournalWait - TimeSpan.FromMilliseconds(200),
            CancellationToken.None);
        timer.Stop();

        Assert.Multiple(() =>
        {
            Assert.That(timer.Elapsed, Is.LessThan(TimeSpan.FromSeconds(3)));
            Assert.That(validating.Task.IsCompleted, Is.False);
        });
        validating.SetResult();
    }

    [Test]
    public void AJournalThatFailsWithinTheBudgetStopsTheStartBeforeTheHello()
    {
        Task failing = Task.Run(async () =>
        {
            await Task.Delay(200);
            throw new Baxy.Kernel.Journal.JournalIntegrityException("tampered");
        });

        Assert.That(
            async () => await HelloJournalWait.WithinAsync(failing, TimeSpan.Zero, CancellationToken.None),
            Throws.InstanceOf<Baxy.Kernel.Journal.JournalIntegrityException>());
    }

    [Test]
    public async Task AJournalThatOpensInTimeIsWaitedFor()
    {
        Task opening = Task.Delay(300);
        await HelloJournalWait.WithinAsync(opening, TimeSpan.Zero, CancellationToken.None);

        Assert.That(opening.IsCompletedSuccessfully, Is.True);
    }

    [Test]
    public async Task ABlockedProcessReadDoesNotHoldTheCaller()
    {
        using var release = new ManualResetEventSlim(false);
        var sampler = new PresenceIdleSampler(new BlockingReader(release));
        var timer = Stopwatch.StartNew();
        Task<PresenceIdleSnapshot> capture = sampler.CaptureAsync(true, true, true, null, "ready");
        timer.Stop();

        Assert.That(timer.Elapsed, Is.LessThan(TimeSpan.FromSeconds(1)));
        Assert.That(capture.IsCompleted, Is.False);
        release.Set();
        PresenceIdleSnapshot snapshot = await capture.WaitAsync(TimeSpan.FromSeconds(10));
        Assert.That(snapshot.Processes, Has.Count.EqualTo(1));
        Assert.That(sampler.Samples, Has.Count.EqualTo(1));
    }

    [Test]
    public void TheStartupVocabularyMarksCoreAndMindReadiness()
    {
        Assert.That(
            ShellTraceStages.All,
            Is.SupersetOf(new[]
            {
                ShellTraceStages.StartupCoreReady,
                ShellTraceStages.StartupMindVerified,
                ShellTraceStages.StartupMindReady,
            }));
    }

    [Test]
    [NonParallelizable]
    public async Task AProbeRunsAfterTheFieldIsReadyAndNeverDelaysStartupReady()
    {
        string path = Path.Combine(Path.GetTempPath(), "baxy-startup-trace-" + Guid.NewGuid().ToString("N") + ".jsonl");
        try
        {
            var probeFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            Task? sequence = null;
            using (ShellTrace? trace = ShellTrace.TryCreate(path))
            using (ShellTraceSink.Use(trace!))
            {
                sequence = ShellStartupSequence.RunAsync(
                    startShell: async () => await Task.Delay(100),
                    initializeField: async () => await Task.Delay(20),
                    probe: async () =>
                    {
                        ShellTraceSink.Record(ShellTraceScopes.Turn, "t1", ShellTraceStages.SubmitReceived);
                        await probeFinish.Task;
                        ShellTraceSink.Record(ShellTraceScopes.Turn, "t1", ShellTraceStages.ResponseFinal);
                    });
                await WaitForStageAsync(path, ShellTraceStages.StartupReady);
                Assert.That(sequence.IsCompleted, Is.False, "the sequence still awaits the probe");
                probeFinish.SetResult();
                await sequence.WaitAsync(TimeSpan.FromSeconds(10));
            }

            string[] stages = Stages(path);
            Assert.That(stages, Is.EqualTo(new[]
            {
                ShellTraceStages.StartupShellBegin,
                ShellTraceStages.StartupFieldBegin,
                ShellTraceStages.StartupFieldReady,
                ShellTraceStages.SubmitReceived,
                ShellTraceStages.StartupShellReady,
                ShellTraceStages.StartupReady,
                ShellTraceStages.ResponseFinal,
            }));
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Test]
    public void AFieldFailureStillWaitsForTheShellAndRunsNoProbe()
    {
        bool probed = false;
        Assert.ThrowsAsync<InvalidOperationException>(() => ShellStartupSequence.RunAsync(
            startShell: () => Task.CompletedTask,
            initializeField: () => Task.FromException(new InvalidOperationException("field")),
            probe: () =>
            {
                probed = true;
                return Task.CompletedTask;
            }));
        Assert.That(probed, Is.False);
    }

    private static async Task WaitForStageAsync(string path, string stage)
    {
        var deadline = Stopwatch.StartNew();
        while (!Stages(path).Contains(stage))
        {
            Assert.That(deadline.Elapsed, Is.LessThan(TimeSpan.FromSeconds(10)), stage);
            await Task.Delay(20);
        }
    }

    private static string[] Stages(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd()
            .Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(static line => (string?)JsonNode.Parse(line)!["stage"] ?? string.Empty)
            .ToArray();
    }

    private sealed class BlockingReader(ManualResetEventSlim release) : IPresenceProcessReader
    {
        public IReadOnlyList<PresenceProcessSample> ReadOwned()
        {
            release.Wait(TimeSpan.FromSeconds(30));
            return [new PresenceProcessSample(7, "Baxy", @"C:\Baxy\Baxy.exe", 1, 1, 0, 0)];
        }
    }
}
