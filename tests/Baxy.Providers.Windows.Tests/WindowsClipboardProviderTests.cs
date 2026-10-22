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

    // FT/proveedores goal (review of receipts): the same plain text written over a Word copy (its HTML, RTF and picture
    // replaced by text alone) changed the clipboard; the same text over the same text alone did not.
    [TestCase(9, true)]
    [TestCase(4, false)]
    public async Task TheSameTextOverARicherCopyIsAChange(int formatsBefore, bool changed)
    {
        var platform = new FakeClipboardPlatform("hola", 1) { Formats = formatsBefore };

        ClipboardWriteResult result = await new WindowsClipboardProvider(platform).WriteTextAsync("hola", CancellationToken.None);

        Assert.That(result.Changed, Is.EqualTo(changed));
    }

    // Revisión 2026-10-22 (C-6): the read-back is bounded by the length of the text written, so «hola mundo» read for
    // «hola» comes back as «hola», truncated; it is not the text written, and is never told as verified.
    [Test]
    public async Task AReadBackCutToTheWrittenLengthIsNotTheTextWritten()
    {
        using JsonDocument arguments = JsonDocument.Parse("{\"text\":\"hola\"}");

        OperationOutcome outcome = await new ClipboardWriteTextHandler(new HoldingClipboard("hola mundo")).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    // A clipboard that accepts every write and goes on holding its own text.
    private sealed class HoldingClipboard(string held) : IClipboardProvider
    {
        public ValueTask<ClipboardTextSnapshot> ReadTextAsync(int maximumCharacters, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ClipboardTextSnapshot(
                held[..Math.Min(held.Length, maximumCharacters)], held.Length, held.Length > maximumCharacters, 2));

        public ValueTask<ClipboardWriteResult> WriteTextAsync(string text, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ClipboardWriteResult(2, text.Length, true));
    }

    private sealed class FakeClipboardPlatform(string text, uint sequence) : IClipboardPlatform
    {
        // Text alone is 4 formats (Unicode, ANSI, OEM text and the locale); a rich copy holds more.
        public int Formats { get; set; } = 4;

        public int FormatCount() => Formats;

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
            Formats = 4;
            Sequence++;
        }
    }
}
