using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The model's processes are found once and then only checked by id: the rail reads every 1.5 s, and listing the PC's
/// processes each time (Process.GetProcessesByName reads the whole process table) ran out of memory (F17).
/// </summary>
[TestFixture]
public sealed class ModelProcessTrackerTests
{
    private const int Mind = 100;
    private const int Python = 101;
    private const int Llama = 102;

    private sealed class Pc
    {
        public readonly HashSet<int> Alive = [Python, Llama];
        public int Lists;
        public DateTimeOffset Now = new(2026, 11, 4, 3, 0, 0, TimeSpan.Zero);

        public IReadOnlyList<(int Id, int Parent)> Scan(IReadOnlyCollection<int> parents, string name)
        {
            Lists++;
            (int Id, int Parent)[] all = name == "python" ? [(Python, Mind)] : [(Llama, Python)];
            return [.. all.Where(entry => parents.Contains(entry.Parent) && Alive.Contains(entry.Id))];
        }

        public bool IsChildOf(int id, int parent) => Alive.Contains(id);
    }

    [Test]
    public void ItFindsTheChainAndThenOnlyChecksTheKnownProcesses()
    {
        var pc = new Pc();
        var tracker = new ModelProcessTracker(pc.Scan, pc.IsChildOf, () => pc.Now);

        List<int> first = tracker.ProcessesOf(Mind);
        pc.Now += TimeSpan.FromSeconds(1.5);
        List<int> second = tracker.ProcessesOf(Mind);
        pc.Now += TimeSpan.FromSeconds(1.5);
        tracker.ProcessesOf(Mind);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.EquivalentTo(new[] { Mind, Python, Llama }));
            Assert.That(second, Is.EquivalentTo(first));
            Assert.That(pc.Lists, Is.EqualTo(2), "python and llama-server listed once, not on every sample");
            Assert.That(tracker.Scans, Is.EqualTo(1));
        });
    }

    [Test]
    public void AModelThatIsNotUpYetIsLookedForNoMoreOftenThanTheInterval()
    {
        var pc = new Pc();
        pc.Alive.Clear();
        var tracker = new ModelProcessTracker(pc.Scan, pc.IsChildOf, () => pc.Now);

        for (int i = 0; i < 6; i++)
        {
            tracker.ProcessesOf(Mind);
            pc.Now += TimeSpan.FromSeconds(1.5);
        }

        Assert.That(tracker.Scans, Is.EqualTo(1));

        pc.Alive.UnionWith([Python, Llama]);
        pc.Now += ModelProcessTracker.RescanInterval;
        Assert.That(tracker.ProcessesOf(Mind), Is.EquivalentTo(new[] { Mind, Python, Llama }));
    }

    [Test]
    public void AServerThatEndedIsDroppedAtOnceAndFoundAgainAtTheNextScan()
    {
        var pc = new Pc();
        var tracker = new ModelProcessTracker(pc.Scan, pc.IsChildOf, () => pc.Now);
        tracker.ProcessesOf(Mind);

        pc.Alive.Remove(Llama);
        pc.Now += TimeSpan.FromSeconds(1.5);
        Assert.That(tracker.ProcessesOf(Mind), Is.EquivalentTo(new[] { Mind, Python }), "no stale id is reported");

        pc.Alive.Add(Llama);
        pc.Now += ModelProcessTracker.RescanInterval;
        Assert.That(tracker.ProcessesOf(Mind), Is.EquivalentTo(new[] { Mind, Python, Llama }));
    }

    [Test]
    public void ANewMindForgetsTheOldOnesProcesses()
    {
        var pc = new Pc();
        var tracker = new ModelProcessTracker(pc.Scan, pc.IsChildOf, () => pc.Now);
        tracker.ProcessesOf(Mind);

        pc.Alive.Clear();
        Assert.That(tracker.ProcessesOf(200), Is.EqualTo(new[] { 200 }));
    }
}
