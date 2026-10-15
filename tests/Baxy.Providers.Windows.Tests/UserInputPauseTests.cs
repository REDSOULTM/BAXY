using System.Buffers.Binary;
using System.Globalization;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The pause detector's two judgements without a desktop (whose Raw Input record is BAXY's, and the self-check
/// against Windows' last-input time), and the census of BAXY's input mark over every injector under <c>src/</c>.
/// </summary>
[TestFixture]
public sealed partial class UserInputPauseTests
{
    private static readonly int Header = 8 + 2 * IntPtr.Size;

    [Test]
    public void AMarkedMouseOrKeyboardRecordIsBaxysAndAnUnmarkedOneIsThePersons()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsUserInputPause.IsOwn(Record(0, BaxyInputMark.Value), Header), Is.True);
            Assert.That(WindowsUserInputPause.IsOwn(Record(1, BaxyInputMark.Value), Header), Is.True);
            Assert.That(WindowsUserInputPause.IsOwn(Record(0, 0), Header), Is.False);
            // The live harness's simulated user injects with a mark of its own: it is the person's.
            Assert.That(WindowsUserInputPause.IsOwn(Record(1, 0x12345678), Header), Is.False);
        });
    }

    // t2-r4 c01-1: the unmarked key UIAutomationCore injects to win the front before a pattern method, sent from a
    // helper script's own UIA client, stopped that helper's burst as if the person had typed.
    [Test]
    public void TheForegroundBidKeyUiAutomationInjectsIsNotThePersons()
    {
        Assert.That(WindowsUserInputPause.IsOwn(Key(0xB9, device: 0), Header), Is.True);
    }

    // Contracases: the same reserved code from a real device, any other injected unmarked key (the harness's simulated
    // person, an on-screen keyboard), and a mouse record are still the person's.
    [Test]
    public void TheBidCodeFromADeviceAndOtherInjectedKeysStayThePersons()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsUserInputPause.IsOwn(Key(0xB9, device: 0x1234), Header), Is.False);
            Assert.That(WindowsUserInputPause.IsOwn(Key(0x41, device: 0), Header), Is.False);
            Assert.That(WindowsUserInputPause.IsOwn(Key(0x41, device: 0x1234), Header), Is.False);
            Assert.That(WindowsUserInputPause.IsOwn(Record(0, 0), Header), Is.False);
        });
    }

    [Test]
    public void ARecordThatIsNeitherMouseNorKeyboardIsNotJudged()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsUserInputPause.IsOwn(Record(2, BaxyInputMark.Value), Header), Is.Null);
            Assert.That(WindowsUserInputPause.IsOwn(new byte[6], Header), Is.Null);
        });
    }

    [Test]
    public void AnInputWindowsRecordedThatTheDetectorMissedCountsAsThePersons()
    {
        // Windows recorded an input at 5000 that the detector (last saw 4000 and 4200) never got, 300 ms ago.
        Assert.That(WindowsUserInputPause.Reconcile(foreign: 4000, own: 4200, windows: 5000, now: 5300), Is.EqualTo(5000));
    }

    // Contracases: BAXY's own input, and an input the detector has not had time to receive, are not the person's.
    [Test]
    public void BaxysOwnInputAndAnInputStillInFlightAreNotThePersons()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsUserInputPause.Reconcile(foreign: 4000, own: 5000, windows: 5000, now: 5300), Is.EqualTo(4000));
            Assert.That(WindowsUserInputPause.Reconcile(foreign: 4000, own: 4200, windows: 5000, now: 5050), Is.EqualTo(4000));
        });
    }

    // interrupcion-fantasma, twin of r9 v3-38 and v3-59: the person types without stopping at 8 keys a second through a
    // path Raw Input never delivers (VK_PACKET characters, or keys another low-level hook swallows; measured 2026-10-08:
    // each one moves Windows' last input, none reaches Raw Input). Read every 50 ms as the lease's wait does, Windows'
    // last input is never 200 ms old while they type: the self-check alone saw a pause all along, and BAXY clicked in
    // the middle of their typing. Across reads, the first such input counts as theirs once it is 200 ms old.
    [Test]
    public void InputRawInputNeverDeliversCountsAsThePersonsWhileItKeepsComing()
    {
        var check = new WindowsUserInputPause.MissedInputCheck();
        long foreign = 4_000;
        long alone = 4_000;
        for (long now = 5_000; now <= 6_000; now += 50)
        {
            long windows = now - now % 125;
            alone = Math.Max(alone, WindowsUserInputPause.Reconcile(alone, own: 3_000, windows, now));
            foreign = Math.Max(foreign, check.Reconcile(foreign, own: 3_000, windows, now));
        }

        Assert.Multiple(() =>
        {
            Assert.That(alone, Is.EqualTo(4_000), "the self-check alone never saw the typing");
            Assert.That(foreign, Is.GreaterThanOrEqualTo(5_625), "the person's typing is seen while it goes on");
            Assert.That(6_000 - foreign, Is.LessThan(500), "never a pause of the lease's half second");
        });
    }

    // Contracases: BAXY's own input (Raw Input delivers its mark a little after Windows records it) and a single input
    // still in flight are not the person's; a single missed input, once old enough, is, as before.
    [Test]
    public void AcrossReadsBaxysOwnInputAndInputInFlightStayNotThePersons()
    {
        var own = new WindowsUserInputPause.MissedInputCheck();
        long first = own.Reconcile(foreign: 4_000, own: 4_200, windows: 5_000, now: 5_010);
        long second = own.Reconcile(foreign: 4_000, own: 5_008, windows: 5_000, now: 5_300);
        var flight = new WindowsUserInputPause.MissedInputCheck();
        long early = flight.Reconcile(foreign: 4_000, own: 4_200, windows: 5_000, now: 5_050);
        long late = flight.Reconcile(foreign: 4_000, own: 4_200, windows: 5_000, now: 5_300);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.EqualTo(4_000));
            Assert.That(second, Is.EqualTo(4_000), "BAXY's own input is not the person's");
            Assert.That(early, Is.EqualTo(4_000), "an input still in flight is not judged yet");
            Assert.That(late, Is.EqualTo(5_000), "a missed input is the person's once it had time to arrive");
        });
    }

    // Review of interrupcion-fantasma (bloqueante), twin of BAXY's own TypeText: a Unicode key every 36 ms that Raw
    // Input never delivers, marked or not (measured: 10 sent, 10 changes of Windows' last input, 0 Raw Input records).
    // Before, «own» stayed at the last input Raw Input delivered and the self-check across reads gave the 8th key to the
    // person: the text stopped at its 7th character as interrupted. Each send is now noted as BAXY's when it goes.
    [Test]
    public void BaxysOwnUnicodeTypingNotedWhenSentIsNeverThePersons()
    {
        var unnoted = new WindowsUserInputPause.MissedInputCheck();
        var noted = new WindowsUserInputPause.MissedInputCheck();
        long began = 10_000;
        long before = 2_000;
        long after = 2_000;
        int cutAt = -1;
        for (int key = 0; key < 40; key++)
        {
            long now = began + 5 + key * 36;
            long windows = key == 0 ? began : now - 36;
            long sentNoted = windows + 1;
            before = Math.Max(before, unnoted.Reconcile(before, own: began, windows, now));
            after = Math.Max(after, noted.Reconcile(after, own: sentNoted, windows, now));
            if (cutAt < 0 && before > began)
                cutAt = key;
        }

        Assert.Multiple(() =>
        {
            Assert.That(cutAt, Is.InRange(5, 9), "the measured defect: unnoted, the text was cut at its 7th character");
            Assert.That(after, Is.EqualTo(2_000), "noted as BAXY's when sent, the whole text is never the person's");
        });
    }

    // Ronda 20 P2 (t-drag-2): windows by handle, each a root of itself but the child 0x211 (of 0x210), each with its process.
    private const nint PersonsWindow = 0x210;
    private const nint PersonsChild = 0x211;
    private const nint MissionsWindow = 0x320;
    private static nint RootOf(nint window) => window == PersonsChild ? PersonsWindow : window;
    private static uint ProcessOf(nint window) => (uint)(window >> 4);

    private static WindowsUserInputPause.PersonWindowBook Book(nint front, long lastInput) =>
        WindowsUserInputPause.PersonWindowBook.Seeded(front, lastInput, RootOf, ProcessOf);

    // t-drag-2: the detector started with the person typing in front, and the first look came without their window.
    // Seeded when it starts, what came before it went to the root of the window in front, and to its process.
    [Test]
    public void TheDetectorSeedsTheWindowInFrontWithTheLastInputBeforeItStarted()
    {
        WindowsUserInputPause.PersonWindowBook book = Book(PersonsChild, lastInput: 5_000);

        Assert.Multiple(() =>
        {
            Assert.That(book.AgoMs(tells: true, PersonsWindow, now: 5_040), Is.EqualTo(40), "the root of the window in front");
            Assert.That(book.ProcessesAgoMs(tells: true, now: 5_040, ProcessOf(PersonsWindow)), Is.EqualTo(40));
            Assert.That(book.AgoMs(tells: true, MissionsWindow, now: 5_040), Is.Null, "another window is not the person's");
        });
    }

    // Contracases: without Raw Input no window of the person is told (the seed is not made up into one); with nothing in
    // front, no window is the person's.
    [Test]
    public void WithoutRawInputOrWithNothingInFrontNoWindowIsThePersons()
    {
        WindowsUserInputPause.PersonWindowBook book = Book(PersonsWindow, lastInput: 5_000);
        WindowsUserInputPause.PersonWindowBook none = Book(front: 0, lastInput: 5_000);

        Assert.Multiple(() =>
        {
            Assert.That(book.AgoMs(tells: false, PersonsWindow, now: 5_040), Is.Null);
            Assert.That(book.ProcessesAgoMs(tells: false, now: 5_040, ProcessOf(PersonsWindow)), Is.Null);
            Assert.That(none.AgoMs(tells: true, PersonsWindow, now: 5_040), Is.Null);
            Assert.That(none.AgoMs(tells: true, 0, now: 5_040), Is.Null);
        });
    }

    // t-drag-2: the simulated person typed VK_PACKET characters, which Raw Input never delivers, into the window in front.
    // The input the self-check counts as theirs went there: that window is now theirs, with that time.
    [Test]
    public void AnInputTheDetectorMissedMakesTheWindowInFrontThePersons()
    {
        WindowsUserInputPause.PersonWindowBook book = Book(MissionsWindow, lastInput: 1_000);
        var check = new WindowsUserInputPause.MissedInputCheck();

        long reconciled = WindowsUserInputPause.SelfCheck(
            check, book, foreign: 1_000, own: 900, windows: 5_000, now: 5_300, helperSending: false, () => PersonsChild);

        Assert.Multiple(() =>
        {
            Assert.That(reconciled, Is.EqualTo(5_000));
            Assert.That(book.AgoMs(tells: true, PersonsWindow, now: 5_300), Is.EqualTo(300));
            Assert.That(book.AgoMs(tells: true, MissionsWindow, now: 5_300), Is.Null, "the earlier window is no longer theirs");
            Assert.That(book.ProcessesAgoMs(tells: true, now: 5_300, ProcessOf(PersonsWindow)), Is.EqualTo(300));
        });
    }

    // Contracase: BAXY's own Unicode typing into the mission's window in front, noted when sent (NoteOwnUndelivered,
    // here «own»), never makes that window the person's; their window and its time stay as they were.
    [Test]
    public void BaxysOwnUnicodeTypingNeverMakesTheWindowInFrontThePersons()
    {
        WindowsUserInputPause.PersonWindowBook book = Book(PersonsWindow, lastInput: 2_000);
        var check = new WindowsUserInputPause.MissedInputCheck();
        long foreign = 2_000;
        int asked = 0;
        for (int key = 0; key < 40; key++)
        {
            long now = 10_005 + key * 36;
            long windows = key == 0 ? 10_000 : now - 36;
            foreign = Math.Max(foreign, WindowsUserInputPause.SelfCheck(
                check, book, foreign, own: windows + 1, windows, now, helperSending: false, () => { asked++; return MissionsWindow; }));
        }

        Assert.Multiple(() =>
        {
            Assert.That(foreign, Is.EqualTo(2_000));
            Assert.That(asked, Is.Zero, "no input was missed, so no window in front was taken");
            Assert.That(book.AgoMs(tells: true, MissionsWindow, now: 11_500), Is.Null);
            Assert.That(book.ProcessesAgoMs(tells: true, now: 11_500, ProcessOf(MissionsWindow)), Is.Null);
            Assert.That(book.AgoMs(tells: true, PersonsWindow, now: 11_500), Is.EqualTo(9_500));
        });
    }

    // Contracase: an older note never replaces a newer one (a missed input reconciled after the detector saw a newer
    // input elsewhere).
    [Test]
    public void AnOlderNoteNeverReplacesANewerOne()
    {
        WindowsUserInputPause.PersonWindowBook book = Book(PersonsWindow, lastInput: 5_000);
        book.Note(MissionsWindow, at: 4_000);

        Assert.Multiple(() =>
        {
            Assert.That(book.AgoMs(tells: true, PersonsWindow, now: 5_100), Is.EqualTo(100));
            Assert.That(book.AgoMs(tells: true, MissionsWindow, now: 5_100), Is.Null);
        });
    }

    // t-drag-2: the person types VK_PACKET characters at 8 a second into their window in front, and the mission's first
    // look reads the detector once, 350 ms in. Read only then, the self-check had first met that input at that read and
    // could not count it yet: no window of the person. Checked on the detector's own timer every SelfCheckMs, it had.
    [Test]
    public void TheSelfCheckOnItsOwnTimerKnowsThePersonsWindowAtTheFirstLook()
    {
        long? Look(bool timer)
        {
            WindowsUserInputPause.PersonWindowBook book = Book(front: 0, lastInput: 1_000);
            var check = new WindowsUserInputPause.MissedInputCheck();
            long foreign = 1_000;
            long look = 5_350;
            for (long now = 5_000; timer && now < look; now += WindowsUserInputPause.SelfCheckMs)
                foreign = Math.Max(foreign, WindowsUserInputPause.SelfCheck(
                    check, book, foreign, own: 900, windows: now - now % 125, now, helperSending: false, () => PersonsChild));
            _ = WindowsUserInputPause.SelfCheck(
                check, book, foreign, own: 900, windows: look - look % 125, look, helperSending: false, () => PersonsChild);
            return book.AgoMs(tells: true, PersonsWindow, look);
        }

        Assert.Multiple(() =>
        {
            Assert.That(Look(timer: false), Is.Null, "the measured defect: read once, too early to count it");
            Assert.That(Look(timer: true), Is.Not.Null.And.LessThan(500), "the person's window at the first look");
        });
    }

    // The detector's wiring of the three, which only a desktop runs: the seed in its constructor, the self-check that
    // marks the window in front on every read, and the timer that runs it with nobody reading. Removing one turns this
    // red instead of letting t-drag-2 come back live with the suite green.
    [Test]
    public void TheDetectorSeedsItsBookChecksOnEveryReadAndOnItsOwnTimer()
    {
        string source = File.ReadAllText(Path.Combine(
            RepositoryRoot(), "src", "Baxy.Providers.Windows", "External", "UserInputPause.cs"));

        Assert.Multiple(() =>
        {
            Assert.That(source, Does.Match(@"_book = PersonWindowBook\.Seeded\(GetForegroundWindow\(\), _lastForeign,"), "the seed");
            Assert.That(source, Does.Match(@"reconciled = SelfCheck\(\s*_selfCheck, _book,[^;]*\bFront\);"), "every read");
            Assert.That(source, Does.Match(@"private static nint Front\(\) => GetForegroundWindow\(\);"), "the window in front");
            Assert.That(source, Does.Match(@"SetTimer\(window, \d+, SelfCheckMs, 0\);\s*(//[^\n]*\n\s*)*_ = SetThreadDpiAwareness"), "the timer");
            Assert.That(source, Does.Match(@"message == WmTimer\)\s*_watching\?\.SelfCheckTick\(\);"), "its tick");
            Assert.That(source, Does.Match(@"void SelfCheckTick\(\) => _ = LastForeignInputMs;"), "the tick reads");
        });
    }

    // While a helper process of BAXY runs (its Unicode keys cannot be noted from this process), missed input is not
    // escalated across reads; once it ended, the person's own Unicode typing is seen while it goes on, as before.
    [Test]
    public void WhileAHelperSendsMissedInputIsNotEscalatedAcrossReadsAndAfterwardsItIs()
    {
        var check = new WindowsUserInputPause.MissedInputCheck();
        long during = 4_000;
        for (long now = 5_000; now <= 6_000; now += 40)
            during = Math.Max(during, check.Reconcile(during, own: 3_000, windows: now - now % 36, now, helperSending: true));
        long afterwards = during;
        for (long now = 6_040; now <= 7_000; now += 50)
            afterwards = Math.Max(afterwards, check.Reconcile(afterwards, own: 3_000, windows: now - now % 125, now));

        Assert.Multiple(() =>
        {
            Assert.That(during, Is.EqualTo(4_000), "a helper's own Unicode keys are not the person's");
            Assert.That(afterwards, Is.GreaterThan(6_000), "the person's typing after it is seen while it goes on");
        });
    }

    // The census of the note: every injector under src/ that sends Unicode keys from this process says so to the pause
    // detector, in the same file (the helpers' scripts run under LeasedInput.WatchHelperAsync instead).
    [Test]
    public void EveryInProcessUnicodeSenderNotesItsKeysAsBaxys()
    {
        string source = Path.Combine(RepositoryRoot(), "src");
        var silent = new List<string>();
        foreach (string file in Directory.EnumerateFiles(source, "*.cs", SearchOption.AllDirectories))
        {
            if (file.Contains(Path.DirectorySeparatorChar + "obj" + Path.DirectorySeparatorChar, StringComparison.Ordinal))
                continue;
            string text = File.ReadAllText(file);
            if (text.Contains("SendInput(", StringComparison.Ordinal) && UnicodeKey().IsMatch(text)
                && !text.Contains("WindowsUserInputPause.NoteOwnUndelivered()", StringComparison.Ordinal))
            {
                silent.Add(Path.GetFileName(file));
            }
        }

        Assert.That(silent, Is.Empty);
    }

    [GeneratedRegex(@"Flags\s*=\s*(Unicode\b|4U\b)|\(0,\s*\w+\[\w+\],\s*Unicode\)")]
    private static partial Regex UnicodeKey();

    // What may act past the window in front (review r2 of interrupcion-fantasma): a press or the wheel, Alt or a Windows
    // key going down, a media, browser or launch key going down. Contracases: a bare move, a letter, Alt going up.
    [Test]
    public void WhatActsBeyondTheFrontIsAPressAWheelASwitchKeyOrAMediaKey()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsUserInputPause.ActsBeyondFront(Mouse(buttons: 0x0001), Header), Is.True, "left down");
            Assert.That(WindowsUserInputPause.ActsBeyondFront(Mouse(buttons: 0x0400), Header), Is.True, "wheel");
            Assert.That(WindowsUserInputPause.ActsBeyondFront(KeyEvent(0x12, up: false), Header), Is.True, "Alt");
            Assert.That(WindowsUserInputPause.ActsBeyondFront(KeyEvent(0x5B, up: false), Header), Is.True, "Win");
            Assert.That(WindowsUserInputPause.ActsBeyondFront(KeyEvent(0xB3, up: false), Header), Is.True, "play/pause");
            Assert.That(WindowsUserInputPause.ActsBeyondFront(KeyEvent(0xAF, up: false), Header), Is.True, "volume up");
            Assert.That(WindowsUserInputPause.ActsBeyondFront(Mouse(buttons: 0), Header), Is.False, "bare move");
            Assert.That(WindowsUserInputPause.ActsBeyondFront(KeyEvent(0x41, up: false), Header), Is.False, "a letter");
            Assert.That(WindowsUserInputPause.ActsBeyondFront(KeyEvent(0x12, up: true), Header), Is.False, "Alt up");
        });
    }

    // Review r2 (menor): whether the point under the cursor may show the mission's window says true when it cannot be
    // told (no window there, or the point not in physical pixels); a window of another application there says false.
    [Test]
    public void APointThatCannotBeToldMayShowTheWindow()
    {
        nint mission = 0x100;
        nint other = 0x200;
        nint popup = 0x300;
        nint Root(nint hwnd) => hwnd;
        nint Owner(nint hwnd) => hwnd == popup ? mission : 0;

        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.MayShow(mission, 0, 0, physical: true, Root, Owner), Is.True, "no window");
            Assert.That(VisibleControlSurface.MayShow(mission, 0, other, physical: false, Root, Owner), Is.True, "not physical");
            Assert.That(VisibleControlSurface.MayShow(mission, 0, popup, physical: true, Root, Owner), Is.True, "its pop-up");
            Assert.That(VisibleControlSurface.MayShow(mission, 0, other, physical: true, Root, Owner), Is.False, "another app");
        });
    }

    private static byte[] Mouse(ushort buttons)
    {
        byte[] record = new byte[Header + 24];
        BinaryPrimitives.WriteUInt32LittleEndian(record, 0);
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(Header + 4), buttons);
        return record;
    }

    private static byte[] KeyEvent(ushort virtualKey, bool up)
    {
        byte[] record = new byte[Header + 16];
        BinaryPrimitives.WriteUInt32LittleEndian(record, 1);
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(Header + 2), (ushort)(up ? 1 : 0));
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(Header + 6), virtualKey);
        return record;
    }

    /// <summary>
    /// Every synthetic key and mouse event under <c>src/</c> carries BAXY's mark, judged call by call (review of
    /// fable/cu-v3-pausa: one marked call used to clear the whole file): no SendKeys of any kind (it cannot carry a
    /// mark), every mouse_event and keybd_event passes the mark as its extra, and every SendInput call is in a method
    /// that writes the mark or builds its records with one that does (or, when it only forwards records, every method
    /// that calls it does).
    /// </summary>
    [Test]
    public void EveryInjectorUnderSrcCarriesBaxysMark()
    {
        string source = Path.Combine(RepositoryRoot(), "src");
        var unmarkable = new List<string>();
        var unmarkedExtra = new List<string>();
        var unmarkedSend = new List<string>();
        foreach (string file in Directory.EnumerateFiles(source, "*.*", SearchOption.AllDirectories))
        {
            if (!(file.EndsWith(".cs", StringComparison.Ordinal) || file.EndsWith(".ps1", StringComparison.Ordinal))
                || file.Contains(Path.DirectorySeparatorChar + "obj" + Path.DirectorySeparatorChar, StringComparison.Ordinal)
                || file.Contains(Path.DirectorySeparatorChar + "bin" + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            {
                continue;
            }

            string text = WithMarkConstants(File.ReadAllText(file));
            string name = Path.GetFileName(file);
            foreach (Match call in SendKeys().Matches(text))
                unmarkable.Add(name + ": " + call.Value);
            if (!Injects().IsMatch(text))
                continue;
            unmarkedExtra.AddRange(UnmarkedEventCalls(text).Select(call => name + ": " + call));
            unmarkedSend.AddRange(UnmarkedSendInputCalls(text).Select(line => name + ":" + line));
        }

        Assert.Multiple(() =>
        {
            Assert.That(unmarkable, Is.Empty, "SendKeys cannot carry BAXY's mark");
            Assert.That(unmarkedExtra, Is.Empty, "mouse_event/keybd_event calls without BAXY's mark as their extra");
            Assert.That(unmarkedSend, Is.Empty, "SendInput calls whose records are not marked");
        });
    }

    // Contracases of the census itself: a marked file with one more unmarked call, and a SendKeys, are caught.
    [Test]
    public void TheCensusJudgesEachCallNotTheFile()
    {
        const string mixed = """
            static void Marked(Input[] inputs) { inputs[0].Extra = new UIntPtr(0x42415859u); }
            public static void Good(int x) { mouse_event(2, 0, 0, 0, Mark); }
            public static void Bad(int x) { mouse_event(4, 0, 0, 0, UIntPtr.Zero); }
            public static uint Plain(char c)
            {
                Input[] inputs = new Input[1];
                inputs[0].Type = 1;
                return SendInput(1, inputs, 40);
            }
            public static uint Wrapped(Input[] inputs)
            {
                return SendInput(1, Marked(inputs), 40);
            }
            """;

        // A constant that holds the mark marks as the mark does (the worker's SendBid, f56793c06); one with another
        // value does not.
        const string named = """
            private const uint BaxyMark = 0x42415859;
            private const uint Other = 0x1;
            private static bool SendBid(bool release) {
              keys[0].Type = 1; keys[0].Extra = new IntPtr(BaxyMark);
              return SendInput(1, keys, 40) == 1;
            }
            private static bool SendOther(bool release) {
              keys[0].Type = 1; keys[0].Extra = new IntPtr(Other);
              return SendInput(1, keys, 40) == 1;
            }
            """;

        Assert.Multiple(() =>
        {
            Assert.That(UnmarkedSendInputCalls(WithMarkConstants(named)), Is.EqualTo(new[] { 9 }));
            Assert.That(UnmarkedEventCalls(mixed), Has.Count.EqualTo(1));
            Assert.That(UnmarkedSendInputCalls(mixed), Has.Count.EqualTo(1));
            Assert.That(SendKeys().IsMatch("[System.Windows.Forms.SendKeys]::SendWait('^k')"), Is.True);
            Assert.That(SendKeys().IsMatch("$shell.SendKeys('{ESC}')"), Is.True);
            Assert.That(SendKeys().IsMatch("private async ValueTask<X> SendKeysAsync("), Is.False);
        });
    }

    // A named constant whose value is BAXY's mark is read as the mark itself.
    private static string WithMarkConstants(string text)
    {
        foreach (Match constant in MarkConstant().Matches(text))
            text = Regex.Replace(text, @"\b" + Regex.Escape(constant.Groups["name"].Value) + @"\b", "0x42415859");
        return text;
    }

    [GeneratedRegex(@"\bconst\s+\w+\s+(?<name>\w+)\s*=\s*0x42415859u?\s*;")]
    private static partial Regex MarkConstant();

    private static List<string> UnmarkedEventCalls(string text)
    {
        var found = new List<string>();
        foreach (Match call in EventCall().Matches(text))
        {
            string arguments = call.Groups["args"].Value;
            string last = arguments[(arguments.LastIndexOf(',') + 1)..].Trim();
            // A declaration names the parameter's type; a call passes a value, which must be the mark.
            if (DeclaredParameter().IsMatch(last) || MarkMention().IsMatch(last))
                continue;
            found.Add(call.Value);
        }

        return found;
    }

    // Each SendInput call is judged by the method around it: from the nearest method declaration above it to the call.
    private static List<int> UnmarkedSendInputCalls(string text)
    {
        string[] lines = text.Split('\n');
        var starts = new List<(int Line, string Name)>();
        for (int index = 0; index < lines.Length; index++)
        {
            Match declaration = MethodDeclaration().Match(lines[index]);
            if (declaration.Success)
                starts.Add((index, declaration.Groups["name"].Value));
        }

        string Body(int start)
        {
            int end = lines.Length;
            foreach ((int line, _) in starts)
            {
                if (line > start)
                {
                    end = line;
                    break;
                }
            }

            return string.Join('\n', lines[start..end]);
        }

        var marking = new HashSet<string>(StringComparer.Ordinal);
        foreach ((int line, string name) in starts)
        {
            if (MarkMention().IsMatch(Body(line)))
                marking.Add(name);
        }

        bool Marks(string body) =>
            MarkMention().IsMatch(body)
            || marking.Any(name => Regex.IsMatch(body, @"\b" + Regex.Escape(name) + @"\s*\("));

        var unmarked = new List<int>();
        for (int index = 0; index < lines.Length; index++)
        {
            if (!SendInputCall().IsMatch(lines[index]) || Declaration().IsMatch(lines[index]))
                continue;
            int owner = starts.Where(start => start.Line <= index).Select(start => start.Line).DefaultIfEmpty(-1).Max();
            if (owner < 0)
            {
                unmarked.Add(index + 1);
                continue;
            }

            string ownerName = starts.First(start => start.Line == owner).Name;
            string body = string.Join('\n', lines[owner..(index + 1)]);
            if (Marks(body))
                continue;
            // A method that only forwards records: every method that calls it must build them marked.
            List<(int Line, string Name)> callers = starts
                .Where(start => start.Line != owner
                    && Regex.IsMatch(Body(start.Line), @"\b" + Regex.Escape(ownerName) + @"\s*\("))
                .ToList();
            if (callers.Count == 0 || callers.Any(caller => !Marks(Body(caller.Line))))
                unmarked.Add(index + 1);
        }

        return unmarked;
    }

    [Test]
    public void TheMarkIsBaxyInAscii() =>
        Assert.That(BaxyInputMark.Value, Is.EqualTo(BinaryPrimitives.ReadUInt32BigEndian("BAXY"u8)));

    // Round 1 integration: the live harness's annoyance meter (scripts/cu_live/molestia/w32.py) tells BAXY's input by
    // the same mark in another process and language; this keeps the two in step instead of trusting a copy.
    [Test]
    public void TheAnnoyanceMeterReadsTheProductsMark()
    {
        string w32 = File.ReadAllText(Path.Combine(RepositoryRoot(), "scripts", "cu_live", "molestia", "w32.py"));
        Match mark = Regex.Match(w32, @"^BAXY_MARK\s*=\s*0x(?<hex>[0-9A-Fa-f_]+)", RegexOptions.Multiline);

        Assert.That(mark.Success, Is.True, "w32.py declares BAXY_MARK");
        Assert.That(
            uint.Parse(mark.Groups["hex"].Value.Replace("_", string.Empty, StringComparison.Ordinal), NumberStyles.HexNumber, CultureInfo.InvariantCulture),
            Is.EqualTo(BaxyInputMark.Value));
    }

    // A file that declares or calls one of the three Win32 injectors (prose that only names them has no parenthesis).
    [GeneratedRegex(@"\b(SendInput|mouse_event|keybd_event)\s*\(")]
    private static partial Regex Injects();

    [GeneratedRegex(@"\[System\.Windows\.Forms\.SendKeys\]::Send|\bSendKeys\s*\.\s*Send(Wait)?\s*\(|\.SendKeys\s*\(")]
    private static partial Regex SendKeys();

    [GeneratedRegex(@"\b(mouse_event|keybd_event)\s*\((?<args>[^;()]*(\([^;()]*\)[^;()]*)*)\)")]
    private static partial Regex EventCall();

    [GeneratedRegex(@"^(UIntPtr|nuint|IntPtr|nint)\s+\w+$")]
    private static partial Regex DeclaredParameter();

    [GeneratedRegex(@"BaxyInputMark\.Value|0x42415859|\bMark\b")]
    private static partial Regex MarkMention();

    [GeneratedRegex(@"\bSendInput\s*\(")]
    private static partial Regex SendInputCall();

    [GeneratedRegex(@"\bextern\b|\bpartial\b")]
    private static partial Regex Declaration();

    [GeneratedRegex(@"^\s*(\[[^\]]*\]\s*)*((public|private|internal|protected|static|unsafe|extern|partial|readonly|async|override)\s+)+[\w<>\[\],.?]+\s+(?<name>\w+)\s*\(")]
    private static partial Regex MethodDeclaration();

    private static byte[] Record(uint type, uint extra)
    {
        var record = new byte[Header + 24];
        BinaryPrimitives.WriteUInt32LittleEndian(record, type);
        int offset = type == 0 ? Header + 20 : Header + 12;
        BinaryPrimitives.WriteUInt32LittleEndian(record.AsSpan(offset), extra);
        return record;
    }

    private static byte[] Key(ushort virtualKey, long device)
    {
        var record = new byte[Header + 24];
        BinaryPrimitives.WriteUInt32LittleEndian(record, 1);
        if (IntPtr.Size == 8)
            BinaryPrimitives.WriteInt64LittleEndian(record.AsSpan(8), device);
        else
            BinaryPrimitives.WriteInt32LittleEndian(record.AsSpan(8), (int)device);
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(Header + 6), virtualKey);
        return record;
    }

    private static string RepositoryRoot()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            directory = directory.Parent;
        return directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found.");
    }
}
