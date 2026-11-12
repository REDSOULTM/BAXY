using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The rail's sampler at shutdown: the window disposes it while a reading may still be under way, and that reading
/// released the lock DisposeAsync had already disposed (ObjectDisposedException from a reading nobody waits for).
/// </summary>
[TestFixture]
public sealed class FieldTelemetrySamplerTests
{
    [Test]
    public async Task AReadingUnderWayWhenTheSamplerIsDisposedEndsWithoutFailing()
    {
        var measuring = new TaskCompletionSource<FieldMetricSnapshot>(TaskCreationOptions.RunContinuationsAsynchronously);
        var sampler = new FieldTelemetrySampler(static () => null, _ => measuring.Task);

        Task<FieldMetricSnapshot> reading = sampler.SampleAsync(CancellationToken.None);
        await sampler.DisposeAsync();
        measuring.SetResult(new FieldMetricSnapshot(1, 2, 3, 4, 5));

        Assert.That((await reading).Cpu, Is.EqualTo(1));
        Assert.ThrowsAsync<ObjectDisposedException>(() => sampler.SampleAsync(CancellationToken.None));
    }

    // Seen in the real App on the PC (2026-11-09): with a model of Ollama's in use the rail said «0.0gb» of the model's VRAM, as
    // only the mind's processes were counted. BAXY's own Ollama and the runner under it count too while its model is in use.
    [Test]
    public void TheOllamaBaxyOpenedCountsAsTheModelWhileItsModelIsInUse()
    {
        var mind = new ModelProcessTracker(scan: static (parents, name) => name == "llama-server" && parents.Contains(4242) ? [(4300, 4242)] : [],
            isChildOf: static (_, _) => true);
        var ollama = new ModelProcessTracker(scan: static (parents, name) => name == "llama-server" && parents.Contains(777) ? [(778, 777)] : [],
            isChildOf: static (_, _) => true);
        int? inUse = 777;
        var sampler = new FieldTelemetrySampler(static () => 4242, processes: mind, otherModel: () => inUse, otherProcesses: ollama);

        List<int> counted = sampler.ModelProcesses();
        inUse = null;
        List<int> afterwards = sampler.ModelProcesses();

        Assert.Multiple(() =>
        {
            Assert.That(counted, Is.EquivalentTo(new[] { 4242, 4300, 777, 778 }));
            Assert.That(afterwards, Is.EquivalentTo(new[] { 4242, 4300 }));
        });
    }

    // F17 (2026-11-03 23:00): on a PC short of RAM, listing the processes threw OutOfMemoryException into the rail's
    // reading and the view (WebView2) went down twice.
    [Test]
    public void ARunOutOfMemoryListingTheProcessesSkipsTheModelReadingAndIsReported()
    {
        var reports = new List<string>();
        var tracker = new ModelProcessTracker(scan: static (_, _) => RunOutOfMemory());
        var sampler = new FieldTelemetrySampler(static () => 4242, processes: tracker, report: reports.Add);

        (double? _, double? vram, double? ram, double? _) = sampler.ReadModel();

        Assert.Multiple(() =>
        {
            Assert.That(vram, Is.Null);
            Assert.That(ram, Is.Null);
            Assert.That(reports, Has.Count.EqualTo(1));
            Assert.That(reports[0], Does.Contain("out of memory"));
        });
    }

    // hub/modelo-local moved these readings inside the catch: with memory to spare, BAXY's own model reads as it did.
    [Test]
    public void WithMemoryToSpareTheModelsReadingsAreStillThere()
    {
        var reports = new List<string>();
        var sampler = new FieldTelemetrySampler(static () => Environment.ProcessId, report: reports.Add);

        (double? _, double? _, double? ram, double? _) = sampler.ReadModel();

        Assert.Multiple(() =>
        {
            Assert.That(ram, Is.GreaterThan(0));
            Assert.That(reports, Is.Empty);
        });
    }

    [Test]
    public void AnotherFailureListingTheProcessesIsNotSilenced()
    {
        var reports = new List<string>();
        var tracker = new ModelProcessTracker(scan: static (_, _) => throw new InvalidOperationException("broken"));
        var sampler = new FieldTelemetrySampler(static () => 4242, processes: tracker, report: reports.Add);

        Assert.Throws<InvalidOperationException>(() => sampler.ReadModel());
        Assert.That(reports, Is.Empty);
    }

    [Test]
    public void TheSampleAfterAnOutOfMemoryScanDoesNotListTheProcessesAgainAtOnce()
    {
        DateTimeOffset now = new(2026, 11, 4, 3, 0, 0, TimeSpan.Zero);
        int scans = 0;
        var tracker = new ModelProcessTracker(
            scan: (_, _) => scans++ == 0 ? RunOutOfMemory() : [],
            isChildOf: static (_, _) => true,
            now: () => now);

        Assert.Throws<OutOfMemoryException>(() => tracker.ProcessesOf(100));
        Assert.That(tracker.ProcessesOf(100), Is.EqualTo(new[] { 100 }));
        Assert.That(scans, Is.EqualTo(1), "a failed scan is not retried inside the interval");

        now += ModelProcessTracker.RescanInterval;
        tracker.ProcessesOf(100);
        Assert.That(scans, Is.GreaterThan(1));
    }

    // A real OutOfMemoryException from the runtime (CA2201 keeps tests from raising the reserved type by hand): an array
    // longer than the CLR allows fails with it before allocating anything (Array.MaxLength, Microsoft Learn).
    private static IReadOnlyList<(int Id, int Parent)> RunOutOfMemory()
    {
        int length = int.MaxValue;
        _ = new int[length];
        return [];
    }
}
