using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Clipboard;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsClipboardProviderTests
{
    [Test]
    public async Task ReadRequiresTwoIdenticalSnapshots()
    {
        var platform = new FakeClipboardPlatform("privado", 7);
        var provider = new WindowsClipboardProvider(platform);

        ClipboardTextSnapshot result = await provider.ReadTextAsync(100, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Text, Is.EqualTo("privado"));
            Assert.That(result.SequenceNumber, Is.EqualTo(7));
            Assert.That(platform.ReadCount, Is.EqualTo(2));
        });
    }

    [Test]
    public void ChangedClipboardDuringReadFailsClosed()
    {
        var platform = new FakeClipboardPlatform("uno", 3) { ChangeOnSecondRead = true };
        var provider = new WindowsClipboardProvider(platform);

        Assert.That(
            async () => await provider.ReadTextAsync(100, CancellationToken.None),
            Throws.TypeOf<ClipboardProviderException>()
                .With.Property(nameof(ClipboardProviderException.Code))
                .EqualTo("clipboard_changed_during_read"));
    }

    [Test]
    public async Task WriteReopensAndVerifiesExactTextAndSequence()
    {
        var platform = new FakeClipboardPlatform("antes", 10);
        var provider = new WindowsClipboardProvider(platform);

        ClipboardWriteResult result = await provider.WriteTextAsync("después", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(platform.Text, Is.EqualTo("después"));
            Assert.That(platform.ReplaceCount, Is.EqualTo(1));
            Assert.That(platform.ReadCount, Is.EqualTo(3));
            Assert.That(result.SequenceNumber, Is.EqualTo(11));
            Assert.That(result.CharacterCount, Is.EqualTo(7));
            Assert.That(result.Changed, Is.True);
        });
    }

    [Test]
    public void OpenWaitsOutAnotherProcessHoldingTheClipboard()
    {
        int tries = 0;
        var waits = new List<TimeSpan>();

        Win32ClipboardPlatform.OpenRetrying(() => ++tries == 4, waits.Add);

        Assert.Multiple(() =>
        {
            Assert.That(tries, Is.EqualTo(4));
            Assert.That(waits, Has.Count.EqualTo(3));
        });
    }

    [Test]
    public void OpenOnTheFirstTryNeverWaits()
    {
        var waits = new List<TimeSpan>();

        Win32ClipboardPlatform.OpenRetrying(() => true, waits.Add);

        Assert.That(waits, Is.Empty);
    }

    [Test]
    public void ClipboardHeldLongerThanASecondIsBusy()
    {
        int tries = 0;
        TimeSpan waited = TimeSpan.Zero;

        Assert.That(
            () => Win32ClipboardPlatform.OpenRetrying(() => { tries++; return false; }, pause => waited += pause),
            Throws.TypeOf<ClipboardProviderException>()
                .With.Property(nameof(ClipboardProviderException.Code))
                .EqualTo("clipboard_busy"));
        Assert.Multiple(() =>
        {
            Assert.That(tries, Is.EqualTo(Win32ClipboardPlatform.OpenAttempts));
            Assert.That(waited, Is.LessThanOrEqualTo(TimeSpan.FromSeconds(1)));
        });
    }

    // Round A: a copy that failed once the person's clipboard was emptied or written came back as a clean failure. A
    // partial write (EmptyClipboard done, SetClipboardData refused), a read-back of other text, and a read-back that
    // did not answer each say the clipboard may already have changed; a write refused before touching it does not.
    [TestCase("partial", "clipboard_partial_write", true)]
    [TestCase("other", "verification_failed", true)]
    [TestCase("busy", "clipboard_busy", true)]
    [TestCase("refused", "clipboard_allocation_failed", false)]
    public async Task ACopyThatFailedAfterTouchingTheClipboardSaysItMayHaveChanged(
        string failure, string errorCode, bool effectMayHaveOccurred)
    {
        var platform = new FakeClipboardPlatform("antes", 1)
        {
            ReplaceFailure = failure switch
            {
                "partial" => new ClipboardProviderException("clipboard_partial_write") { EffectMayHaveOccurred = true },
                "refused" => new ClipboardProviderException("clipboard_allocation_failed"),
                _ => null,
            },
            WrittenInstead = failure == "other" ? "otro" : null,
            BusyAfterReplace = failure == "busy",
        };
        using JsonDocument arguments = JsonDocument.Parse("{\"text\":\"nuevo\"}");

        OperationOutcome outcome = await new ClipboardWriteTextHandler(new WindowsClipboardProvider(platform)).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
        });
    }

    private sealed class FakeClipboardPlatform(string text, uint sequence) : IClipboardPlatform
    {
        public string Text { get; private set; } = text;

        public uint Sequence { get; private set; } = sequence;

        public int ReadCount { get; private set; }

        public int ReplaceCount { get; private set; }

        public bool ChangeOnSecondRead { get; init; }

        public ClipboardProviderException? ReplaceFailure { get; init; }

        public string? WrittenInstead { get; init; }

        public bool BusyAfterReplace { get; init; }

        public uint GetSequenceNumber() => Sequence;

        public ClipboardTextSnapshot ReadText(int maximumCharacters)
        {
            if (BusyAfterReplace && ReplaceCount > 0)
                throw new ClipboardProviderException("clipboard_busy");
            ReadCount++;
            if (ChangeOnSecondRead && ReadCount == 2)
            {
                Text = "dos";
                Sequence++;
            }

            bool truncated = Text.Length > maximumCharacters;
            string bounded = truncated ? Text[..maximumCharacters] : Text;
            return new ClipboardTextSnapshot(bounded, bounded.Length, truncated, Sequence);
        }

        public void ReplaceText(string text)
        {
            if (ReplaceFailure is not null)
                throw ReplaceFailure;
            ReplaceCount++;
            Text = WrittenInstead ?? text;
            Sequence++;
        }
    }
}
