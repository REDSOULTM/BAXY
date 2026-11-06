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

    // uso-89 (diag-b5bd, R06): a fresh Edge's first look listed its frame's 23 controls and no Document; a later look
    // had the Document and the page's ListItems. listed: the controls the view lists (controlCount may count more).
    private static JsonDocument Frame(int listed, bool document, int? counted = null)
    {
        var controls = Enumerable.Range(0, listed)
            .Select(i => $$"""{"i":{{i}},"kind":"{{(document && i == listed - 1 ? "Document" : "Button")}}","name":"c{{i}}"}""");
        return JsonDocument.Parse(
            $$"""{"ok":true,"controlCount":{{counted ?? listed}},"controls":[{{string.Join(",", controls)}}]}""");
    }

    private static async Task<(int Count, bool Woken, int Reads)> SettleFrame(
        JsonDocument first, bool awaitsDocument, params JsonDocument[] later)
    {
        var queue = new Queue<JsonDocument>(later);
        int reads = 0;
        (JsonDocument answer, bool woken) = await WindowsVisibleControlAdapter.SettleTreeAsync(
            first,
            () =>
            {
                reads++;
                return Task.FromResult(queue.Count > 0 ? queue.Dequeue() : null);
            },
            _ => Task.CompletedTask,
            awaitsDocument);
        using (answer)
            return (answer.RootElement.GetProperty("controlCount").GetInt32(), woken, reads);
    }

    [Test]
    public async Task AChromiumFrameReadWithoutItsPageIsReadAgainUntilThePageComes()
    {
        var settled = await SettleFrame(Frame(23, false), true, Frame(23, false), Frame(31, true), Frame(31, true));
        Assert.That(settled, Is.EqualTo((31, true, 3)));
    }

    // The page came while the frame lost a passing control: that read is the page. A read that failed ends the wait.
    [Test]
    public async Task AReadThatBringsThePageIsKeptAndAFailedReadEndsTheWait()
    {
        var shrunk = await SettleFrame(Frame(23, false), true, Frame(22, true), Frame(22, true));
        var failed = await SettleFrame(Frame(23, false), true,
            JsonDocument.Parse("""{"ok":false,"error":"x"}"""), Frame(31, true));
        Assert.Multiple(() =>
        {
            Assert.That(shrunk, Is.EqualTo((22, true, 2)));
            Assert.That(failed, Is.EqualTo((23, false, 1)));
        });
    }

    [Test]
    public async Task APageThatNeverComesIsWaitedForWithinTheBound()
    {
        var settled = await SettleFrame(Frame(23, false), true,
            Frame(23, false), Frame(23, false), Frame(23, false), Frame(23, false), Frame(23, false), Frame(40, true));
        Assert.That(settled, Is.EqualTo((23, false, WindowsVisibleControlAdapter.TreeSettleReads)));
    }

    [Test]
    public async Task AFrameWithItsPageOrACutReadOrAnotherToolkitIsNotReadAgain()
    {
        var withPage = await SettleFrame(Frame(25, true), true, Frame(40, true));
        var cut = await SettleFrame(Frame(23, false, counted: 60), true, Frame(70, true));
        var otherToolkit = await SettleFrame(Frame(23, false), false, Frame(31, true));
        Assert.Multiple(() =>
        {
            Assert.That(withPage, Is.EqualTo((25, false, 0)));
            Assert.That(cut, Is.EqualTo((60, false, 0)));
            Assert.That(otherToolkit, Is.EqualTo((23, false, 0)));
        });
    }

    [Test]
    public async Task TheReadsAreBounded()
    {
        var settled = await Settle(0, 1, 2, 3, 4, 5, 6, 7);
        Assert.That(settled.Reads, Is.EqualTo(WindowsVisibleControlAdapter.TreeSettleReads));
        Assert.That(settled.Count, Is.EqualTo(5));
    }
}
