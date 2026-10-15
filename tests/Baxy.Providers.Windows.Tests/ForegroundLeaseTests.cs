using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The foreground lease (GOAL_COMPUTER_USE_V3 point 0, fix 3) on a fake clock, a fake pause detector and a fake
/// desktop: it waits for the person's pause, never acts over them, and gives back the front, the window order and
/// the cursor exactly.
/// </summary>
[TestFixture]
public sealed class ForegroundLeaseTests
{
    private const nint Mission = 0x4660;
    private const nint Person = 0x1111;
    private const nint Between = 0x2222;

    [Test]
    public async Task ItWaitsUntilThePersonHasPausedHalfASecond()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 9_900 };
        var desktop = new FakeDesktop();

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.Null);
            Assert.That(burst.MayAct, Is.True);
            Assert.That(burst.WaitedMs, Is.EqualTo(400));
            Assert.That(desktop.Front, Is.EqualTo(Mission));
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission }));
        });
    }

    [Test]
    public async Task APersonAlreadyPausedIsNotWaitedFor()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000 };

        IInputBurst burst = await Lease(pause, clock, new FakeDesktop()).AcquireAsync(Mission, CancellationToken.None);

        Assert.That(burst.WaitedMs, Is.Zero);
    }

    [Test]
    public async Task AHeldModifierOrButtonIsWaitedOutToo()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 0, HeldUntilMs = 10_300 };
        pause.Clock = clock;

        IInputBurst burst = await Lease(pause, clock, new FakeDesktop()).AcquireAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.MayAct, Is.True);
            Assert.That(burst.WaitedMs, Is.GreaterThanOrEqualTo(300));
        });
    }

    [Test]
    public async Task APersonWhoNeverPausesIsNeverActedOver()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { Clock = clock, AlwaysActive = true };
        var desktop = new FakeDesktop();

        IInputBurst burst = await Lease(pause, clock, desktop, maxWaitMs: 8_000)
            .AcquireAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.EqualTo("input_user_not_paused"));
            Assert.That(burst.MayAct, Is.False);
            Assert.That(burst.WaitedMs, Is.InRange(8_000, 8_100));
            Assert.That(desktop.Fronted, Is.Empty);
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(burst.Restore(), Is.True);
            Assert.That(desktop.GivenFront, Is.Empty);
        });
    }

    [Test]
    public async Task TheFrontTheWindowOrderAndTheCursorAreGivenBackExactly()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var desktop = new FakeDesktop { Above = Between, CursorAt = (300, 200) };
        IInputBurst burst = await Lease(new FakePause(), clock, desktop).AcquireAsync(Mission, CancellationToken.None);
        desktop.CursorAt = (900, 640);

        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(restored, Is.True);
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(desktop.GivenFront, Is.EqualTo(new[] { Person }));
            Assert.That(desktop.PlacedBelow, Is.EqualTo(new[] { (Mission, Between) }));
            Assert.That(desktop.CursorAt, Is.EqualTo((300, 200)));
        });
    }

    [Test]
    public async Task RestoringTwiceGivesTheFirstAnswerAndChangesNothingMore()
    {
        var desktop = new FakeDesktop { Above = Between };
        IInputBurst burst = await Lease(new FakePause(), new FakeClock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);

        bool first = burst.Restore();
        bool second = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.True);
            Assert.That(second, Is.True);
            Assert.That(desktop.GivenFront, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task AMinimizedMissionWindowGoesBackToTheTaskbar()
    {
        var desktop = new FakeDesktop { MissionMinimized = true };
        IInputBurst burst = await Lease(new FakePause(), new FakeClock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);

        _ = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Minimized, Is.EqualTo(new[] { Mission }));
            Assert.That(desktop.PlacedBelow, Is.Empty);
        });
    }

    // Contracase: the mission's window already in front is not brought, and no front is handed anywhere.
    [Test]
    public async Task AWindowAlreadyInFrontIsNotBroughtAndOnlyTheCursorIsGivenBack()
    {
        var desktop = new FakeDesktop { Front = Mission, CursorAt = (10, 10) };
        IInputBurst burst = await Lease(new FakePause(), new FakeClock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);
        desktop.CursorAt = (50, 60);

        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(restored, Is.True);
            Assert.That(desktop.Fronted, Is.Empty);
            Assert.That(desktop.GivenFront, Is.Empty);
            Assert.That(desktop.CursorAt, Is.EqualTo((10, 10)));
        });
    }

    [Test]
    public async Task ThePersonsInputDuringTheBurstStopsItAndTheirCursorStaysWhereTheyPutIt()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause();
        var desktop = new FakeDesktop { CursorAt = (300, 200) };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireAsync(Mission, CancellationToken.None);
        Assert.That(burst.MayAct, Is.True);

        clock.NowMs += 120;
        pause.LastForeignInputMs = clock.NowMs;
        desktop.CursorAt = (700, 420);
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(burst.UserActed, Is.True);
            Assert.That(burst.MayAct, Is.False);
            Assert.That(restored, Is.True);
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(desktop.CursorAt, Is.EqualTo((700, 420)));
        });
    }

    // Review of fable/cu-v3-pausa: a person who puts another window in front during the burst keeps it. Giving the
    // front back to the saved window, or minimizing or reordering the mission's, would steal the window they chose.
    [Test]
    public async Task AWindowThePersonPutInFrontDuringTheBurstIsLeftTheirs()
    {
        const nint Chosen = 0x3333;
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause();
        var desktop = new FakeDesktop { Above = Between, MissionMinimized = true };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireAsync(Mission, CancellationToken.None);

        clock.NowMs += 90;
        pause.LastForeignInputMs = clock.NowMs;
        desktop.Front = Chosen;
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(restored, Is.True);
            Assert.That(desktop.Front, Is.EqualTo(Chosen));
            Assert.That(desktop.GivenFront, Is.Empty);
            Assert.That(desktop.Minimized, Is.Empty);
            Assert.That(desktop.PlacedBelow, Is.Empty);
        });
    }

    // Contracase: with the mission's window still in front after the burst, the front goes back to the person.
    [Test]
    public async Task TheMissionWindowStillInFrontAfterTheBurstIsGivenBack()
    {
        var desktop = new FakeDesktop { MissionMinimized = true };
        IInputBurst burst = await Lease(new FakePause(), new FakeClock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);

        _ = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(desktop.Minimized, Is.EqualTo(new[] { Mission }));
        });
    }

    // Review of fable/cu-v3-pausa: another top-level window of the mission's process in front is the person's (a
    // second folder window, the shell's taskbar, another browser window), so the lease brings the mission's own window
    // and gives the front back; only a window the mission's window owns (its dialog) counts as it.
    [Test]
    public void OnlyTheWindowItsChildrenOrTheWindowsItOwnsCountAsInFront()
    {
        const nint Child = 0x4661;
        const nint Dialog = 0x4662;
        const nint DialogOfDialog = 0x4663;
        const nint Sibling = 0x4664;
        nint Root(nint hwnd) => hwnd == Child ? Mission : hwnd;
        nint Owner(nint hwnd) => hwnd switch
        {
            Dialog => Mission,
            DialogOfDialog => Dialog,
            _ => 0,
        };

        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.IsOrOwnedBy(Mission, Mission, Root, Owner), Is.True);
            Assert.That(VisibleControlSurface.IsOrOwnedBy(Mission, Child, Root, Owner), Is.True);
            Assert.That(VisibleControlSurface.IsOrOwnedBy(Mission, Dialog, Root, Owner), Is.True);
            Assert.That(VisibleControlSurface.IsOrOwnedBy(Mission, DialogOfDialog, Root, Owner), Is.True);
            // Contracases: a sibling window of the same process, the mission's owner, and nobody in front.
            Assert.That(VisibleControlSurface.IsOrOwnedBy(Mission, Sibling, Root, Owner), Is.False);
            Assert.That(VisibleControlSurface.IsOrOwnedBy(Dialog, Mission, Root, Owner), Is.False);
            Assert.That(VisibleControlSurface.IsOrOwnedBy(Mission, 0, Root, Owner), Is.False);
        });
    }

    [Test]
    public async Task ASiblingWindowOfTheMissionsProcessInFrontIsNotTakenForIt()
    {
        const nint Sibling = 0x4664;
        var desktop = new FakeDesktop { Front = Sibling };

        IInputBurst burst = await Lease(new FakePause(), new FakeClock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(burst.MayAct, Is.True);
            Assert.That(desktop.Fronted, Is.EqualTo(new[] { Mission }));
            Assert.That(restored, Is.True);
            Assert.That(desktop.Front, Is.EqualTo(Sibling));
        });
    }

    // Contracase: BAXY's own input during the burst is not the person's.
    [Test]
    public async Task BaxysOwnInputDuringTheBurstDoesNotStopIt()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause();
        IInputBurst burst = await Lease(pause, clock, new FakeDesktop()).AcquireAsync(Mission, CancellationToken.None);

        clock.NowMs += 120;

        Assert.That(burst.MayAct, Is.True);
    }

    [Test]
    public async Task AFrontThatDoesNotComeBackIsReportedNotRestored()
    {
        var desktop = new FakeDesktop { RefusesGivingFront = true };
        IInputBurst burst = await Lease(new FakePause(), new FakeClock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);

        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(restored, Is.False);
            Assert.That(desktop.GivenFront, Has.Count.EqualTo(2), "one retry");
        });
    }

    [Test]
    public async Task AWindowThatWillNotComeToTheFrontGetsNothingAndTheFrontStaysThePersons()
    {
        var desktop = new FakeDesktop { Frontable = false };
        IInputBurst burst = await Lease(new FakePause(), new FakeClock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.EqualTo("input_window_not_in_front"));
            Assert.That(burst.MayAct, Is.False);
            Assert.That(burst.Restore(), Is.True);
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    [Test]
    public async Task AGoneWindowIsRefusedWithoutTouchingTheDesktop()
    {
        var desktop = new FakeDesktop { MissionAlive = false };
        IInputBurst burst = await Lease(new FakePause(), new FakeClock { NowMs = 10_000 }, desktop)
            .AcquireAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.EqualTo("input_window_not_in_front"));
            Assert.That(desktop.Fronted, Is.Empty);
        });
    }

    [Test]
    public void AClickOrAPointOutsideAGrantedBurstDoesNotTouchTheCursor()
    {
        var refused = new FakeInputBurst { Refusal = "input_user_not_paused" };
        var interrupted = new FakeInputBurst { UserActed = true };

        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.Click(refused, 1, 1), Is.False);
            Assert.That(VisibleControlSurface.PointAt(interrupted, 1, 1), Is.False);
        });
    }

    // A helper that brings up its own window (a script): the burst waits for the pause like any other and gives the
    // front and the cursor back to the person when the helper took them.
    [Test]
    public async Task AHelperBurstWaitsForThePauseAndGivesBackWhatTheHelperTook()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 9_800 };
        var desktop = new FakeDesktop { CursorAt = (5, 5) };

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);
        // The helper brings its window up and clicks somewhere.
        desktop.Front = Mission;
        desktop.CursorAt = (300, 400);
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(burst.MayAct, Is.True);
            Assert.That(burst.WaitedMs, Is.EqualTo(300));
            Assert.That(desktop.Fronted, Is.Empty, "the lease takes nothing for a helper");
            Assert.That(restored, Is.True);
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(desktop.CursorAt, Is.EqualTo((5, 5)));
        });
    }

    [Test]
    public async Task AHelperBurstIsRefusedToAPersonWhoNeverPauses()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { Clock = clock, AlwaysActive = true };

        IInputBurst burst = await Lease(pause, clock, new FakeDesktop()).AcquireForHelperAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.EqualTo("input_user_not_paused"));
            Assert.That(burst.MayAct, Is.False);
        });
    }

    // Contracase: the person acted during the helper's burst (they switched window, moved the mouse): what they did is
    // theirs and nothing is handed back over it.
    [Test]
    public async Task AHelperBurstDoesNotUndoWhatThePersonDidDuringIt()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000 };
        var desktop = new FakeDesktop { CursorAt = (5, 5) };

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);
        clock.NowMs += 100;
        pause.LastForeignInputMs = clock.NowMs;
        desktop.Front = Between;
        desktop.CursorAt = (70, 80);
        _ = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(burst.UserActed, Is.True);
            Assert.That(desktop.GivenFront, Is.Empty);
            Assert.That(desktop.Front, Is.EqualTo(Between));
            Assert.That(desktop.CursorAt, Is.EqualTo((70, 80)));
        });
    }

    // Review of fable/cu-v3-molestia2: the helper brought its window up before the person went back to typing. That
    // window is the helper's, as the leased window is in a window burst, and the person typing on does not make it
    // theirs: the front goes back to the window they were in.
    [Test]
    public async Task AWindowTheHelperBroughtUpIsGivenBackEvenWhenThePersonKeptTyping()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000 };
        var desktop = new FakeDesktop { CursorAt = (5, 5) };

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);
        desktop.Front = Mission;
        burst.ObserveFront();
        clock.NowMs += 1_000;
        pause.LastForeignInputMs = clock.NowMs;
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(burst.UserActed, Is.True);
            Assert.That(restored, Is.True);
            Assert.That(desktop.GivenFront, Is.EqualTo(new[] { Person }));
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    // Contracase: after the helper's window came up the person switched to a third window; that one is their choice.
    [Test]
    public async Task AThirdWindowThePersonChoseAfterTheHelpersStaysTheirs()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000 };
        var desktop = new FakeDesktop();

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);
        desktop.Front = Mission;
        burst.ObserveFront();
        clock.NowMs += 300;
        pause.LastForeignInputMs = clock.NowMs;
        desktop.Front = Between;
        burst.ObserveFront();
        _ = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(desktop.GivenFront, Is.Empty);
            Assert.That(desktop.Front, Is.EqualTo(Between));
        });
    }

    // Review of fable/cu-v3-molestia2: the lease checked its window once, when it took the front. A toast or a popup
    // that takes the front afterwards, with no input of the person, must stop the flow before its next key, or that
    // key lands in the other window.
    [Test]
    public async Task AFlowWhoseWindowLostTheFrontWithoutThePersonSendsNothingMore()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000 };
        var desktop = new FakeDesktop();
        var sent = new List<string>();

        (string? Code, bool Sent) stopped = await LeasedInput.RunAsync<(string?, bool)>(
            Lease(pause, clock, desktop),
            Mission,
            _ =>
            {
                desktop.Front = Between;
                LeasedInput.EnsureMayAct();
                sent.Add("key");
                return ValueTask.FromResult<(string?, bool)>((null, true));
            },
            (code, effect) => (code, effect),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sent, Is.Empty);
            Assert.That(stopped.Code, Is.EqualTo(LeasedInput.WindowChanged));
        });
    }

    // Contracase: with the window still in front and no input of the person, every key of the flow goes.
    [Test]
    public async Task AFlowWhoseWindowKeepsTheFrontSendsEveryKey()
    {
        var desktop = new FakeDesktop();
        var sent = new List<int>();

        (string? Code, bool Sent) done = await LeasedInput.RunAsync<(string?, bool)>(
            Lease(new FakePause { LastForeignInputMs = 2_000 }, new FakeClock { NowMs = 10_000 }, desktop),
            Mission,
            _ =>
            {
                for (int key = 0; key < 3; key++)
                {
                    LeasedInput.EnsureMayAct();
                    sent.Add(key);
                }

                return ValueTask.FromResult<(string?, bool)>((null, true));
            },
            (code, effect) => (code, effect),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sent, Is.EqualTo(new[] { 0, 1, 2 }));
            Assert.That(done.Code, Is.Null);
        });
    }

    // interrupcion-fantasma, twin of r9 v3-56: a click pressed in the person's pause and given back (front and cursor
    // theirs again); during its post-read they go on typing in their own window (the simulated user's keys, which Raw
    // Input never delivers: the self-check counts them) and moving the mouse inside it. Nothing of that reaches the
    // mission's window behind: the post-read is not cut as «you were using the PC».
    [Test]
    public async Task ThePersonTypingInTheirOwnWindowAfterTheFrontWentBackDoesNotCutThePostRead()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, PointerMs = 0, OverMissionMs = 0 };
        var desktop = new FakeDesktop { CursorAt = (220, 928), ShowsMissionAtCursor = false };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireAsync(Mission, CancellationToken.None);
        desktop.CursorAt = (1200, 437);
        clock.NowMs += 60;
        Assert.That(burst.Restore(), Is.True);

        clock.NowMs += 500;
        pause.LastForeignInputMs = clock.NowMs;
        desktop.CursorAt = (240, 920);

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Front, Is.EqualTo(Person));
            Assert.That(burst.UserActed, Is.False);
            Assert.That(burst.MayAct, Is.True);
        });
    }

    // Contracases: after the front went back, what can reach the mission's window still stops it: the person clicks
    // (anywhere: a press lands where the cursor is), the cursor goes over the mission's window, or they bring it to the
    // front. And an input of theirs before the front went back, or one in flight then, always does.
    [TestCase("click")]
    [TestCase("hover")]
    [TestCase("front")]
    [TestCase("before")]
    [TestCase("inflight")]
    public async Task WhatCanReachTheMissionsWindowStillStopsTheBurstAfterTheFrontWentBack(string what)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, PointerMs = 0, OverMissionMs = 0 };
        var desktop = new FakeDesktop { CursorAt = (220, 928), ShowsMissionAtCursor = false };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireAsync(Mission, CancellationToken.None);
        clock.NowMs += 60;
        if (what == "before")
            pause.LastForeignInputMs = clock.NowMs - 20;
        if (what == "inflight")
            pause.UnexplainedMs = clock.NowMs - 10;
        _ = burst.Restore();
        pause.UnexplainedMs = 0;

        clock.NowMs += 500;
        pause.LastForeignInputMs = clock.NowMs;
        switch (what)
        {
            case "click":
                pause.PointerMs = clock.NowMs;
                break;
            case "hover":
                desktop.ShowsMissionAtCursor = true;
                break;
            case "front":
                desktop.Front = Mission;
                break;
        }

        Assert.That(burst.UserActed, Is.True);
    }

    // Review r2 of interrupcion-fantasma (importante): between two reads of a post-read (OCR every 220 ms, the vision
    // read once at about 200 ms) the person's cursor crosses the mission's window (its hover changes what it draws) and
    // leaves it, or they Alt+Tab to it and back, or press a media key: at the read the cursor is over their own window
    // and their window is in front, yet the capture changed because of them. The pass and the key are remembered.
    [TestCase("crossed")]
    [TestCase("alttab")]
    public async Task WhatReachedTheMissionsWindowBetweenTwoReadsStillStopsTheBurst(string what)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, PointerMs = 0, OverMissionMs = 0 };
        var desktop = new FakeDesktop { CursorAt = (220, 928), ShowsMissionAtCursor = false };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireAsync(Mission, CancellationToken.None);
        clock.NowMs += 60;
        _ = burst.Restore();

        clock.NowMs += 120;
        pause.LastForeignInputMs = clock.NowMs;
        if (what == "crossed")
        {
            pause.OverMissionMs = clock.NowMs;
            desktop.ShowsMissionAtCursor = true;
        }
        else
        {
            pause.PointerMs = clock.NowMs;
            desktop.Front = Mission;
        }

        clock.NowMs += 100;
        pause.LastForeignInputMs = clock.NowMs;
        desktop.CursorAt = (240, 920);
        desktop.ShowsMissionAtCursor = false;
        desktop.Front = Person;

        Assert.Multiple(() =>
        {
            Assert.That(burst.UserActed, Is.True);
            Assert.That(burst.MayAct, Is.False);
        });
    }

    // Contracase: the same moves between two reads, but only over the person's own window (the cursor never over the
    // mission's, no press and no switching key): the post-read is not cut.
    [Test]
    public async Task MovesOnlyOverThePersonsOwnWindowBetweenTwoReadsDoNotStopTheBurst()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, PointerMs = 0, OverMissionMs = 0 };
        var desktop = new FakeDesktop { CursorAt = (220, 928), ShowsMissionAtCursor = false };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireAsync(Mission, CancellationToken.None);
        clock.NowMs += 60;
        _ = burst.Restore();

        for (int read = 0; read < 3; read++)
        {
            clock.NowMs += 220;
            pause.LastForeignInputMs = clock.NowMs - 30;
            desktop.CursorAt = (240 + read * 15, 920);
            Assert.That(burst.UserActed, Is.False, $"read {read}");
        }
    }

    // Contracase: the person's window was the mission's (it held the front when the burst began): their keys after the
    // burst go into it, and they stop it as before.
    [Test]
    public async Task KeysAfterTheBurstIntoTheMissionsOwnWindowStillStopIt()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, PointerMs = 0, OverMissionMs = 0 };
        var desktop = new FakeDesktop { Front = Mission, ShowsMissionAtCursor = false };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireAsync(Mission, CancellationToken.None);
        _ = burst.Restore();

        clock.NowMs += 500;
        pause.LastForeignInputMs = clock.NowMs;

        Assert.That(burst.UserActed, Is.True);
    }

    // molestia-ayudantes (riesgos-fusion 1): a bare move of the person's mouse outside the helper's window cut the
    // Spotify, messaging, Steam, clipboard and quick-switcher scripts (the watcher killed the process). It reaches
    // nothing: the helper goes on, the front goes back to the person, and the cursor stays where they put it.
    [Test]
    public async Task ABareMoveOutsideTheHelpersWindowDoesNotCutItsBurst()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };
        var desktop = new FakeDesktop { CursorAt = (5, 5) };

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);
        desktop.Front = Mission;
        burst.ObserveFront();
        clock.NowMs += 200;
        pause.LastForeignInputMs = clock.NowMs;
        pause.OverOtherMs = clock.NowMs;
        pause.PointerAt = (clock.NowMs, 40, 60);
        desktop.CursorAt = (40, 60);
        bool mayAct = burst.MayAct;
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(mayAct, Is.True, "a bare move reaches nothing");
            Assert.That(restored, Is.True);
            Assert.That(desktop.Front, Is.EqualTo(Person), "the front back to the person");
            Assert.That(desktop.CursorAt, Is.EqualTo((40, 60)), "the cursor stays where the person put it");
        });
    }

    // Contracases: a key, a button or the wheel of the person, or their cursor over the window the helper brought up
    // (seen by the watcher, or in front now), still cut the helper.
    [TestCase("key", false)]
    [TestCase("over the helper's window", false)]
    [TestCase("over the window in front", true)]
    public async Task WhatReachesStillCutsTheHelpersBurst(string what, bool unobserved)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };
        var desktop = new FakeDesktop();

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);
        desktop.Front = Mission;
        if (!unobserved)
            burst.ObserveFront();
        clock.NowMs += 200;
        pause.LastForeignInputMs = clock.NowMs;
        if (what == "key")
            pause.ReachingMs = clock.NowMs;
        else
            pause.OverMissionMs = clock.NowMs;

        Assert.That(burst.MayAct, Is.False);
    }

    // Review of molestia-ayudantes (2 and the «no robar el ratón» aggravation): a person who keeps moving the mouse
    // without a key or a click is waited for, and refused cleanly at the ceiling with nothing brought up nor sent.
    // Granted, a helper jumped the cursor from under their hand, and a flow's window came up under the moving cursor,
    // caught the next move and stopped half done (input_user_interrupted, sent=true).
    [TestCase("helper")]
    [TestCase("flow")]
    public async Task ABurstIsNotGrantedWhileThePersonMovesTheMouse(string kind)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { Clock = clock, AlwaysActive = true, ReachingMs = 2_000, OverMissionMs = 0 };
        var desktop = new FakeDesktop();
        ForegroundLease lease = Lease(pause, clock, desktop);

        IInputBurst burst = kind == "helper"
            ? await lease.AcquireForHelperAsync(CancellationToken.None)
            : await lease.AcquireForFlowAsync(Mission, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.EqualTo("input_user_not_paused"));
            Assert.That(burst.WaitedMs, Is.GreaterThanOrEqualTo(8_000));
            Assert.That(desktop.Fronted, Is.Empty, "nothing brought up");
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    // The same for a typed flow on a known window (the messaging and Steam clients, LeasedInput.RunAsync): a bare move
    // elsewhere does not cut it; a key, or the cursor over the leased window, does.
    [TestCase("bare move elsewhere", true)]
    [TestCase("key", false)]
    [TestCase("over the leased window", false)]
    public async Task AFlowsBurstIsCutOnlyByWhatReachesItsWindow(string what, bool mayAct)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };
        var desktop = new FakeDesktop();

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForFlowAsync(Mission, CancellationToken.None);
        clock.NowMs += 150;
        pause.LastForeignInputMs = clock.NowMs;
        if (what == "key")
            pause.ReachingMs = clock.NowMs;
        else if (what == "over the leased window")
            pause.OverMissionMs = clock.NowMs;
        else
            pause.OverOtherMs = clock.NowMs;

        Assert.Multiple(() =>
        {
            Assert.That(burst.Refusal, Is.Null);
            Assert.That(burst.MayAct, Is.EqualTo(mayAct));
        });
        _ = burst.Restore();
        Assert.That(desktop.Front, Is.EqualTo(Person));
    }

    // Contracase: a mission's act (AcquireAsync) still yields to any input of the person, a bare move too: it gives
    // the front back at once and goes on after their pause (r4a M1).
    [Test]
    public async Task AMissionsBurstStillYieldsToABareMove()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };

        IInputBurst burst = await Lease(pause, clock, new FakeDesktop()).AcquireAsync(Mission, CancellationToken.None);
        clock.NowMs += 150;
        pause.LastForeignInputMs = clock.NowMs;

        Assert.That(burst.MayAct, Is.False);
    }

    // molestia-ayudantes (c6, s11, s13: final_frente=no): the person typed in their own window, which cut the helper
    // before the watcher saw the window it brought up; that window is still the helper's (typing moves no front) and
    // the front goes back to the person. AHelperBurstDoesNotUndoWhatThePersonDidDuringIt is the contracase (a click).
    [Test]
    public async Task AWindowTheHelperBroughtUpUnseenAfterThePersonsKeyIsStillGivenBack()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, FrontMovingMs = 2_000 };
        var desktop = new FakeDesktop { CursorAt = (5, 5) };

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);
        clock.NowMs += 100;
        pause.LastForeignInputMs = clock.NowMs;
        burst.ObserveFront();
        desktop.Front = Mission;
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(burst.UserActed, Is.True);
            Assert.That(restored, Is.True);
            Assert.That(desktop.GivenFront, Is.EqualTo(new[] { Person }));
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    // Review of molestia-ayudantes, 3 (contracase of the one above): the person's keys in their own window opened a
    // dialog of its application (Ctrl+O in their editor) during the helper; that dialog is theirs and keeps the front
    // (handing the front to its disabled owner would take it from them).
    [Test]
    public async Task ADialogThePersonsKeysOpenedInTheirApplicationKeepsTheFront()
    {
        const nint dialog = 0x2222;
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, FrontMovingMs = 2_000 };
        var desktop = new FakeDesktop();
        _ = desktop.PersonsApplication.Add(dialog);

        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);
        clock.NowMs += 100;
        pause.LastForeignInputMs = clock.NowMs;
        burst.ObserveFront();
        desktop.Front = dialog;
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(restored, Is.True);
            Assert.That(desktop.GivenFront, Is.Empty);
            Assert.That(desktop.Front, Is.EqualTo(dialog));
        });
    }

    // Review of molestia-ayudantes, 1: a bare move no longer cuts a typed flow or a helper, so BAXY may jump the cursor
    // to a click after the person moved it. The cursor goes back where the person's own move left it, not where BAXY
    // clicked (in a window gone behind). Twins of a helper's click (Spotify) and of a flow's (the messaging client).
    [TestCase("helper")]
    [TestCase("flow")]
    public async Task TheCursorGoesBackWhereThePersonLeftItAfterBaxysJump(string kind)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };
        var desktop = new FakeDesktop { CursorAt = (5, 5) };
        ForegroundLease lease = Lease(pause, clock, desktop);
        IInputBurst burst = kind == "helper"
            ? await lease.AcquireForHelperAsync(CancellationToken.None)
            : await lease.AcquireForFlowAsync(Mission, CancellationToken.None);
        desktop.Front = Mission;
        burst.ObserveFront();

        clock.NowMs += 50;
        pause.LastForeignInputMs = clock.NowMs;
        pause.OverOtherMs = clock.NowMs;
        pause.PointerAt = (clock.NowMs, 40, 60);
        desktop.CursorAt = (40, 60);
        clock.NowMs += 600;
        bool mayAct = burst.MayAct;
        desktop.CursorAt = (300, 300);
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(mayAct, Is.True, "a bare move elsewhere does not cut it");
            Assert.That(restored, Is.True);
            Assert.That(desktop.CursorAt, Is.EqualTo((40, 60)), "where the person's move left it");
            Assert.That(desktop.Front, Is.EqualTo(Person));
        });
    }

    // The same when only the person's keys came (they cut the flow after BAXY's jump): the cursor goes back where it
    // was, which no key of theirs moved.
    [Test]
    public async Task AKeyOfThePersonAfterBaxysJumpGivesTheCursorBackWhereItWas()
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };
        pause.PointerAt = (1_500, 5, 5);
        var desktop = new FakeDesktop { CursorAt = (5, 5) };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForFlowAsync(Mission, CancellationToken.None);

        desktop.CursorAt = (300, 300);
        clock.NowMs += 50;
        pause.LastForeignInputMs = clock.NowMs;
        pause.ReachingMs = clock.NowMs;
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(burst.UserActed, Is.True);
            Assert.That(restored, Is.True);
            Assert.That(desktop.CursorAt, Is.EqualTo((5, 5)));
        });
    }

    // Contracases: the person moved the cursor after BAXY's jump (it is where their move left it), or where their
    // input left it cannot be told (an input the detector missed): it stays where it is.
    [TestCase(true)]
    [TestCase(false)]
    public async Task TheCursorThePersonMovedLastStaysWhereItIs(bool told)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };
        var desktop = new FakeDesktop { CursorAt = (5, 5) };
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);

        desktop.CursorAt = (300, 300);
        clock.NowMs += 50;
        pause.LastForeignInputMs = clock.NowMs;
        desktop.CursorAt = (310, 320);
        if (told)
            pause.PointerAt = (clock.NowMs, 310, 320);
        bool restored = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(restored, Is.True);
            Assert.That(desktop.CursorAt, Is.EqualTo((310, 320)));
        });
    }

    // Review of molestia-ayudantes, aggravation: a flow's click never jumps the cursor from under a hand that is moving
    // it (the move does not cut its keys); once the hand rests (QuietMs), it clicks.
    [TestCase(0, "input_user_interrupted|True")]
    [TestCase(ForegroundLease.QuietMs, "clicked")]
    public async Task AFlowsClickWaitsForTheHandOffTheMouse(int restedMs, string expected)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };
        var desktop = new FakeDesktop();
        bool typed = false;

        string result = await LeasedInput.RunAsync(
            Lease(pause, clock, desktop),
            Mission,
            _ =>
            {
                clock.NowMs += 10;
                pause.LastForeignInputMs = clock.NowMs;
                pause.PointerAt = (clock.NowMs, 9, 9);
                clock.NowMs += restedMs;
                LeasedInput.EnsureMayAct();
                typed = true;
                LeasedInput.EnsureMayMovePointer();
                return ValueTask.FromResult("clicked");
            },
            (code, sent) => $"{code}|{sent}",
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(typed, Is.True, "its keys go on");
            Assert.That(result, Is.EqualTo(expected));
        });
    }

    // The twin of the real path: the watcher of a helper's process (LeasedInput.WatchHelperAsync) lets a script of a
    // few hundred ms finish while the person only moves the mouse, and still kills it at their key.
    [TestCase(false, false)]
    [TestCase(true, true)]
    public async Task TheHelpersWatcherKillsItOnlyAtAnInputThatReaches(bool key, bool interrupted)
    {
        var clock = new FakeClock { NowMs = 10_000 };
        var pause = new FakePause { LastForeignInputMs = 2_000, ReachingMs = 2_000, OverMissionMs = 0 };
        var desktop = new FakeDesktop();
        IInputBurst burst = await Lease(pause, clock, desktop).AcquireForHelperAsync(CancellationToken.None);

        (string? result, bool stopped) = await LeasedInput.WatchHelperAsync(
            burst,
            async run =>
            {
                desktop.Front = Mission;
                pause.LastForeignInputMs = clock.NowMs + 1;
                if (key)
                    pause.ReachingMs = clock.NowMs + 1;
                await Task.Delay(300, run);
                return "ok";
            },
            CancellationToken.None);
        _ = burst.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(stopped, Is.EqualTo(interrupted));
            Assert.That(result, interrupted ? Is.Null : Is.EqualTo("ok"));
        });
    }

    private static ForegroundLease Lease(FakePause pause, FakeClock clock, FakeDesktop desktop, int maxWaitMs = 8_000) =>
        new(pause, clock, desktop, maxWaitMs);

    private sealed class FakeClock : ILeaseClock
    {
        public long NowMs { get; set; }

        public ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken)
        {
            NowMs += milliseconds;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class FakePause : IUserInputPause
    {
        private long _lastForeign;

        internal FakeClock? Clock { get; set; }

        // The person types without a pause: their last input is always now.
        internal bool AlwaysActive { get; init; }

        internal long HeldUntilMs { get; init; }

        // A press, the wheel, Alt, a Windows key or a media key of the person (null: not told apart from their other
        // input).
        internal long? PointerMs { get; set; }

        // The person's cursor last over the mission's window (null: not told apart from their other input).
        internal long? OverMissionMs { get; set; }

        internal long UnexplainedMs { get; set; }

        // A key, a mouse button or the wheel of the person (null: not told apart from their other input, bare moves).
        internal long? ReachingMs { get; set; }

        public long LastReachingInputMs => ReachingMs ?? LastForeignInputMs;

        // A mouse button going down, Alt or a Windows key of the person (null: not told apart from their other input).
        internal long? FrontMovingMs { get; set; }

        public long LastFrontMovingInputMs => FrontMovingMs ?? LastForeignInputMs;

        public long LastBeyondFrontInputMs => PointerMs ?? LastForeignInputMs;

        // The person's cursor last over any other window, once the mission's is told apart (review of
        // molestia-ayudantes, 4: the lease must ask about the window it means).
        internal long OverOtherMs { get; set; }

        public long LastPointerOverMs(nint window) =>
            OverMissionMs is not { } overMission ? LastForeignInputMs : window == Mission ? overMission : OverOtherMs;

        // Where the person's last mouse input left the cursor (null: not told).
        internal (long AtMs, int X, int Y)? PointerAt { get; set; }

        public (long AtMs, int X, int Y)? LastPointerAt => PointerAt;

        public long UnexplainedInputMs => UnexplainedMs;

        public long LastForeignInputMs
        {
            get => AlwaysActive && Clock is not null ? Clock.NowMs : _lastForeign;
            set => _lastForeign = value;
        }

        public bool HeldDown() => Clock is not null && Clock.NowMs < HeldUntilMs;

        public bool TellsOwnInput => true;

        public string Source => "fake";
    }

    private sealed class FakeDesktop : ILeaseDesktop
    {
        internal nint Front { get; set; } = Person;

        internal nint Above { get; init; }

        internal bool MissionMinimized { get; init; }

        internal bool MissionAlive { get; init; } = true;

        internal bool Frontable { get; init; } = true;

        internal bool RefusesGivingFront { get; init; }

        internal (int X, int Y) CursorAt { get; set; } = (0, 0);

        // Whether the point under the cursor shows the mission's window (true: not told apart, as the lease assumes).
        internal bool ShowsMissionAtCursor { get; set; } = true;

        internal List<nint> Fronted { get; } = [];

        internal List<nint> GivenFront { get; } = [];

        internal List<(nint Window, nint Above)> PlacedBelow { get; } = [];

        internal List<nint> Minimized { get; } = [];

        public nint Foreground() => Front;

        public bool Holds(nint window) => window == Front;

        public bool IsAlive(nint window) => window != Mission || MissionAlive;

        public bool IsMinimized(nint window) => window == Mission && MissionMinimized;

        // Windows of the person's application besides their own (a dialog it opened).
        internal HashSet<nint> PersonsApplication { get; } = [];

        public bool SameApplication(nint window, nint other) =>
            window == other
            || (other == Person && PersonsApplication.Contains(window))
            || (window == Person && PersonsApplication.Contains(other));

        public nint WindowAbove(nint window) => window == Mission ? Above : 0;

        public (int X, int Y) Cursor() => CursorAt;

        public bool Shows(nint window, int x, int y) => window != Mission || ShowsMissionAtCursor;

        public bool SetCursor(int x, int y)
        {
            CursorAt = (x, y);
            return true;
        }

        public bool BringToFront(nint window)
        {
            Fronted.Add(window);
            if (Frontable)
                Front = window;
            return Front == window;
        }

        public void GiveFront(nint window)
        {
            GivenFront.Add(window);
            if (!RefusesGivingFront)
                Front = window;
        }

        public void PlaceBelow(nint window, nint above) => PlacedBelow.Add((window, above));

        public void Minimize(nint window) => Minimized.Add(window);
    }
}
