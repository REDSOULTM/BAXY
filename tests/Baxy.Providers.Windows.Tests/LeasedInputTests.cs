using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// GOAL_COMPUTER_USE_V3 point 0, fix 3, second pass (pending of round 1): the primitives that still sent real keys and
/// clicks without the foreground lease (the messaging client's search and composer, the Steam client's dialog and
/// console, the copy/paste/select-all chords, the calculator and quick-switcher scripts, the Spotify scripts) run
/// inside a burst: nothing starts before the person's pause, a flow stops at their first input, and the burst is
/// always given back.
/// </summary>
[TestFixture]
public sealed class LeasedInputTests
{
    [Test]
    public async Task ARefusedBurstRunsNothingAndSaysWhy()
    {
        var lease = new ScriptedLease { Refusal = "input_user_not_paused" };
        int ran = 0;

        (string? Code, bool Sent) stopped = await LeasedInput.RunAsync<(string?, bool)>(
            lease, 0x4660, _ => { ran++; return ValueTask.FromResult<(string?, bool)>((null, true)); },
            (code, sent) => (code, sent), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(ran, Is.Zero);
            Assert.That(stopped, Is.EqualTo(("input_user_not_paused", false)));
            Assert.That(lease.Bursts.Single().Restores, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task AFlowStopsAtThePersonsFirstInputAndGivesTheBurstBack()
    {
        var lease = new ScriptedLease();
        var events = new List<int>();

        (string? Code, bool Sent) stopped = await LeasedInput.RunAsync<(string?, bool)>(
            lease, 0x4660,
            _ =>
            {
                for (int key = 0; key < 5; key++)
                {
                    LeasedInput.EnsureMayAct();
                    events.Add(key);
                    if (key == 1)
                        lease.Bursts[^1].UserActed = true;
                }

                return ValueTask.FromResult<(string?, bool)>((null, true));
            },
            (code, sent) => (code, sent), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(events, Is.EqualTo(new[] { 0, 1 }));
            Assert.That(stopped, Is.EqualTo((LeasedInput.Interrupted, true)));
            Assert.That(lease.Bursts.Single().Restores, Is.EqualTo(1));
        });
    }

    // Contracase: outside a burst (a flow that never needed one) the check sends nothing back.
    [Test]
    public void OutsideABurstTheCheckDoesNothing() =>
        Assert.DoesNotThrow(LeasedInput.EnsureMayAct);

    [Test]
    public void TheMessagingClientSaysAFrontItCouldNotTakeAsBefore()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.LeaseStop("input_window_not_in_front"),
                Is.EqualTo("messaging_focus_not_verified"));
            Assert.That(WindowsDesktopMessagingAutomation.LeaseStop("input_user_not_paused"),
                Is.EqualTo("input_user_not_paused"));
            Assert.That(WindowsDesktopMessagingAutomation.LeaseStop(LeasedInput.Interrupted),
                Is.EqualTo(LeasedInput.Interrupted));
        });
    }

    [TestCase("clipboard.copy")]
    [TestCase("clipboard.paste")]
    [TestCase("input.select.all")]
    public async Task AChordWaitsForThePersonsPause(string operation)
    {
        using var scripts = new Scripts();
        var runner = new CountingRunner("{\"version\":1,\"ok\":true,\"effectObserved\":true}");
        var refusing = new ScriptedLease { Refusal = "input_user_not_paused" };
        var granting = new ScriptedLease();

        ExternalCapabilityReceipt refused = await scripts.Interaction(runner, refusing)
            .InvokeAsync(operation, Json("{}"), CancellationToken.None);
        int callsWhenRefused = runner.Calls;
        _ = await scripts.Interaction(runner, granting).InvokeAsync(operation, Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("input_user_not_paused"));
            Assert.That(refused.EffectObserved, Is.False);
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(callsWhenRefused, Is.Zero);
            Assert.That(runner.Calls, Is.EqualTo(1));
            Assert.That(granting.Bursts.Single().Restores, Is.EqualTo(1));
        });
    }

    // Contracase: moving or clicking the pointer is the act the person asked for; giving the cursor back would undo it.
    [Test]
    public async Task APointerActionThePersonAskedForIsNotLeased()
    {
        using var scripts = new Scripts();
        var runner = new CountingRunner("{\"version\":1,\"ok\":true,\"effectObserved\":true}");
        var refusing = new ScriptedLease { Refusal = "input_user_not_paused" };

        _ = await scripts.Interaction(runner, refusing)
            .InvokeAsync("input.pointer.control", Json("""{"action":"move_center"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(runner.Calls, Is.EqualTo(1));
            Assert.That(refusing.Bursts, Is.Empty);
        });
    }

    // Review r4 (the Calculator's script used to wait for the person's pause): its buttons are now pressed by UI
    // Automation's Invoke, which sends no key and takes no front, so the person keeps typing in their own window and
    // the expression is pressed meanwhile. No burst is asked for, even from a lease that would refuse one.
    [Test]
    public async Task TheCalculatorPressesItsButtonsWithoutWaitingForThePersonsPause()
    {
        using var scripts = new Scripts();
        var runner = new CountingRunner("{\"ok\":true,\"typed\":\"6*7\",\"displayName\":\"La pantalla muestra 42\",\"value\":\"42\"}");
        var refusing = new ScriptedLease { Refusal = "input_user_not_paused" };

        ExternalCapabilityReceipt evaluated = await scripts.Device(runner, refusing)
            .InvokeAsync("calculator.expression.evaluate", Json("""{"expression":"6*7"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(evaluated.Verified, Is.True);
            Assert.That(runner.Calls, Is.EqualTo(1));
            Assert.That(refusing.Bursts, Is.Empty, "no burst: nothing of the person's input is shared");
        });
    }

    [Test]
    public async Task TheMediaClientScriptWaitsForThePersonsPause()
    {
        using var scripts = new Scripts();
        var runner = new CountingRunner("{\"ok\":true,\"effectObserved\":true,\"playbackStatus\":\"paused\"}");
        var refusing = new ScriptedLease { Refusal = "input_user_not_paused" };

        var adapter = new SpotifyDesktopAdapter(runner, scripts.Play, scripts.Control) { InputLease = refusing };
        ExternalCapabilityReceipt refused = await adapter.InvokeAsync(
            "media.control", Json("""{"action":"pause"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("input_user_not_paused"));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(runner.Calls, Is.Zero);
        });
    }

    // Review of fable/cu-v3-molestia2: a flow whose window lost the front without the person (a toast, a popup) stops
    // before its next key with its own cause, not as the person's interruption.
    [Test]
    public async Task AFlowStopsWhenItsWindowLosesTheFront()
    {
        var lease = new ScriptedLease();
        var events = new List<int>();

        (string? Code, bool Sent) stopped = await LeasedInput.RunAsync<(string?, bool)>(
            lease, 0x4660,
            _ =>
            {
                for (int key = 0; key < 5; key++)
                {
                    LeasedInput.EnsureMayAct();
                    events.Add(key);
                    if (key == 0)
                        lease.Bursts[^1].HoldsWindow = false;
                }

                return ValueTask.FromResult<(string?, bool)>((null, true));
            },
            (code, sent) => (code, sent), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(events, Is.EqualTo(new[] { 0 }));
            Assert.That(stopped, Is.EqualTo((LeasedInput.WindowChanged, true)));
            Assert.That(lease.Bursts.Single().Restores, Is.EqualTo(1));
        });
    }

    // Review of fable/cu-v3-molestia2: a message stopped between its first character and Enter may sit in the chat's
    // composer, where the person's next Enter would send it; the stop says so.
    [Test]
    public async Task AStopThatLeftTheComposerChangedSaysTextWasLeftThere()
    {
        var lease = new ScriptedLease();

        (string? Code, bool Sent) stopped = await LeasedInput.RunAsync<(string?, bool)>(
            lease, 0x4660,
            _ =>
            {
                try
                {
                    LeasedInput.EnsureMayAct();
                    lease.Bursts[^1].UserActed = true;
                    LeasedInput.EnsureMayAct();
                }
                catch (LeasedInput.BurstStoppedException stop)
                {
                    throw WindowsDesktopMessagingAutomation.ComposerAfterStop(stop, composerChanged: true);
                }

                return ValueTask.FromResult<(string?, bool)>((null, true));
            },
            (code, sent) => (WindowsDesktopMessagingAutomation.LeaseStop(code), sent), CancellationToken.None);

        Assert.That(stopped, Is.EqualTo((WindowsDesktopMessagingAutomation.DraftLeftAfterInterruption, true)));
    }

    // Contracase: the composer looks as before (the stop came before any character landed): the stop keeps its cause.
    [TestCase(LeasedInput.Interrupted)]
    [TestCase(LeasedInput.WindowChanged)]
    public void AStopWithTheComposerUnchangedKeepsItsCause(string code) =>
        Assert.That(
            WindowsDesktopMessagingAutomation.ComposerAfterStop(new LeasedInput.BurstStoppedException(code), false).Code,
            Is.EqualTo(code));

    // Review of fable/cu-v3-molestia2: a helper's script (it compiles for a second or more, and the media client's may
    // run for a minute) is watched while it runs: at the person's first input it is stopped, and the receipt says so.
    // Review r4 (the Calculator's script used to be stopped at the person's first input): pressing by Invoke does not
    // touch the person's input, so their typing never stops it half pressed. The script is not watched by a burst.
    [Test]
    public async Task TheCalculatorScriptIsNotStoppedByThePersonsInput()
    {
        using var scripts = new Scripts();
        var runner = new BlockingRunner();
        var lease = new ScriptedLease();
        using var cancel = new CancellationTokenSource();
        Task<ExternalCapabilityReceipt> evaluating = scripts.Device(runner, lease)
            .InvokeAsync("calculator.expression.evaluate", Json("""{"expression":"6*7"}"""), cancel.Token)
            .AsTask();

        await runner.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
        bool stillRunning = !evaluating.IsCompleted;
        cancel.Cancel();
        try
        {
            _ = await evaluating;
        }
        catch (OperationCanceledException)
        {
            // Stopped here by the test itself, never by the person's input.
        }

        Assert.Multiple(() =>
        {
            Assert.That(lease.Bursts, Is.Empty, "no burst watches the script");
            Assert.That(stillRunning, Is.True, "nothing of the person's stops it");
        });
    }

    [Test]
    public async Task TheMediaClientScriptStopsAtThePersonsFirstInput()
    {
        using var scripts = new Scripts();
        var runner = new BlockingRunner();
        var lease = new ScriptedLease();
        var adapter = new SpotifyDesktopAdapter(runner, scripts.Play, scripts.Control) { InputLease = lease };
        Task<ExternalCapabilityReceipt> playing = adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"lofi"}"""), CancellationToken.None).AsTask();

        ExternalCapabilityReceipt receipt = await InterruptAsync(runner, lease, playing);

        AssertStopped(receipt, runner, lease);
    }

    [Test]
    public async Task AChordScriptStopsAtThePersonsFirstInput()
    {
        using var scripts = new Scripts();
        var runner = new BlockingRunner();
        var lease = new ScriptedLease();
        Task<ExternalCapabilityReceipt> pasting = scripts.Interaction(runner, lease)
            .InvokeAsync("clipboard.paste", Json("{}"), CancellationToken.None).AsTask();

        ExternalCapabilityReceipt receipt = await InterruptAsync(runner, lease, pasting);

        AssertStopped(receipt, runner, lease);
    }

    // Contracase: a script that ends before the person acts keeps its own answer.
    [Test]
    public async Task AHelperScriptThatEndsBeforeThePersonActsKeepsItsAnswer()
    {
        var lease = new ScriptedLease();
        IInputBurst burst = await lease.AcquireForHelperAsync(CancellationToken.None);

        (string? Result, bool Interrupted) done = await LeasedInput.WatchHelperAsync(
            burst, _ => ValueTask.FromResult("done"), CancellationToken.None);

        Assert.That(done, Is.EqualTo(("done", false)));
    }

    private static async Task<ExternalCapabilityReceipt> InterruptAsync(
        BlockingRunner runner, ScriptedLease lease, Task<ExternalCapabilityReceipt> running)
    {
        await runner.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
        lease.Bursts.Single().UserActed = true;
        return await running.WaitAsync(TimeSpan.FromSeconds(10));
    }

    private static void AssertStopped(ExternalCapabilityReceipt receipt, BlockingRunner runner, ScriptedLease lease) =>
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(LeasedInput.Interrupted));
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Verified, Is.False);
            Assert.That(runner.Cancelled, Is.True, "the script is stopped, not left typing");
            Assert.That(lease.Bursts.Single().Restores, Is.GreaterThanOrEqualTo(1));
        });

    private static JsonElement Json(string text)
    {
        using JsonDocument document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }

    private sealed class Scripts : IDisposable
    {
        private readonly string _root = Path.Combine(Path.GetTempPath(), "baxy-leased-" + Guid.NewGuid().ToString("N"));

        internal Scripts()
        {
            Directory.CreateDirectory(_root);
            foreach (string name in new[]
            {
                "KnownFolderOpen.ps1", "KnownFileOpen.ps1", "DesktopSelectAll.ps1", "DesktopKeyPress.ps1",
                "Play.ps1", "Control.ps1",
            })
            {
                File.WriteAllText(Path.Combine(_root, name), "# test fixture");
            }
        }

        internal string Play => Path.Combine(_root, "Play.ps1");

        internal string Control => Path.Combine(_root, "Control.ps1");

        internal WindowsDesktopInteractionAdapter Interaction(IExternalProcessRunner runner, IForegroundLease lease) =>
            new(runner,
                Path.Combine(_root, "KnownFolderOpen.ps1"),
                Path.Combine(_root, "KnownFileOpen.ps1"),
                Path.Combine(_root, "DesktopSelectAll.ps1"),
                Path.Combine(_root, "DesktopKeyPress.ps1"))
            {
                ChordLease = lease,
            };

        internal WindowsDeviceControlAdapter Device(IExternalProcessRunner runner, IForegroundLease lease) =>
            new(Path.Combine(_root, "scans"), _root, runner) { KeysLease = lease };

        public void Dispose()
        {
            if (Directory.Exists(_root))
                Directory.Delete(_root, recursive: true);
        }
    }

    private sealed class CountingRunner(string output) : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Calls++;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, string.Empty));
        }
    }

    // A script that runs until it is stopped (the runner kills the process on cancellation).
    private sealed class BlockingRunner : IExternalProcessRunner
    {
        internal TaskCompletionSource Started { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);

        internal bool Cancelled { get; private set; }

        public async ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Started.TrySetResult();
            try
            {
                await Task.Delay(Timeout.Infinite, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                Cancelled = true;
                throw;
            }

            return new ExternalProcessResult(0, string.Empty, string.Empty);
        }
    }

    private sealed class ScriptedLease : IForegroundLease
    {
        internal string? Refusal { get; init; }

        internal List<FakeInputBurst> Bursts { get; } = [];

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken)
        {
            var burst = new FakeInputBurst { Refusal = Refusal };
            Bursts.Add(burst);
            return ValueTask.FromResult<IInputBurst>(burst);
        }

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            AcquireAsync(0, cancellationToken);
    }
}
