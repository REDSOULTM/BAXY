using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class PresenceIdleSamplerTests
{
    [Test]
    public void SamplerPublishesAttributedDeltasWithoutHardCodedResourceNumbers()
    {
        var clock = new FakeClock(new DateTimeOffset(2026, 8, 31, 12, 0, 0, TimeSpan.Zero));
        var reader = new ScriptedProcessReader(
        [
            [
                Sample(101, "Baxy", 40_000_000, 200, 1.0, 512L * 1024 * 1024),
                Sample(202, "llama-server", 80_000_000, 80, 10.0, 1_800L * 1024 * 1024),
            ],
            [
                Sample(101, "Baxy", 41_000_000, 201, 1.2, 512L * 1024 * 1024),
                Sample(202, "llama-server", 79_000_000, 80, 16.0, 1_800L * 1024 * 1024),
            ],
        ]);
        var sampler = new PresenceIdleSampler(reader, clock);

        PresenceIdleSnapshot start = sampler.Capture(true, true, true, null, "ready");
        clock.Advance(TimeSpan.FromMinutes(15));
        PresenceIdleSnapshot end = sampler.Capture(true, true, true, null, "ready");

        long workingDelta = PresenceIdleSampler.TotalWorkingSet(end)
            - PresenceIdleSampler.TotalWorkingSet(start);
        Assert.Multiple(() =>
        {
            Assert.That(start.Processes, Has.Count.EqualTo(2));
            Assert.That(end.Processes.Select(process => process.ProcessId), Is.EqualTo(new[] { 101, 202 }));
            Assert.That(start.Processes.All(process => process.Path.Length > 0), Is.True);
            Assert.That(PresenceIdleSampler.HasUnattributedProcess(start), Is.False);
            Assert.That(PresenceIdleSampler.ExceedsVramCeiling(end), Is.False);
            Assert.That(workingDelta, Is.EqualTo(0));
            Assert.That(sampler.HasMonotonicWorkingSetGrowth(), Is.False);
            Assert.That(sampler.HasAvoidableProcessTreeSpin(logicalProcessorCount: 16), Is.False);
            Assert.That((end.Utc - start.Utc).TotalMinutes, Is.EqualTo(15));
        });
    }

    [Test]
    public void MonotonicWorkingSetGrowthIsDetectedFromTheShippedRule()
    {
        var reader = new ScriptedProcessReader(
        [
            [Sample(1, "Baxy", 10_000_000, 10, 1, 0)],
            [Sample(1, "Baxy", 30_000_000, 10, 1, 0)],
            [Sample(1, "Baxy", 50_000_000, 10, 1, 0)],
        ]);
        var sampler = new PresenceIdleSampler(reader);
        sampler.Capture(true, true, true, null, "ready");
        sampler.Capture(true, true, true, null, "ready");
        sampler.Capture(true, true, true, null, "ready");

        Assert.That(sampler.HasMonotonicWorkingSetGrowth(), Is.True);
    }

    [Test]
    public void ProcessTreeSpinIncludesMindAndKeepWarmChildren()
    {
        var clock = new FakeClock(new DateTimeOffset(2026, 8, 31, 12, 0, 0, TimeSpan.Zero));
        var reader = new ScriptedProcessReader(
        [
            [
                Sample(1, "Baxy", 10_000_000, 10, 1.0, 0),
                Sample(2, "llama-server", 10_000_000, 10, 100.0, 1_000_000_000),
            ],
            [
                Sample(1, "Baxy", 10_000_000, 10, 20.0, 0),
                Sample(2, "llama-server", 10_000_000, 10, 400.0, 1_000_000_000),
            ],
        ]);
        var sampler = new PresenceIdleSampler(reader, clock);
        sampler.Capture(true, true, true, null, "ready");
        clock.Advance(TimeSpan.FromSeconds(10));
        sampler.Capture(true, true, true, null, "ready");

        Assert.That(
            sampler.HasAvoidableProcessTreeSpin(logicalProcessorCount: 16),
            Is.True);
    }

    [Test]
    public void ReusedPidWithADifferentExecutableIsNotChargedToTheOldProcess()
    {
        var clock = new FakeClock(new DateTimeOffset(2026, 8, 31, 12, 0, 0, TimeSpan.Zero));
        var reader = new ScriptedProcessReader(
        [
            [new PresenceProcessSample(2, "python", @"C:\BAXY\old.exe", 1, 1, 1, 0)],
            [new PresenceProcessSample(2, "python", @"C:\BAXY\new.exe", 1, 1, 500, 0)],
        ]);
        var sampler = new PresenceIdleSampler(reader, clock);
        sampler.Capture(true, true, true, null, "ready");
        clock.Advance(TimeSpan.FromSeconds(10));
        sampler.Capture(true, true, true, null, "ready");

        Assert.That(
            sampler.HasAvoidableProcessTreeSpin(logicalProcessorCount: 16),
            Is.False);
    }

    [Test]
    public void PresenceHostWritesStatusAndIdleSamplesToTheDataRoot()
    {
        string root = PrivateDataRootTestSupport.NewPath("presence-idle");
        try
        {
            var run = new MemoryRunKey();
            Directory.CreateDirectory(root);
            string exe = Path.Combine(root, "Baxy.exe");
            File.WriteAllBytes(exe, [0x4D, 0x5A]);
            var reader = new ScriptedProcessReader(
            [
                [Sample(7, "Baxy", 12_000_000, 40, 2.0, 0)],
            ]);
            var host = new PresenceHost(
                new WindowsAutostartRegistration(run, () => exe),
                new PresenceStatusStore(Path.Combine(root, "presence")),
                new PresenceIdleSampler(reader),
                registerNativeTray: false);

            host.Start([]);
            PresenceIdleSnapshot sample = host.CaptureIdleSample();

            Assert.That(File.Exists(host.StatusPath), Is.True);
            string status = File.ReadAllText(host.StatusPath);
            Assert.That(status, Does.Contain(PresenceLimits.StatusSchema));
            Assert.That(status, Does.Contain("autostart_registered"));
            Assert.That(host.AutostartCommand, Does.Contain(exe));
            Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.EqualTo(host.AutostartCommand));
            Assert.That(sample.Processes[0].Name, Is.EqualTo("Baxy"));
            Assert.That(File.Exists(Path.Combine(root, "presence", "idle-samples.v1.jsonl")), Is.True);
            host.Dispose();
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static PresenceProcessSample Sample(
        int processId,
        string name,
        long workingSet,
        long handles,
        double cpu,
        long vram) =>
        new(processId, name, "C:\\BAXY\\" + name + ".exe", workingSet, handles, cpu, vram);

    private sealed class ScriptedProcessReader : IPresenceProcessReader
    {
        private readonly Queue<IReadOnlyList<PresenceProcessSample>> _frames;

        internal ScriptedProcessReader(IReadOnlyList<IReadOnlyList<PresenceProcessSample>> frames)
        {
            _frames = new Queue<IReadOnlyList<PresenceProcessSample>>(frames);
        }

        public IReadOnlyList<PresenceProcessSample> ReadOwned()
        {
            IReadOnlyList<PresenceProcessSample> next = _frames.Count > 0
                ? _frames.Dequeue()
                : [];
            return next;
        }
    }

    private sealed class FakeClock : IPresenceClock
    {
        internal FakeClock(DateTimeOffset utc) => UtcNow = utc;

        public DateTimeOffset UtcNow { get; private set; }

        internal void Advance(TimeSpan delta) => UtcNow += delta;
    }

    private sealed class MemoryRunKey : IWindowsRunKey
    {
        private readonly Dictionary<string, string> _values = new(StringComparer.Ordinal);

        public string? Read(string name) =>
            _values.TryGetValue(name, out string? value) ? value : null;

        public void Write(string name, string value) => _values[name] = value;

        public void Delete(string name) => _values.Remove(name);
    }
}
