using System.Buffers.Binary;
using System.Text.Json;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The foreground lease's round 4 mechanics (r4a molestia.md and regresiones.md) on a fake clock, a fake pause detector
/// and a fake desktop whose hand-backs really move the front: a keyboard text whole in the person's pause (c6), a
/// mission's window taken to the front and kept there for its acts (estabilización D, which replaced the sequences
/// held for a look, g1 and s11), a front asked for again when something took it back (w1), and the opening's guard
/// deciding by who moved the front (M2).
/// </summary>
[TestFixture]
public sealed class ForegroundSequenceTests
{
    // 18016 in the steps' JSON.
    private const nint Mission = 0x4660;
    private const nint Person = 0x1111;
    private const nint Other = 0x2222;

    // r4a M1 (c6) on the real lease: the next burst used to be asked for while the window still held the front, and
    // the previous burst's restore then handed it to the person; the text stopped at its 8th character.
    [Test]
    public async Task AFourteenCharacterTextArrivesWholeWithItsWindowInFrontAtEveryCharacter()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop();
        var keyboard = new LeaseKeyboard(Lease(new Pause(), clock, desktop), desktop);

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"prueba B mundo","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(string.Concat(keyboard.Typed), Is.EqualTo("prueba B mundo"));
            Assert.That(keyboard.InFrontAtEachCharacter, Is.All.True);
            Assert.That(keyboard.Typed, Has.Count.InRange(1, 2));
        });
    }

    // Contracase (review of fable/cu-v3-rafaga): the person types between two characters while the mission's window
    // holds the front: their key went into the mission's field, mixed with the text. The text ends there, interrupted
    // with its effect and never verified; the front is theirs at once and the window is not brought up again.
    [Test]
    public async Task ThePersonTypingInTheMiddleEndsTheTextAsInterruptedAndGetsTheFrontBack()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause();
        var desktop = new Desktop();
        var keyboard = new LeaseKeyboard(Lease(pause, clock, desktop), desktop)
        {
            EachCharacter = typed =>
            {
                if (typed == 5 && pause.LastForeignInputMs < 10_000)
                    pause.LastForeignInputMs = clock.NowMs + 1;
            },
        };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"prueba B mundo","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Typed, Is.EqualTo(new[] { "prueb" }));
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission }), "not brought up again over the person");
        });
    }

    // r4a M1 (c6): a bare move of the person's mouse reaches no field: the front is theirs at once, and the rest of
    // the text waits for their pause; nothing of the text goes to their window.
    [Test]
    public async Task ThePersonMovingTheMouseInTheMiddleGetsTheFrontBackAndTheRestWaitsForTheirPause()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause { Reaching = 2_000 };
        var desktop = new Desktop();
        var keyboard = new LeaseKeyboard(Lease(pause, clock, desktop), desktop)
        {
            EachCharacter = typed =>
            {
                if (typed == 5 && pause.LastForeignInputMs < 10_000)
                    pause.LastForeignInputMs = clock.NowMs + 1;
            },
        };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"prueba B mundo","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.Typed, Is.EqualTo(new[] { "prueb", "a B mundo" }));
            Assert.That(desktop.GivenFront, Does.Contain(Person), "the front went back to the person in the middle");
            Assert.That(keyboard.InFrontAtEachCharacter, Is.All.True);
            Assert.That(receipt.Result?.GetProperty("waitedMs").GetInt64(), Is.GreaterThanOrEqualTo(500));
        });
    }

    // Contracase: the person clicked another window in the middle (the front is theirs): the text ends there and the
    // mission's window is not brought up over the window they chose.
    [Test]
    public async Task APersonWhoMovedTheFrontInTheMiddleKeepsIt()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause { Reaching = 2_000 };
        var desktop = new Desktop();
        var keyboard = new LeaseKeyboard(Lease(pause, clock, desktop), desktop)
        {
            EachCharacter = typed =>
            {
                if (typed == 5 && pause.LastForeignInputMs < 10_000)
                {
                    pause.LastForeignInputMs = clock.NowMs + 1;
                    desktop.Front = Other;
                }
            },
        };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"prueba B mundo","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(keyboard.Typed, Is.EqualTo(new[] { "prueb" }));
            Assert.That(desktop.Front, Is.EqualTo(Other));
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission }));
        });
    }

    // Only a key, a mouse button or the wheel can reach a field; a bare move of the mouse cannot.
    [TestCase(0, 0x0000, false, TestName = "reach: mouse move")]
    [TestCase(0, 0x0001, true, TestName = "reach: left button down")]
    [TestCase(0, 0x0400, true, TestName = "reach: wheel")]
    [TestCase(1, 0x0000, true, TestName = "reach: a key down")]
    [TestCase(1, 0x0001, true, TestName = "reach: a key up")]
    public void OnlyAnInputThatCanReachAFieldIsTold(int type, int flags, bool reaches)
    {
        int header = 8 + 2 * IntPtr.Size;
        byte[] record = new byte[header + 24];
        BinaryPrimitives.WriteUInt32LittleEndian(record, (uint)type);
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(header + (type == 0 ? 4 : 2)), (ushort)flags);

        Assert.That(WindowsUserInputPause.ReachesContent(record, header), Is.EqualTo(reaches));
    }

    // Estabilización D (the owner's decision of 2026-10-10, «no molestar» in its simple form): a mission's act takes
    // its window's front after the person's pause and keeps it (nothing given back, the cursor untouched); the next act
    // on it waits for nothing and brings nothing up. Before (r4a M2, g1), a key's front was held only for the look after
    // it, up to 1.5 s, and then given back.
    [Test]
    public async Task AMissionsActTakesItsWindowsFrontAndKeepsIt()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { CursorAt = (40, 50) };
        ForegroundLease lease = Lease(new Pause(), clock, desktop);

        string? first = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        long afterFirst = clock.NowMs;
        string? second = await lease.TakeForMissionAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.Null);
            Assert.That(second, Is.Null);
            Assert.That(clock.NowMs, Is.EqualTo(afterFirst), "a window in front waits for nothing");
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission }), "brought up once");
            Assert.That(desktop.Front, Is.EqualTo(Mission));
            Assert.That(desktop.GivenFront, Is.Empty);
            Assert.That(desktop.CursorAt, Is.EqualTo((40, 50)));
        });
    }

    // The person's pause first (the lease's own wait, reused): an input of theirs 100 ms ago is waited out before the
    // window comes up, so no key of theirs lands in the mission's window.
    [Test]
    public async Task AMissionsActWaitsForThePersonsPauseBeforeTakingTheFront()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause { LastForeignInputMs = 9_900 };
        var desktop = new Desktop();

        string? taken = await Lease(pause, clock, desktop).TakeForMissionAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(taken, Is.Null);
            Assert.That(clock.NowMs - pause.LastForeignInputMs, Is.GreaterThanOrEqualTo(ForegroundLease.QuietMs));
            Assert.That(desktop.Front, Is.EqualTo(Mission));
        });
    }

    // Contracases: a person who never pauses (the wait has its ceiling), and a window that never takes the front (asked
    // only within FrontTakeCapMs), get nothing taken and nothing sent: the person's window keeps the front.
    [Test]
    public async Task AMissionsActTakesNothingFromAPersonWhoNeverPausesNorForAWindowThatNeverComes()
    {
        var clock = new Clock { NowMs = 10_000 };
        var typing = new Desktop();
        string? notPaused = await new ForegroundLease(new TypingPause(clock), clock, typing, maxWaitMs: 2_000)
            .TakeForMissionAsync(Mission, CancellationToken.None);
        var stubborn = new Desktop { Clock = clock, BringingCostsMs = 600, NeverTakes = true };
        // Revisión D (H5): the bid for the right is tried once, and Windows still gives the front back to the person.
        stubborn.OnGiveFront = () => stubborn.Front = Person;
        string? notInFront = await Lease(new Pause(), clock, stubborn).TakeForMissionAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(notPaused, Is.EqualTo("input_user_not_paused"));
            Assert.That(typing.Fronted, Is.Empty);
            Assert.That(typing.Front, Is.EqualTo(Person));
            Assert.That(notInFront, Is.EqualTo("input_window_not_in_front"));
            Assert.That(stubborn.Fronted, Has.Count.EqualTo(2), "asked again only inside the bound");
            Assert.That(stubborn.GivenFront, Is.EqualTo(new[] { Mission }), "one bid, after the bound");
            Assert.That(stubborn.Front, Is.EqualTo(Person));
        });
    }

    // Revisión D (H1): the person's input that can reach a window (a key, a mouse button, the wheel) after the take gives
    // their window the front back at once, and the next act waits for a new pause and brings the mission's up again.
    // Contracase: a person who stays still keeps the mission's window in front for the look.
    [Test]
    public async Task ThePersonsInputAfterTheTakeGivesThemTheFrontBackAndTheNextActWaitsForTheirPause()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause();
        var desktop = new Desktop();
        var lease = new ForegroundLease(pause, clock, desktop, maxWaitMs: 8_000, watchMission: false);

        _ = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        lease.MissionActEnded("input.visible.click");
        clock.NowMs += 300;
        bool keptWhileStill = !lease.CheckMissionFront() && desktop.Front == Mission;
        pause.Reaching = clock.NowMs;
        pause.LastForeignInputMs = clock.NowMs;
        bool givenBack = lease.CheckMissionFront();
        nint frontAfterTheirKey = desktop.Front;
        long before = clock.NowMs;
        string? again = await lease.TakeForMissionAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(keptWhileStill, Is.True);
            Assert.That(givenBack, Is.True);
            Assert.That(frontAfterTheirKey, Is.EqualTo(Person));
            Assert.That(desktop.GivenFront, Is.EqualTo(new[] { Person }));
            Assert.That(again, Is.Null);
            Assert.That(clock.NowMs - before, Is.GreaterThanOrEqualTo(ForegroundLease.QuietMs - 50), "their pause first");
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission, Mission }));
        });
    }

    // Revisión D (H1): a text never leaves its window in front while the next act is decided (an Enter of the person's
    // would send what BAXY wrote); a key or a click does. Without telling the person's input apart, no act leaves it.
    [TestCase("input.text.type", true, true)]
    [TestCase("input.key.press", true, false)]
    [TestCase("input.visible.click", true, false)]
    [TestCase("input.visible.click", false, true)]
    public async Task ATextNeverLeavesItsWindowInFrontNorAnyActWithoutTellingThePersonApart(
        string operation, bool tells, bool givenBack)
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop();
        var lease = new ForegroundLease(new Pause { Tells = tells }, clock, desktop, maxWaitMs: 8_000, watchMission: false);

        _ = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        lease.MissionActEnded(operation);

        Assert.That(desktop.Front, Is.EqualTo(givenBack ? Person : Mission));
    }

    // Encargo K (banco def1 x8, c2): a window just brought up took the keyboard a moment after the front, and the first
    // key sent at once was lost («125+75» → «25+75»; after the text gave the front back, the Enter brought it up again
    // and was lost too). Each fresh take waits until the window takes the keys; the window already in front waits for
    // nothing, as before.
    [Test]
    public async Task AWindowJustBroughtUpIsGivenTheKeyboardBeforeEachActAsInTheSequenceOfDef1()
    {
        var clock = new Clock { NowMs = 10_000 };
        long takesKeysAt = 0;
        var desktop = new Desktop { Clock = clock };
        desktop.OnBrought = () => takesKeysAt = clock.NowMs + 60;
        desktop.TakesKeysWhen = () => clock.NowMs >= takesKeysAt;
        var lease = new ForegroundLease(new Pause(), clock, desktop, maxWaitMs: 8_000, watchMission: false);

        long before = clock.NowMs;
        string? text = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        bool textGoesWithKeys = desktop.TakesKeysWhen();
        long textWaited = clock.NowMs - before;
        lease.MissionActEnded("input.text.type");
        nint frontAfterText = desktop.Front;

        clock.NowMs += 1_000;
        before = clock.NowMs;
        string? enter = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        bool enterGoesWithKeys = desktop.TakesKeysWhen();
        long enterWaited = clock.NowMs - before;
        lease.MissionActEnded("input.key.press");
        int askedBefore = desktop.KeysAsked;
        before = clock.NowMs;
        string? inFront = await lease.TakeForMissionAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(text, Is.Null);
            Assert.That(textGoesWithKeys, Is.True);
            Assert.That(textWaited, Is.InRange(60, 60 + 15));
            Assert.That(frontAfterText, Is.EqualTo(Person), "a text still gives the front back");
            Assert.That(enter, Is.Null);
            Assert.That(enterGoesWithKeys, Is.True, "the Enter after the text waits again");
            Assert.That(enterWaited, Is.InRange(60, 60 + 15));
            Assert.That(inFront, Is.Null);
            Assert.That(clock.NowMs, Is.EqualTo(before), "a window in front waits for nothing");
            Assert.That(desktop.KeysAsked, Is.EqualTo(askedBefore), "nor is it asked");
        });
    }

    // Encargo K, contracases: a window that never shows taking the keyboard is waited for only up to the bound, and the
    // act goes as it went before; a front the person moved elsewhere during the wait ends it at once, never fought.
    [Test]
    public async Task TheKeyboardsWaitIsBoundedAndEndsWhenTheFrontIsNoLongerTheMissions()
    {
        var clock = new Clock { NowMs = 10_000 };
        var never = new Desktop { Clock = clock, TakesKeysWhen = () => false };
        long before = clock.NowMs;
        string? bounded = await Lease(new Pause(), clock, never).TakeForMissionAsync(Mission, CancellationToken.None);
        long boundedWaited = clock.NowMs - before;

        var moved = new Desktop { Clock = clock, TakesKeysWhen = () => false };
        clock.OnDelay = () => moved.Front = Other;
        before = clock.NowMs;
        string? left = await Lease(new Pause(), clock, moved).TakeForMissionAsync(Mission, CancellationToken.None);
        long leftWaited = clock.NowMs - before;
        clock.OnDelay = null;

        Assert.Multiple(() =>
        {
            Assert.That(bounded, Is.Null);
            Assert.That(boundedWaited, Is.InRange(ForegroundLease.KeysReadyCapMs, ForegroundLease.KeysReadyCapMs + 15));
            Assert.That(never.Front, Is.EqualTo(Mission));
            Assert.That(left, Is.Null, "the act's own check refuses a window not in front");
            Assert.That(leftWaited, Is.LessThanOrEqualTo(15));
            Assert.That(moved.Front, Is.EqualTo(Other));
            Assert.That(moved.Fronted, Is.EqualTo(new[] { Mission }), "brought up once, never again over theirs");
            Assert.That(moved.GivenFront, Is.Empty);
        });
    }

    // Encargo K, contracase («no molestar»): a person typing in their window when the act comes gets nothing taken; the
    // keyboard's wait never starts and their window keeps the front.
    [Test]
    public async Task APersonTypingInTheirWindowKeepsItsFrontAndNoKeyboardIsAwaited()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { Clock = clock, TakesKeysWhen = () => false };

        string? refused = await new ForegroundLease(new TypingPause(clock), clock, desktop, maxWaitMs: 2_000)
            .TakeForMissionAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused, Is.EqualTo("input_user_not_paused"));
            Assert.That(desktop.Fronted, Is.Empty);
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(desktop.KeysAsked, Is.Zero);
        });
    }

    // Revisión D (H2): the mission ended (the turn was cancelled) while its act was in flight: the front goes back right
    // behind that act, never before it ends and never left with the mission's window; a later act of the ended mission
    // is never sent; a new mission gives the old one's front back.
    [Test]
    public async Task TheEndOfTheMissionGivesTheFrontBackBehindTheActInFlight()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop();
        var missions = new Missions { Generation = 1 };
        var lease = new ForegroundLease(new Pause(), clock, desktop, maxWaitMs: 8_000, missions, watchMission: false);

        _ = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        missions.Running = false;
        bool heldDuringTheAct = !lease.CheckMissionFront() && desktop.Front == Mission;
        lease.MissionActEnded("input.visible.click");
        bool givenAfter = lease.CheckMissionFront();
        string? late = await lease.TakeForMissionAsync(Mission, CancellationToken.None);

        missions.Running = true;
        _ = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        lease.MissionActEnded("input.visible.click");
        missions.Generation = 2;
        bool givenForTheNext = lease.CheckMissionFront();

        Assert.Multiple(() =>
        {
            Assert.That(heldDuringTheAct, Is.True);
            Assert.That(givenAfter, Is.True);
            Assert.That(late, Is.EqualTo("input_mission_ended"));
            Assert.That(givenForTheNext, Is.True);
            Assert.That(desktop.GivenFront, Is.EqualTo(new[] { Person, Person }));
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission, Mission }), "the late act brought nothing up");
        });
    }

    // Revisión D (H3): the person's window is the one in front after their pause (they switched while BAXY waited), and
    // a front another window took since is theirs: never fought.
    [Test]
    public async Task ThePersonsWindowIsReadAfterTheirPauseAndAFrontTheyMovedIsNotFought()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause { LastForeignInputMs = 9_900 };
        var desktop = new Desktop();
        clock.OnDelay = () => desktop.Front = Other;
        var lease = new ForegroundLease(pause, clock, desktop, maxWaitMs: 8_000, watchMission: false);

        _ = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        clock.OnDelay = null;
        lease.MissionActEnded("input.text.type");
        nint backTo = desktop.Front;

        _ = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        lease.MissionActEnded("input.visible.click");
        desktop.Front = Person;
        bool forgotten = lease.CheckMissionFront();
        lease.MissionActEnded("input.text.type");

        Assert.Multiple(() =>
        {
            Assert.That(backTo, Is.EqualTo(Other));
            Assert.That(forgotten, Is.True);
            Assert.That(desktop.GivenFront, Is.EqualTo(new[] { Other }), "nothing fought after the person moved the front");
        });
    }

    // Revisión D (H5): only a mission's take wins the right to set the foreground when the bringing does not hold
    // (ForegroundRight through GiveFront), once, after the bringing's own bound. A burst on a known window never bids
    // (estab G4: a helper's window brought up by its host takes the same path, next test).
    [Test]
    public async Task OnlyAMissionsTakeWinsTheRightOnceAfterTheBringingsBound()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { Clock = clock, BringingCostsMs = 600, NeverTakes = true };
        var lease = new ForegroundLease(new Pause(), clock, desktop, maxWaitMs: 8_000, watchMission: false);

        IInputBurst burst = await lease.AcquireAsync(Mission, CancellationToken.None);
        List<nint> givenByTheBurst = [.. desktop.GivenFront];
        string? taken = await lease.TakeForMissionAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.EqualTo("input_window_not_in_front"));
            Assert.That(givenByTheBurst, Is.Empty, "a burst never bids for the right");
            Assert.That(taken, Is.Null);
            Assert.That(desktop.GivenFront, Is.EqualTo(new[] { Mission }), "the mission's take bid once");
            Assert.That(desktop.Front, Is.EqualTo(Mission));
        });
    }

    // Estab G4: the media client's script could not bring its window up (spotify_foreground_not_verified); its host
    // brings it up within the helper's burst the way a mission's act takes it (the bringing, then one bid after its
    // bound), and the burst gives the person their front back when it ends. Contracases: once the person acted nothing
    // is brought, and a burst on a known window brings nothing else up.
    [Test]
    public async Task AHelpersWindowIsBroughtUpAsAMissionsAndItsBurstGivesThePersonTheirFrontBack()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { Clock = clock, BringingCostsMs = 600, NeverTakes = true };
        var pause = new Pause();
        var lease = new ForegroundLease(pause, clock, desktop, maxWaitMs: 8_000, watchMission: false);

        IInputBurst burst = await lease.AcquireForHelperAsync(CancellationToken.None);
        bool brought = await burst.BringUpAsync(Mission, CancellationToken.None);
        nint frontWhileRunning = desktop.Front;
        bool restored = burst.Restore();

        IInputBurst interrupted = await lease.AcquireForHelperAsync(CancellationToken.None);
        pause.LastForeignInputMs = clock.NowMs + 1;
        int frontedBefore = desktop.Fronted.Count;
        bool broughtOverThePerson = await interrupted.BringUpAsync(Mission, CancellationToken.None);
        _ = interrupted.Restore();
        pause.LastForeignInputMs = 2_000;
        IInputBurst known = await lease.AcquireAsync(Other, CancellationToken.None);
        bool broughtByAKnownWindow = await known.BringUpAsync(Mission, CancellationToken.None);
        _ = known.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(brought, Is.True);
            Assert.That(frontWhileRunning, Is.EqualTo(Mission));
            Assert.That(desktop.GivenFront.Take(2), Is.EqualTo(new[] { Mission, Person }), "one bid, then given back");
            Assert.That(restored, Is.True);
            Assert.That(broughtOverThePerson, Is.False);
            Assert.That(broughtByAKnownWindow, Is.False);
            Assert.That(desktop.Fronted.Skip(frontedBefore).Where(window => window == Mission), Is.Empty);
        });
    }

    // A burst never keeps a front it took: a text's and a key's both go back at once (before, a key's was held for its
    // look and its receipt said frontHeld), and a burst on the window the mission already holds in front gives nothing
    // back: the mission's front stays where it is.
    [Test]
    public async Task ABurstNeverKeepsTheFrontItTookAndLeavesTheMissionsFrontWhereItIs()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop();
        ForegroundLease lease = Lease(new Pause(), clock, desktop);
        var keyboard = new LeaseKeyboard(lease, desktop);

        ExternalCapabilityReceipt typed = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":18016}"""), CancellationToken.None);
        nint frontAfterText = desktop.Front;
        ExternalCapabilityReceipt pressed = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":18016}"""), CancellationToken.None);
        nint frontAfterKey = desktop.Front;
        string? taken = await lease.TakeForMissionAsync(Mission, CancellationToken.None);
        ExternalCapabilityReceipt inFront = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(typed.Verified, Is.True, typed.ErrorCode);
            Assert.That(pressed.Verified, Is.True, pressed.ErrorCode);
            Assert.That(inFront.Verified, Is.True, inFront.ErrorCode);
            Assert.That(frontAfterText, Is.EqualTo(Person));
            Assert.That(frontAfterKey, Is.EqualTo(Person));
            Assert.That(pressed.Result?.TryGetProperty("frontHeld", out _), Is.False);
            Assert.That(taken, Is.Null);
            Assert.That(desktop.Front, Is.EqualTo(Mission), "the mission's front stays with it");
        });
    }

    // Safety review r10a: without Raw Input a burst never stops for the person, so a long text would be typed whole over
    // them. It goes in short bursts instead, each after a pause of the session's input, with the front given back
    // between them; the text still arrives whole. Contracase: a detector that tells the person apart types it in one.
    [TestCase(false)]
    [TestCase(true)]
    public async Task WithoutTellingThePersonApartALongTextGoesInShortBursts(bool tells)
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { CursorAt = (40, 50) };
        ForegroundLease lease = Lease(new Pause { Tells = tells }, clock, desktop);
        var keyboard = new LeaseKeyboard(lease, desktop);
        const string text = "mañana a las 5 llevo pan";

        ExternalCapabilityReceipt typed = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"mañana a las 5 llevo pan","window":18016}"""), CancellationToken.None);

        int bursts = (text.Length + WindowsDesktopInteractionAdapter.BlindBurstCharacters - 1)
            / WindowsDesktopInteractionAdapter.BlindBurstCharacters;
        Assert.Multiple(() =>
        {
            Assert.That(typed.Verified, Is.True, typed.ErrorCode);
            Assert.That(string.Concat(keyboard.Typed), Is.EqualTo(text));
            Assert.That(keyboard.InFrontAtEachCharacter, Is.All.True);
            if (tells)
            {
                Assert.That(keyboard.Typed, Has.Count.EqualTo(1));
                Assert.That(desktop.Fronted, Has.Count.EqualTo(1));
            }
            else
            {
                Assert.That(keyboard.Typed, Has.All.Length.LessThanOrEqualTo(WindowsDesktopInteractionAdapter.BlindBurstCharacters));
                Assert.That(keyboard.Typed, Has.Count.EqualTo(bursts));
                Assert.That(desktop.Fronted, Has.Count.EqualTo(bursts), "the front was given back between bursts");
            }

            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(desktop.CursorAt, Is.EqualTo((40, 50)));
        });
    }

    // r4a M4 (w1): something handed the front back right after the lease brought the window up (the opening's guard):
    // the lease asks for it again instead of only looking, and wins.
    [Test]
    public async Task AFrontTakenBackRightAfterTheBringingIsAskedForAgain()
    {
        var desktop = new Desktop { TakenBackAfterBringing = 1 };

        IInputBurst burst = await Lease(new Pause(), new Clock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.Null);
            Assert.That(desktop.Front, Is.EqualTo(Mission));
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission, Mission }));
        });
    }

    // r4a M4 (w1): the lease brings a window up under the front's gate the guards read and hand back under.
    [Test]
    public async Task TheLeaseBringsAWindowUpOnlyOnceTheGuardLeftTheFrontsGate()
    {
        var desktop = new Desktop();
        ForegroundLease lease = Lease(new Pause(), new Clock { NowMs = 10_000 }, desktop);
        await ForegroundHandBack.FrontGate.WaitAsync();
        ValueTask<IInputBurst> acquiring;
        int frontedWhileGuardHeldTheGate;
        try
        {
            acquiring = lease.AcquireAsync(Mission, CancellationToken.None);
            await Task.Delay(50);
            frontedWhileGuardHeldTheGate = desktop.Fronted.Count;
        }
        finally
        {
            _ = ForegroundHandBack.FrontGate.Release();
        }

        IInputBurst burst = await acquiring;

        Assert.Multiple(() =>
        {
            Assert.That(frontedWhileGuardHeldTheGate, Is.Zero);
            Assert.That(burst.Refusal, Is.Null);
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission }));
        });
    }

    // r4a M2: only a mouse button or Alt or a Windows key going down can move the front; a letter typed, a key let go
    // or a mouse move cannot (the person typing in their own window does not make the opened application theirs).
    [TestCase(0, 0x0001, 0, true, TestName = "left button down")]
    [TestCase(0, 0x0004, 0, true, TestName = "right button down")]
    [TestCase(0, 0x0002, 0, false, TestName = "left button up")]
    [TestCase(0, 0x0000, 0, false, TestName = "mouse move")]
    [TestCase(1, 0x0000, 0x12, true, TestName = "Alt down")]
    [TestCase(1, 0x0000, 0x5B, true, TestName = "Windows key down")]
    [TestCase(1, 0x0001, 0x5B, false, TestName = "Windows key up")]
    [TestCase(1, 0x0000, 0x41, false, TestName = "a letter")]
    [TestCase(1, 0x0000, 0x0D, false, TestName = "Enter")]
    public void OnlyAnInputThatCanMoveTheFrontIsTold(int type, int flags, int key, bool moves)
    {
        int header = 8 + 2 * IntPtr.Size;
        byte[] record = new byte[header + 24];
        BinaryPrimitives.WriteUInt32LittleEndian(record, (uint)type);
        if (type == 0)
        {
            BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(header + 4), (ushort)flags);
        }
        else
        {
            BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(header + 2), (ushort)flags);
            BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(header + 6), (ushort)key);
        }

        Assert.That(WindowsUserInputPause.MovesFront(record, header), Is.EqualTo(moves));
    }

    // r4a M3: a pointer's burst is short. Its baseline is taken behind before the lease, no settle keeps the window in
    // front, and the front goes back right after the press, before any post-read.
    [Test]
    public async Task APointersBurstTakesItsBaselineBehindAndGivesTheFrontBackRightAfterThePress()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { CursorAt = (5, 5) };
        var pointer = new LeasePointer(Lease(new Pause(), clock, desktop), desktop);

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.True);
            Assert.That(pointer.Events, Is.EqualTo(new[] { "baseline behind", "press in front" }));
            Assert.That(desktop.Front, Is.EqualTo(Person), "given back before the caller's post-read");
            Assert.That(desktop.CursorAt, Is.EqualTo((5, 5)));
            Assert.That(clock.NowMs - 10_000, Is.LessThan(150), "no settle in front");
            Assert.That(pressed.Burst!.Restore(), Is.True, "the caller's restore only confirms it");
        });
    }

    // Safety review r10a: in front and inside its rectangle is not enough. A window of another application kept always
    // on top over the point (a picture-in-picture, a sticky note) would get the press: nothing is pressed, and the front
    // and the cursor go back.
    [Test]
    public async Task APointAnotherWindowCoversIsNeverPressed()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { CursorAt = (5, 5) };
        var pointer = new LeasePointer(Lease(new Pause(), clock, desktop), desktop) { ShownAt = new([Other]) };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.False);
            Assert.That(pressed.Refusal, Is.EqualTo("input_window_not_in_front"));
            Assert.That(pointer.PointsAsked, Is.EqualTo(new[] { (Mission, 100, 120) }));
            Assert.That(pointer.Events, Has.None.StartsWith("press"));
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(desktop.CursorAt, Is.EqualTo((5, 5)));
        });
    }

    // The point is asked again right before the press: a window that came over it after the first check gets nothing.
    // Contracase: a point that shows the mission's window both times is pressed.
    [Test]
    public async Task APointIsCheckedAgainRightBeforeThePress()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { CursorAt = (5, 5) };
        var covered = new LeasePointer(Lease(new Pause(), clock, desktop), desktop) { ShownAt = new([Mission, Other]) };
        PointerPressed late = await LocatedPointPress.PointerAsync(
            covered, Mission, 100, 120, null, null, CancellationToken.None);

        var clear = new LeasePointer(Lease(new Pause(), clock, desktop), desktop);
        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            clear, Mission, 100, 120, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(late.Pressed, Is.False);
            Assert.That(late.Refusal, Is.EqualTo("input_window_not_in_front"));
            Assert.That(covered.PointsAsked, Has.Count.EqualTo(2));
            Assert.That(covered.Events, Has.None.StartsWith("press"));
            Assert.That(pressed.Pressed, Is.True);
            Assert.That(clear.PointsAsked, Has.Count.EqualTo(2));
            Assert.That(clear.Events, Does.Contain("press in front"));
        });
    }

    // Contracase: the person acts between the bringing and the press: nothing is pressed and the front is theirs.
    [Test]
    public async Task APointerWhoseBurstThePersonInterruptedPressesNothing()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause();
        var desktop = new Desktop();
        var pointer = new LeasePointer(Lease(pause, clock, desktop), desktop)
        {
            BeforePress = () => pause.LastForeignInputMs = clock.NowMs + 1,
        };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.False);
            Assert.That(pressed.Refusal, Is.EqualTo("input_user_interrupted"));
            Assert.That(pointer.Events, Is.EqualTo(new[] { "baseline behind" }));
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    // Review of fable/cu-v3-rafaga: mouse_event is processed by Windows later; the front and the cursor go back only
    // once the detector saw the press and the release (Windows routed them), never before.
    [Test]
    public async Task APointersFrontGoesBackOnlyOnceItsPressAndReleaseWereRouted()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause();
        var desktop = new Desktop { CursorAt = (5, 5) };
        long pressedAt = 0;
        long frontBackAt = 0;
        desktop.OnGiveFront = () => frontBackAt = clock.NowMs;
        var pointer = new LeasePointer(Lease(pause, clock, desktop), desktop)
        {
            AfterPress = () =>
            {
                pressedAt = clock.NowMs;
                pause.OwnCount = () => clock.NowMs >= pressedAt + 30 ? 2 : 0;
            },
        };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.True);
            Assert.That(frontBackAt - pressedAt, Is.InRange(30, 40), "given back once both were routed");
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    // Contracase: inputs the detector never sees hold the front at most OwnInputSettleMs.
    [Test]
    public async Task APointersFrontGoesBackAtTheSettlesCapWhenItsInputIsNeverSeen()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { CursorAt = (5, 5) };
        long pressedAt = 0;
        long frontBackAt = 0;
        desktop.OnGiveFront = () => frontBackAt = clock.NowMs;
        var pointer = new LeasePointer(Lease(new Pause(), clock, desktop), desktop)
        {
            AfterPress = () => pressedAt = clock.NowMs,
        };

        _ = await LocatedPointPress.PointerAsync(pointer, Mission, 100, 120, null, null, CancellationToken.None);

        Assert.That(
            frontBackAt - pressedAt, Is.InRange(ForegroundLease.OwnInputSettleMs, ForegroundLease.OwnInputSettleMs + 10));
    }

    // Review of fable/cu-v3-rafaga: the person was working; the baseline is taken after their pause, right before the
    // burst, not seconds before it (a window redrawing by itself meanwhile would read as the press's effect).
    [Test]
    public async Task APointersBaselineIsTakenAfterThePersonsPause()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause { LastForeignInputMs = 10_000 };
        var desktop = new Desktop();
        var pointer = new LeasePointer(Lease(pause, clock, desktop), desktop) { Clock = clock };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.True);
            Assert.That(pointer.BaselineAt, Is.GreaterThanOrEqualTo(10_000 + ForegroundLease.QuietMs));
            Assert.That(pressed.Before, Is.Not.Null);
            Assert.That(pressed.WaitedMs, Is.GreaterThanOrEqualTo(ForegroundLease.QuietMs));
        });
    }

    // Contracase: the person acted between the baseline and the burst; without a point to find again, no image says
    // what the press changed, and none is handed to the post-read.
    [Test]
    public async Task APersonActingBetweenTheBaselineAndTheBurstLeavesNoBaseline()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause();
        var desktop = new Desktop();
        var pointer = new LeasePointer(Lease(pause, clock, desktop), desktop)
        {
            Clock = clock,
            AfterBaseline = () => pause.LastForeignInputMs = clock.NowMs,
        };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.True);
            Assert.That(pressed.Before, Is.Null);
        });
    }

    // fable/cu-v3-reintento-pausa (banco r6, s12: a burst of 559 ms in a pause of about 500): a point read before the
    // wait is checked on the window's own drawing and found again by OCR after the pause and before the burst; the
    // burst only brings the window up, presses and gives it back, so it fits in the person's pause.
    [Test]
    public async Task APointReadBeforeTheWaitIsCheckedAndFoundAgainBeforeTheBurst()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { CursorAt = (5, 5) };
        long pressedAt = 0;
        long frontBackAt = 0;
        nint frontWhileLocating = 0;
        desktop.OnGiveFront = () => frontBackAt = clock.NowMs;
        var pointer = new LeasePointer(Lease(new Pause(), clock, desktop), desktop)
        {
            Clock = clock,
            AfterPress = () => pressedAt = clock.NowMs,
        };
        var located = new VisibleControlSurface.CapturedWindow(Mission, [], 0, 0, 1, 1, "read") { SelfDrawn = true };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, located,
            (again, _) =>
            {
                frontWhileLocating = desktop.Front;
                clock.NowMs += 250;
                return ValueTask.FromResult<(int X, int Y)?>((130, 140));
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.True);
            Assert.That(frontWhileLocating, Is.EqualTo(Person), "the word is located again behind the person's window");
            Assert.That(pointer.Events, Is.EqualTo(new[] { "baseline behind", "press in front" }));
            Assert.That(desktop.CursorAt, Is.EqualTo((5, 5)));
            Assert.That(pointer.PressedAt, Is.EqualTo((130, 140)), "pressed where it was found again");
            Assert.That(pressed.Before?.Sha256, Is.EqualTo("base"), "the check's capture is the post-read's baseline");
            Assert.That(frontBackAt - pressedAt, Is.LessThanOrEqualTo(ForegroundLease.OwnInputSettleMs + 10));
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    // Contracase: the person acted between the check and the burst (the lease waited for a new pause): the read point
    // is checked again inside the burst before anything is pressed.
    [Test]
    public async Task APersonActingBetweenTheCheckAndTheBurstGetsThePointCheckedAgain()
    {
        var clock = new Clock { NowMs = 10_000 };
        var pause = new Pause();
        var desktop = new Desktop();
        int baselines = 0;
        var pointer = new LeasePointer(Lease(pause, clock, desktop), desktop)
        {
            Clock = clock,
            AfterBaseline = () =>
            {
                if (baselines++ == 0)
                    pause.LastForeignInputMs = clock.NowMs;
            },
        };
        var located = new VisibleControlSurface.CapturedWindow(Mission, [], 0, 0, 1, 1, "base") { SelfDrawn = true };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, located, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.True);
            Assert.That(pointer.Events, Is.EqualTo(new[] { "baseline behind", "baseline in front", "press in front" }));
            Assert.That(pressed.WaitedMs, Is.GreaterThanOrEqualTo(ForegroundLease.QuietMs));
        });
    }

    // Contracase: the window moved while the person's pause was waited for: nothing is brought up nor pressed.
    [Test]
    public async Task APointOnAWindowThatMovedWhileWaitingBringsNothingUp()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop();
        var pointer = new LeasePointer(Lease(new Pause(), clock, desktop), desktop) { Clock = clock };
        var located = new VisibleControlSurface.CapturedWindow(Mission, [], 40, 0, 1, 1, "base") { SelfDrawn = true };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, located, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.False);
            Assert.That(pressed.Refusal, Is.EqualTo(VisibleControlSurface.SurfaceChangedWhileWaiting));
            Assert.That(desktop.Fronted, Is.Empty);
        });
    }

    // Review of fable/cu-v3-reintento-pausa: a point read on a screen copy (a window nothing covered: the vision
    // locator's box, which is never located again) is checked on a screen copy, never on the window's own drawing,
    // which never matches a screen copy and would refuse every such press; the baseline is still the window's own
    // drawing, as the post-read reads it behind.
    [Test]
    public async Task APointReadOnAScreenCopyIsCheckedOnAScreenCopyAndPressed()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop();
        var pointer = new LeasePointer(Lease(new Pause(), clock, desktop), desktop) { Clock = clock, ScreenCopy = "copy" };
        var located = new VisibleControlSurface.CapturedWindow(Mission, [], 0, 0, 1, 1, "copy") { SelfDrawn = false };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, located, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.True);
            Assert.That(pointer.Events, Is.EqualTo(new[] { "screen copy behind", "baseline behind", "press in front" }));
            Assert.That(pressed.Before?.Sha256, Is.EqualTo("base"));
            Assert.That(pressed.Before?.SelfDrawn, Is.True);
        });
    }

    // Contracase: the window's drawing cannot be taken after the pause (a capture that comes back black): the point
    // is not checked, so nothing is brought up nor pressed, and the refusal is said instead of an exception.
    [Test]
    public async Task APointWhoseWindowCannotBeCapturedAfterThePauseBringsNothingUp()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop();
        var pointer = new LeasePointer(Lease(new Pause(), clock, desktop), desktop) { Clock = clock, CaptureFails = true };
        var located = new VisibleControlSurface.CapturedWindow(Mission, [], 0, 0, 1, 1, "base") { SelfDrawn = true };

        PointerPressed pressed = await LocatedPointPress.PointerAsync(
            pointer, Mission, 100, 120, located, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Pressed, Is.False);
            Assert.That(pressed.Refusal, Is.EqualTo(VisibleControlSurface.SurfaceChangedWhileWaiting));
            Assert.That(desktop.Fronted, Is.Empty);
        });
    }

    // Contracase: a window that never takes the front is asked for it only up to FrontTakeCapMs, and the burst is
    // refused with nothing sent; the person's front stays.
    [Test]
    public async Task AWindowThatNeverTakesTheFrontIsRefusedWithinItsBound()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { CursorAt = (40, 50), Clock = clock, BringingCostsMs = 600, NeverTakes = true };
        ForegroundLease lease = Lease(new Pause(), clock, desktop);

        IInputBurst burst = await lease.AcquireAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.EqualTo("input_window_not_in_front"));
            Assert.That(burst.MayAct, Is.False);
            Assert.That(desktop.Fronted, Has.Count.EqualTo(2), "asked again only inside the bound");
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    private static ForegroundLease Lease(Pause pause, Clock clock, Desktop desktop) =>
        new(pause, clock, desktop, maxWaitMs: 8_000, watchMission: false);

    // What the App says of its missions.
    private sealed class Missions : IMissionRunning
    {
        internal long Generation { get; set; }

        internal bool Running { get; set; } = true;

        public (long Generation, bool Running) Read() => (Generation, Running);
    }

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Keys(IDesktopKeyboard keyboard) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard);

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("keys and text start no process");
    }

    // The keyboard of the product on the real lease and the fake desktop: a character is typed only while the
    // mission's window holds the front, as Windows would deliver it.
    private sealed class LeaseKeyboard(ForegroundLease lease, Desktop desktop) : IDesktopKeyboard
    {
        internal List<string> Typed { get; } = [];

        internal List<bool> InFrontAtEachCharacter { get; } = [];

        internal Action<int>? EachCharacter { get; init; }

        public int InputSize => IntPtr.Size == 8 ? 40 : 28;

        public DesktopForeground Foreground() => new(desktop.Front, desktop.Front == Mission ? 18016 : 4242, "ventana");

        public uint PressChord(IReadOnlyList<ushort> virtualKeys) => (uint)virtualKeys.Count * 2;

        public uint TypeText(string text, Func<bool> keepGoing)
        {
            int typed = 0;
            foreach (char _ in text)
            {
                EachCharacter?.Invoke(Typed.Sum(piece => piece.Length) + typed);
                if (!keepGoing())
                    break;
                InFrontAtEachCharacter.Add(desktop.Front == Mission);
                typed++;
            }

            Typed.Add(text[..typed]);
            return (uint)typed * 2;
        }

        public bool Holds(nint window) => desktop.Holds(window);

        public ValueTask<IInputBurst> FrontAsync(nint window, CancellationToken cancellationToken) =>
            lease.AcquireAsync(window, cancellationToken);

        public bool GiveFront(nint window)
        {
            desktop.GiveFront(window);
            return true;
        }

        public int LastError() => 0;

        public ValueTask SettleAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }

    // The pointer of the product on the real lease and the fake desktop: it records where the window was when the
    // baseline was taken and when the press went.
    private sealed class LeasePointer(ForegroundLease lease, Desktop desktop) : IPointerFallback
    {
        internal List<string> Events { get; } = [];

        internal Action? BeforePress { get; init; }

        internal Action? AfterPress { get; init; }

        internal Action? AfterBaseline { get; init; }

        internal Clock? Clock { get; init; }

        internal long BaselineAt { get; private set; }

        internal (int X, int Y)? PressedAt { get; private set; }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
            lease.AcquireAsync(window, cancellationToken);

        public ValueTask<(bool Paused, long WaitedMs)> PauseAsync(CancellationToken cancellationToken) =>
            lease.WaitForPauseAsync(cancellationToken);

        public bool Prepare(nint window, int screenX, int screenY) => desktop.Holds(window);

        // The window shown at each point asked (the mission's when unset), in the order asked.
        internal Queue<nint>? ShownAt { get; init; }

        internal List<(nint Window, int X, int Y)> PointsAsked { get; } = [];

        public bool Shows(nint window, int screenX, int screenY)
        {
            PointsAsked.Add((window, screenX, screenY));
            return (ShownAt is { Count: > 0 } shown ? shown.Dequeue() : window) == window;
        }

        // The hash of a screen copy (none taken when unset), and whether every capture fails (comes back black).
        internal string? ScreenCopy { get; init; }

        internal bool CaptureFails { get; init; }

        public ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(nint window, CancellationToken cancellationToken)
        {
            if (CaptureFails)
                throw new IOException("Window content capture came back black.");
            if (ScreenCopy is null)
                return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);
            Events.Add(desktop.Front == window ? "screen copy in front" : "screen copy behind");
            return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 1, 1, ScreenCopy) { SelfDrawn = false });
        }

        public ValueTask<VisibleControlSurface.CapturedWindow?> CaptureBehindAsync(
            nint window, CancellationToken cancellationToken)
        {
            if (CaptureFails)
                throw new IOException("Window content capture came back black.");
            Events.Add(desktop.Front == window ? "baseline in front" : "baseline behind");
            BaselineAt = Clock?.NowMs ?? 0;
            AfterBaseline?.Invoke();
            return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                Clock is null ? null : new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 1, 1, "base") { SelfDrawn = true });
        }

        public bool Click(IInputBurst burst, int screenX, int screenY)
        {
            BeforePress?.Invoke();
            if (!burst.MayAct)
                return false;
            Events.Add(desktop.Front == Mission ? "press in front" : "press behind");
            PressedAt = (screenX, screenY);
            desktop.CursorAt = (screenX, screenY);
            AfterPress?.Invoke();
            return true;
        }
    }

    private sealed class Clock : ILeaseClock
    {
        public long NowMs { get; set; }

        // What happens on the desktop while the lease waits (the person switching windows).
        internal Action? OnDelay { get; set; }

        public ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken)
        {
            NowMs += milliseconds;
            OnDelay?.Invoke();
            return ValueTask.CompletedTask;
        }
    }

    private sealed class Pause : IUserInputPause
    {
        public long LastForeignInputMs { get; set; } = 2_000;

        // The person's last input that reaches a field; null: every input of theirs does.
        internal long? Reaching { get; set; }

        public long LastReachingInputMs => Reaching ?? LastForeignInputMs;

        public long LastOwnInputMs { get; set; }

        // BAXY's own inputs the detector saw so far (none by default).
        internal Func<long>? OwnCount { get; set; }

        public long OwnInputCount => OwnCount?.Invoke() ?? 0;

        public bool HeldDown() => false;

        public bool TellsOwnInput => Tells;

        internal bool Tells { get; init; } = true;

        public string Source => "fake";
    }

    // A person who types all the time: their last input is always now.
    private sealed class TypingPause(Clock clock) : IUserInputPause
    {
        public long LastForeignInputMs => clock.NowMs;

        public long LastReachingInputMs => clock.NowMs;

        public long LastOwnInputMs => 0;

        public long OwnInputCount => 0;

        public bool HeldDown() => false;

        public bool TellsOwnInput => true;

        public string Source => "fake";
    }

    private sealed class Desktop : ILeaseDesktop
    {
        internal nint Front { get; set; } = Person;

        internal nint Above { get; init; }

        internal (int X, int Y) CursorAt { get; set; }

        // How many bringings are taken back right after they succeed (a guard handing the front back in between).
        internal int TakenBackAfterBringing { get; set; }

        internal List<nint> Fronted { get; } = [];

        internal List<nint> GivenFront { get; } = [];

        internal List<(nint Window, nint Above)> PlacedBelow { get; } = [];

        public nint Foreground() => Front;

        public bool Holds(nint window) => window == Front;

        public bool IsAlive(nint window) => true;

        public bool IsMinimized(nint window) => false;

        public nint WindowAbove(nint window) => window == Mission ? Above : 0;

        public (int X, int Y) Cursor() => CursorAt;

        public bool SetCursor(int x, int y)
        {
            CursorAt = (x, y);
            return true;
        }

        // r20b palanca 4: what bringing a window up costs on the clock (a slow activation), and a window that never
        // takes the front.
        internal Clock? Clock { get; init; }

        internal int BringingCostsMs { get; init; }

        internal bool NeverTakes { get; init; }

        public bool BringToFront(nint window)
        {
            Fronted.Add(window);
            if (Clock is not null)
                Clock.NowMs += BringingCostsMs;
            if (NeverTakes)
                return false;
            Front = window;
            OnBrought?.Invoke();
            if (TakenBackAfterBringing > 0)
            {
                TakenBackAfterBringing--;
                Front = Person;
            }

            return Front == window;
        }

        internal Action? OnGiveFront { get; set; }

        // Encargo K: what happens when a bringing holds, and whether the window in front takes the keyboard (null: it
        // always does); how many times that was asked.
        internal Action? OnBrought { get; set; }

        internal Func<bool>? TakesKeysWhen { get; set; }

        internal int KeysAsked { get; private set; }

        public bool TakesKeys(nint window)
        {
            KeysAsked++;
            return TakesKeysWhen?.Invoke() ?? true;
        }

        public void GiveFront(nint window)
        {
            GivenFront.Add(window);
            Front = window;
            OnGiveFront?.Invoke();
        }


        public void PlaceBelow(nint window, nint above) => PlacedBelow.Add((window, above));

        public void Minimize(nint window)
        {
        }
    }
}
