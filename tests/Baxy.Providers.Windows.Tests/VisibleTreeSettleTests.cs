using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// PLAN_GENERAL A2 (uso real 2026-10-21): a tree built on demand is read again until its count of controls settles.
public sealed class VisibleTreeSettleTests
{
    private static JsonDocument View(int controls) =>
        JsonDocument.Parse($$"""{"ok":true,"controlCount":{{controls}},"controls":[]}""");

    private static async Task<(int Count, bool Woken, int Reads, int Pauses)> Settle(int first, params int[] later)
    {
        var queue = new Queue<int>(later);
        int reads = 0, pauses = 0;
        (JsonDocument answer, bool woken) = await WindowsVisibleControlAdapter.SettleTreeAsync(
            View(first),
            () =>
            {
                reads++;
                return Task.FromResult<JsonDocument?>(queue.Count > 0 ? View(queue.Dequeue()) : null);
            },
            _ =>
            {
                pauses++;
                return Task.CompletedTask;
            });
        using (answer)
            return (answer.RootElement.GetProperty("controlCount").GetInt32(), woken, reads, pauses);
    }

    [Test]
    public async Task ATreeThatIsStillBeingBuiltIsReadUntilItStopsGrowing()
    {
        var settled = await Settle(1, 14, 60, 60, 70);
        Assert.That(settled, Is.EqualTo((60, true, 3, 3)));
    }

    [Test]
    public async Task ATreeThatNeverComesCostsOnePause()
    {
        var settled = await Settle(3, 3, 3, 3);
        Assert.That(settled, Is.EqualTo((3, false, 1, 1)));
    }

    [Test]
    public async Task ATreeAlreadyThereIsNotReadAgain()
    {
        var settled = await Settle(25, 80);
        Assert.That(settled, Is.EqualTo((25, false, 0, 0)));
    }

    [Test]
    public async Task TheReadsAreBounded()
    {
        var settled = await Settle(0, 1, 2, 3, 4, 5, 6, 7);
        Assert.That(settled.Reads, Is.EqualTo(WindowsVisibleControlAdapter.TreeSettleReads));
        Assert.That(settled.Count, Is.EqualTo(5));
    }
}
