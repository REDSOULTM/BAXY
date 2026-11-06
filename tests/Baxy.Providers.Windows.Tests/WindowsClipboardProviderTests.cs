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

    // Review of uso-108: a call already cancelled starts no thread and touches nothing.
    [Test]
    public async Task ACallAlreadyCancelledTouchesNothing()
    {
        var platform = new FakeClipboardPlatform("antes", 10);
        var provider = new WindowsClipboardProvider(platform);
        using var cancelled = new CancellationTokenSource();
        cancelled.Cancel();

        Assert.Multiple(() =>
        {
            Assert.ThrowsAsync<OperationCanceledException>(async () => await provider.WriteTextAsync("después", cancelled.Token));
            Assert.ThrowsAsync<OperationCanceledException>(async () => await provider.ReadTextAsync(100, cancelled.Token));
        });
        // A thread started anyway would still be on its way.
        await Task.Delay(200);
        Assert.Multiple(() =>
        {
            Assert.That(platform.ReadCount, Is.Zero);
            Assert.That(platform.ReplaceCount, Is.Zero);
            Assert.That(platform.Text, Is.EqualTo("antes"));
        });
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

    private static readonly TimeSpan ShortDeadline = TimeSpan.FromMilliseconds(100);

    // A8 (agent-desktop probes/windows/FINDINGS.md A22-3): a read inside a call that does not return ends with its code,
    // and what it held is let go.
    [Test]
    public async Task AReadThatDoesNotReturnEndsWithItsCode()
    {
        using var blocked = new BlockingClipboardPlatform();
        Task<ClipboardTextSnapshot> read = Task.Run(async () =>
            await new WindowsClipboardProvider(blocked, ShortDeadline).ReadTextAsync(100, CancellationToken.None));

        Task finished = await Task.WhenAny(read, Task.Delay(TimeSpan.FromSeconds(15)));

        Assert.That(finished, Is.SameAs(read), "the read did not answer");
        var refused = Assert.CatchAsync<ClipboardProviderException>(async () => await read);
        Assert.Multiple(() =>
        {
            Assert.That(refused!.Code, Is.EqualTo("clipboard_owner_not_responding"));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(blocked.Releases, Is.EqualTo(1));
        });
    }

    // agent-desktop clipboard_worker_state.rs: while a call is left behind inside the OS the next is refused and does not
    // pile up behind it; when the call comes back the clipboard is used again.
    [Test]
    public async Task WhileACallIsLeftBehindTheNextIsRefusedAndAfterItTheyGoOn()
    {
        using var blocked = new BlockingClipboardPlatform();
        var provider = new WindowsClipboardProvider(blocked, ShortDeadline);
        Assert.CatchAsync<ClipboardProviderException>(async () => await provider.ReadTextAsync(100, CancellationToken.None));
        int started = blocked.ReadCount;

        var refused = Assert.CatchAsync<ClipboardProviderException>(
            async () => await provider.WriteTextAsync("nuevo", CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(refused!.Code, Is.EqualTo("clipboard_owner_not_responding"));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(blocked.ReadCount, Is.EqualTo(started));
            Assert.That(blocked.ReplaceCount, Is.Zero);
        });

        blocked.Let();
        ClipboardTextSnapshot read = await UntilAnswered(() => provider.ReadTextAsync(100, CancellationToken.None));
        Assert.That(read.Text, Is.EqualTo("texto"));
    }

    // AD's clipboard tests «refused each other» when any running call counted: only one left behind does.
    [Test]
    public async Task CallsThatEndInTimeDoNotRefuseEachOther()
    {
        var platform = new FakeClipboardPlatform("hola", 1);
        var provider = new WindowsClipboardProvider(platform);

        for (int attempt = 0; attempt < 20; attempt++)
        {
            ClipboardTextSnapshot read = await provider.ReadTextAsync(100, CancellationToken.None);
            Assert.That(read.Text, Is.EqualTo("hola"));
        }
    }

    // A call that throws inside its thread ends like one that answered: its own failure, and nothing left behind.
    [Test]
    public async Task ACallThatFailsInsideLeavesNothingBehind()
    {
        var platform = new FailingOnceClipboardPlatform();
        var provider = new WindowsClipboardProvider(platform, TimeSpan.FromSeconds(30));

        var failed = Assert.CatchAsync<ClipboardProviderException>(
            async () => await provider.ReadTextAsync(100, CancellationToken.None));
        ClipboardTextSnapshot read = await provider.ReadTextAsync(100, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(failed!.Code, Is.EqualTo("clipboard_read_failed"));
            Assert.That(read.Text, Is.EqualTo("texto"));
        });
    }

    // An owner that does not answer is never asked: nothing is opened, so the clipboard is not held for anyone.
    [Test]
    public void AnOwnerThatDoesNotAnswerIsRefusedBeforeOpeningAnything()
    {
        var platform = new FakeClipboardPlatform("antes", 1) { OwnerAnswers = false };
        var provider = new WindowsClipboardProvider(platform);

        var read = Assert.CatchAsync<ClipboardProviderException>(
            async () => await provider.ReadTextAsync(100, CancellationToken.None));
        var write = Assert.CatchAsync<ClipboardProviderException>(
            async () => await provider.WriteTextAsync("nuevo", CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(read!.Code, Is.EqualTo("clipboard_owner_not_responding"));
            Assert.That(write!.Code, Is.EqualTo("clipboard_owner_not_responding"));
            Assert.That(write.EffectMayHaveOccurred, Is.False);
            Assert.That(platform.ReadCount, Is.Zero);
            Assert.That(platform.ReplaceCount, Is.Zero);
        });
    }

    // EmptyClipboard waits on the old owner as well (measured: 4 s, until the owner came back), and it may still empty the
    // clipboard after the call is left behind; a write that never got past the reading before it touched nothing.
    [TestCase("write", true)]
    [TestCase("read before", false)]
    public void AWriteThatDoesNotReturnSaysWhetherItMayHaveChanged(string blockedOn, bool effectMayHaveOccurred)
    {
        using var blocked = new BlockingClipboardPlatform { ReadsAnswer = blockedOn == "write" };
        var provider = new WindowsClipboardProvider(blocked, ShortDeadline);

        var refused = Assert.CatchAsync<ClipboardProviderException>(
            async () => await provider.WriteTextAsync("nuevo", CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(refused!.Code, Is.EqualTo("clipboard_owner_not_responding"));
            Assert.That(refused.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
            Assert.That(blocked.Releases, Is.EqualTo(1));
        });
    }

    // The code reaches the model as the handler's failure, on a read and on the read-back of a write.
    [Test]
    public async Task TheHandlerSaysTheOwnerDoesNotAnswer()
    {
        using var blocked = new BlockingClipboardPlatform();
        using JsonDocument arguments = JsonDocument.Parse("{}");

        OperationOutcome outcome = await new ClipboardReadTextHandler(new WindowsClipboardProvider(blocked, ShortDeadline))
            .ExecuteAsync(new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()), CancellationToken.None);

        Assert.That(
            OperationVisibleFacts.FromOutcome("clipboard.read.text", outcome),
            Is.EqualTo("{\"status\":\"failed\",\"error\":\"clipboard_owner_not_responding\"}"));
    }

    // B11: what the clipboard holds, on this failure only, with no names; empty says what it always said.
    [TestCase("files", 3, "{\"status\":\"failed\",\"error\":\"clipboard_has_no_text\",\"observed\":{\"holds\":\"files\",\"count\":3}}")]
    [TestCase("image", null, "{\"status\":\"failed\",\"error\":\"clipboard_has_no_text\",\"observed\":{\"holds\":\"image\"}}")]
    [TestCase("other", null, "{\"status\":\"failed\",\"error\":\"clipboard_has_no_text\",\"observed\":{\"holds\":\"other\"}}")]
    [TestCase(null, null, "{\"status\":\"failed\",\"error\":\"clipboard_has_no_text\"}")]
    public async Task ANoTextFailureSaysWhatItHoldsInstead(string? kind, int? count, string expected)
    {
        var platform = new NoTextClipboardPlatform(kind is null ? null : new ClipboardHolds(kind, count));
        using JsonDocument arguments = JsonDocument.Parse("{}");

        OperationOutcome outcome = await new ClipboardReadTextHandler(new WindowsClipboardProvider(platform))
            .ExecuteAsync(new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()), CancellationToken.None);

        Assert.That(OperationVisibleFacts.FromOutcome("clipboard.read.text", outcome), Is.EqualTo(expected));
    }

    // Banco de uso 05-11 (S07): the model read a clipboard nobody asked about, which held a command with a key, and told it.
    // What looks like a key by its form does not reach the model; the rest of the text does, and it says the part is there.
    [Test]
    public async Task AReadGivesTheTextWithoutWhatLooksLikeAKeyAndSaysItIsThere()
    {
        const string key = "Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3Hs5Gf0Aj";
        string text = $"conecta --host 203.0.113.7 --token {key}";
        JsonElement read = await ReadThrough(new FakeClipboardPlatform(text, 7));

        Assert.Multiple(() =>
        {
            Assert.That(read.GetProperty("text").GetString(), Is.EqualTo("conecta --host 203.0.113.7 --token •••"));
            Assert.That(read.GetRawText(), Does.Not.Contain(key));
            Assert.That(read.GetProperty("characterCount").GetInt32(), Is.EqualTo(text.Length));
            Assert.That(read.GetProperty("secretLike").GetString(), Does.Contain("•••").And.Contain("not read aloud"));
        });
    }

    [Test]
    public async Task AReadOfOrdinaryTextIsAsItWasAndSaysNothingOfKeys()
    {
        const string text = "Comprar pan, leche y dos kilos de papas para el domingo";
        JsonElement read = await ReadThrough(new FakeClipboardPlatform(text, 7));

        Assert.Multiple(() =>
        {
            Assert.That(read.GetProperty("text").GetString(), Is.EqualTo(text));
            Assert.That(read.TryGetProperty("secretLike", out _), Is.False);
            Assert.That(read.TryGetProperty("markedPrivate", out _), Is.False);
            // A key more in every read flipped a paste: with readFrom in it, «mete lo copiao en el notepad» went from 9 of 10 to
            // 2 of 10 pasting. An ordinary read says what it said.
            Assert.That(read.TryGetProperty("readFrom", out _), Is.False);
        });
    }

    // Microsoft's «Cloud Clipboard and Clipboard History Formats»: an application that copies something it wants kept out of
    // the clipboard's history and of other monitors marks it, as password managers do. BAXY takes that for what it says.
    [Test]
    public async Task AReadOfAClipboardItsOwnerMarkedPrivateGivesNoneOfIt()
    {
        const string text = "cualquier cosa, con la forma que sea";
        JsonElement read = await ReadThrough(new FakeClipboardPlatform(text, 7) { MarkedPrivate = true });

        Assert.Multiple(() =>
        {
            Assert.That(read.GetProperty("text").GetString(), Is.EqualTo("•••"));
            Assert.That(read.GetRawText(), Does.Not.Contain("cualquier"));
            Assert.That(read.GetProperty("markedPrivate").GetString(), Does.Contain("marked"));
            Assert.That(read.GetProperty("characterCount").GetInt32(), Is.EqualTo(text.Length));
        });
    }

    // A write and its read-back compare the real text: masking is what the model is given, not what the clipboard holds.
    [Test]
    public async Task AWriteOfAKeyStillReadsItBackWhole()
    {
        const string key = "Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3Hs5Gf0Aj";
        var platform = new FakeClipboardPlatform("antes", 7);
        using JsonDocument arguments = JsonDocument.Parse($$"""{"text":"{{key}}"}""");

        OperationOutcome outcome = await new ClipboardWriteTextHandler(new WindowsClipboardProvider(platform))
            .ExecuteAsync(new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(platform.Text, Is.EqualTo(key));
        });
    }

    private static async Task<JsonElement> ReadThrough(IClipboardPlatform platform)
    {
        using JsonDocument arguments = JsonDocument.Parse("{}");
        OperationOutcome outcome = await new ClipboardReadTextHandler(new WindowsClipboardProvider(platform))
            .ExecuteAsync(new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()), CancellationToken.None);
        Assert.That(outcome.Succeeded, Is.True);
        return outcome.Result!.Value.Clone();
    }

    // Control: a read that failed is not told as anything held, and a write over a copy of files goes on as before.
    [Test]
    public async Task AReadThatFailedHoldsNothingAndAWriteOverFilesGoesOn()
    {
        using JsonDocument arguments = JsonDocument.Parse("{}");
        OperationOutcome failed = await new ClipboardReadTextHandler(new WindowsClipboardProvider(new FailingOnceClipboardPlatform()))
            .ExecuteAsync(new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()), CancellationToken.None);
        var overFiles = new NoTextClipboardPlatform(new ClipboardHolds("files", 2));

        ClipboardWriteResult written = await new WindowsClipboardProvider(overFiles).WriteTextAsync("nuevo", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(
                OperationVisibleFacts.FromOutcome("clipboard.read.text", failed),
                Is.EqualTo("{\"status\":\"failed\",\"error\":\"clipboard_read_failed\"}"));
            Assert.That(written.Changed, Is.True);
        });
    }

    private const uint Files = 15;
    private const uint DeviceBitmap = 8;
    private const uint ImageFile = 49_000;

    // B11: files before a picture, as agent-desktop reads them; text was asked for before any of this. The file count is
    // only asked for when there are files, since it asks the owner.
    [TestCase(new uint[] { Files, DeviceBitmap }, 5, "files", 2)]
    [TestCase(new uint[] { DeviceBitmap }, 3, "image", null)]
    [TestCase(new uint[] { ImageFile }, 1, "image", null)]
    [TestCase(new uint[0], 1, "other", null)]
    public void WhatItHoldsReadsTheFormats(uint[] formats, int count, string kind, int? files)
    {
        ClipboardHolds? holds = Win32ClipboardPlatform.WhatItHolds(formats.Contains, ImageFile, count, () => 2);

        Assert.That(holds, Is.EqualTo(new ClipboardHolds(kind, files)));
    }

    [Test]
    public void NoFormatsHoldNothing() =>
        Assert.That(
            Win32ClipboardPlatform.WhatItHolds(static _ => false, ImageFile, 0, static () => throw new InvalidOperationException()),
            Is.Null);

    private static async Task<T> UntilAnswered<T>(Func<ValueTask<T>> call)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew();
        while (true)
        {
            try
            {
                return await call();
            }
            catch (ClipboardProviderException) when (watch.Elapsed < TimeSpan.FromSeconds(5))
            {
                await Task.Delay(10);
            }
        }
    }

    // Stays inside the call it is told to block until the test lets it go, as a read does inside GetClipboardData.
    private sealed class BlockingClipboardPlatform : IClipboardPlatform, IDisposable
    {
        private readonly ManualResetEventSlim _go = new();
        private int _reads;
        private int _replaces;
        private int _releases;

        public bool ReadsAnswer { get; init; }

        public int ReadCount => Volatile.Read(ref _reads);

        public int ReplaceCount => Volatile.Read(ref _replaces);

        public int Releases => Volatile.Read(ref _releases);

        public uint GetSequenceNumber() => 1;

        public ClipboardTextSnapshot ReadText(int maximumCharacters)
        {
            Interlocked.Increment(ref _reads);
            if (!ReadsAnswer)
                _go.Wait();
            return new ClipboardTextSnapshot("texto", 5, false, 1);
        }

        public void ReplaceText(string text)
        {
            Interlocked.Increment(ref _replaces);
            _go.Wait();
        }

        public void ReleaseAbandonedOpen() => Interlocked.Increment(ref _releases);

        public void Let() => _go.Set();

        public void Dispose() => _go.Set();
    }

    private sealed class FailingOnceClipboardPlatform : IClipboardPlatform
    {
        private bool _failed;

        public uint GetSequenceNumber() => 1;

        public ClipboardTextSnapshot ReadText(int maximumCharacters)
        {
            if (_failed)
                return new ClipboardTextSnapshot("texto", 5, false, 1);
            _failed = true;
            throw new ClipboardProviderException("clipboard_read_failed");
        }

        public void ReplaceText(string text)
        {
        }
    }

    // No text until something is written over it.
    private sealed class NoTextClipboardPlatform(ClipboardHolds? holds) : IClipboardPlatform
    {
        private string? _text;
        private uint _sequence = 1;

        public uint GetSequenceNumber() => _sequence;

        public ClipboardTextSnapshot ReadText(int maximumCharacters) =>
            _text is { } text
                ? new ClipboardTextSnapshot(text, text.Length, false, _sequence)
                : throw new ClipboardProviderException("clipboard_has_no_text") { Holds = holds };

        public void ReplaceText(string text)
        {
            _text = text;
            _sequence++;
        }
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

        public bool OwnerAnswers { get; init; } = true;

        public bool MarkedPrivate { get; init; }

        public bool OwnerResponds(CancellationToken cancellationToken) => OwnerAnswers;

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
            return new ClipboardTextSnapshot(bounded, bounded.Length, truncated, Sequence) { MarkedPrivate = MarkedPrivate };
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
