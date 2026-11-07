using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// N9 (L5, 2026-11-05): a PC whose processor or integrated GPU reads the model too slowly. Five relaunches that read at the
/// same pace would have taken hours to end in a breakdown that names no cause, and a read that fits its limit but takes
/// 17 min was a spinner and a count of seconds, nothing the person could tell from a hang.
/// </summary>
[TestFixture]
public sealed class SlowMachineStartTests
{
    private static JsonObject TooSlow() => new()
    {
        ["reply"] = new JsonObject
        {
            ["catalog.configure"] = new JsonObject
            {
                ["type"] = "error",
                ["startup"] = new JsonObject { ["cause"] = "lectura_lenta", ["tokensPerS"] = 20, ["needMinutes"] = 41 },
            },
        },
    };

    [Test]
    public void TheCauseCarriesItsFigures()
    {
        // As it comes from the mind: read from its line.
        MindStartupFailure? failure = MindStartupFailure.FromReply(JsonNode.Parse(TooSlow()["reply"]!["catalog.configure"]!.ToJsonString())!.AsObject());

        Assert.Multiple(() =>
        {
            Assert.That(failure?.Cause, Is.EqualTo(MindStartupFailure.ReadTooSlow));
            Assert.That(failure?.TokensPerS, Is.EqualTo(20));
            Assert.That(failure?.NeedMinutes, Is.EqualTo(41));
        });
    }

    [Test]
    public async Task AReadTooSlowIsSaidAtOnceAndNotReadAgain()
    {
        using var fake = new FakeMind();
        fake.Script(TooSlow());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            (_, JsonObject agent) = await view.SendAsync("GET", "/agent/status");

            Assert.Multiple(() =>
            {
                Assert.That(viewModel.Failure, Is.EqualTo(MainWindowViewModel.EngineUnavailable),
                    "the same pace again would take as long: no relaunch");
                Assert.That(viewModel.IsMindPreparing, Is.False);
                Assert.That((string?)agent["failureCause"], Is.EqualTo("lectura_lenta"));
                Assert.That(agent["failureRead"]?.ToJsonString(), Is.EqualTo("""{"tokens_per_s":20,"minutes":41}"""));
                Assert.That(fake.Seen.Count(static seen => seen == "catalog.configure"), Is.EqualTo(1));
            });
        }
    }

    [Test]
    public async Task ThePersonMayStillAskForAnotherTry()
    {
        // The PC may only have been busy: «Reintentar» is theirs.
        using var fake = new FakeMind();
        fake.Script(TooSlow());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.RetryEngine(), Is.True);
            Assert.That(viewModel.Failure, Is.Not.EqualTo(MainWindowViewModel.EngineUnavailable));
        }
    }

    [Test]
    public async Task AnotherCauseIsRelaunchedAsBefore()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject
                {
                    ["type"] = "error",
                    ["startup"] = new JsonObject { ["cause"] = "ram_insuficiente" },
                },
            },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            (_, JsonObject agent) = await view.SendAsync("GET", "/agent/status");

            Assert.Multiple(() =>
            {
                Assert.That(viewModel.Failure, Is.Not.EqualTo(MainWindowViewModel.EngineUnavailable));
                Assert.That(viewModel.IsMindPreparing, Is.True, "a relaunch waits its turn");
                Assert.That(agent["failureRead"], Is.Null);
            });
        }
    }

    [Test]
    public async Task WhileTheModelReadsTheViewIsToldHowFarAndWhyItIsSlow()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject
                {
                    ["every"] = 0.05,
                    ["count"] = 3,
                    ["facts"] = new JsonObject { ["secondsLeft"] = 600, ["onProcessor"] = true },
                },
            },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);

            List<JsonObject> boots = [.. view.Sink.Events.Where(static e => (string?)e["type"] == "boot")];
            JsonObject? reading = boots.FirstOrDefault(static e => e["reading"] is not null);
            Assert.That(reading, Is.Not.Null, "no boot event told the read");
            Assert.Multiple(() =>
            {
                Assert.That(reading!["reading"]?["total"]?.GetValue<long>(), Is.EqualTo(3));
                Assert.That(reading["reading"]?["seconds_left"]?.GetValue<long>(), Is.EqualTo(600));
                Assert.That((bool?)reading["onProcessor"], Is.True);
                Assert.That(boots[^1]["reading"], Is.Null, "a mind that is up reads nothing");
            });
        }
    }

    // The reader's thread cannot publish to the view: WebView2 only takes the UI thread, and its failure is swallowed
    // (FieldUiBridge): the percentage and the processor would never be shown, with every test here green. Found by a blind
    // review. On a context of its own, as the App's, a line of progress waits for that context.
    [Test]
    public async Task TheReadReachesTheViewOnTheUiThread()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject
                {
                    ["every"] = 0,
                    ["count"] = 2,
                    ["facts"] = new JsonObject { ["onProcessor"] = true },
                },
            },
        });
        var ui = new CountingContext();
        SynchronizationContext? before = SynchronizationContext.Current;
        SynchronizationContext.SetSynchronizationContext(ui);
        var viewModel = new MainWindowViewModel();
        SynchronizationContext.SetSynchronizationContext(before);
        await using (viewModel)
        {
            var seenOn = new List<bool>();
            viewModel.PropertyChanged += (_, change) =>
            {
                if (change.PropertyName == nameof(MainWindowViewModel.MindReading))
                {
                    seenOn.Add(CountingContext.Inside);
                }
            };
            await ViewModelHarness.StartMindAsync(viewModel);
            await ui.DrainAsync();

            Assert.That(ui.Posted, Is.GreaterThanOrEqualTo(1), "the read was not posted to the UI context");
            Assert.That(seenOn.All(static inside => inside), Is.True, "told off the UI context");
        }
    }

    [Test]
    public async Task AStartThatIsNoLongerStartingDoesNotBringBackItsRead()
    {
        using var fake = new FakeMind();
        fake.Script(TooSlow());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            typeof(MainWindowViewModel)
                .GetMethod("OnMindReading", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!
                .Invoke(viewModel, [new MindModelReading(1, 2, 3, true)]);
            await Task.Delay(100);

            Assert.That(viewModel.MindReading, Is.Null, "a late line of a start that ended");
        }
    }

    [Test]
    public async Task AnotherStartDoesNotInheritTheProcessorOfTheLastOne()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject
                {
                    ["every"] = 0,
                    ["count"] = 1,
                    ["facts"] = new JsonObject { ["onProcessor"] = true },
                },
            },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(viewModel.MindOnProcessor, Is.True);

            fake.Script(new JsonObject());
            await ViewModelHarness.StopMindForRestartAsync(viewModel);
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.MindOnProcessor, Is.False);
        }
    }

    [Test]
    public async Task AMindThatCameUpAfterAReadTooSlowEndsTheBreakdown()
    {
        using var fake = new FakeMind();
        fake.Script(TooSlow());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(viewModel.Failure, Is.EqualTo(MainWindowViewModel.EngineUnavailable));

            fake.Script(new JsonObject());
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.IsMindReady, Is.True);
            Assert.That(viewModel.Failure, Is.Null, "a BAXY that works shows no breakdown");
        }
    }

    private sealed class CountingContext : SynchronizationContext
    {
        [ThreadStatic]
        private static bool t_inside;
        private int _pending;

        internal static bool Inside => t_inside;

        internal int Posted { get; private set; }

        public override void Post(SendOrPostCallback callback, object? state)
        {
            Posted++;
            Interlocked.Increment(ref _pending);
            ThreadPool.QueueUserWorkItem(_ =>
            {
                t_inside = true;
                try
                {
                    callback(state);
                }
                finally
                {
                    t_inside = false;
                    Interlocked.Decrement(ref _pending);
                }
            });
        }

        internal async Task DrainAsync()
        {
            while (Volatile.Read(ref _pending) > 0)
            {
                await Task.Delay(10);
            }
        }
    }

    [Test]
    public async Task AMindWithAGpuSaysNothingOfTheProcessor()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject
                {
                    ["every"] = 0,
                    ["count"] = 1,
                    ["facts"] = new JsonObject { ["onProcessor"] = false },
                },
            },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(view.Sink.Events.Where(static e => (string?)e["type"] == "boot")
                .All(static e => (bool?)e["onProcessor"] != true), Is.True);
        }
    }

    // W1 (REL4, 1.2.x and 1.3.0): the first start after installing said «The model isn't available» for ~25 s while the
    // runtime's files were still being checked (no hash cache yet): nothing had been tried, so nothing had failed.
    [Test]
    public async Task WhileTheRuntimeIsCheckedTheModelIsOnItsWayNotUnavailable()
    {
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            // What the shell's start does before it checks the runtime (InitializeAsync).
            viewModel.MarkStartupMindPending();
            (int status, JsonObject agent) = await view.SendAsync("GET", "/agent/status");

            Assert.Multiple(() =>
            {
                Assert.That(status, Is.EqualTo(200));
                Assert.That(viewModel.MindFailed, Is.False);
                Assert.That(viewModel.IsMindPreparing, Is.True);
                Assert.That((string?)agent["failure"], Is.Null);
                Assert.That((string?)view.Channel.BootEvent()["failed"], Is.Null);
            });
        }
    }

    // The count of seconds the view shows runs from the check: the first start of the mind does not set it back to zero
    // halfway through the wait.
    [Test]
    public async Task TheFirstStartKeepsCountingFromTheCheckOfTheRuntime()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            viewModel.MarkStartupMindPending();
            DateTimeOffset checking = viewModel.MindStartedAt;
            await Task.Delay(50);
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.IsMindReady, Is.True);
            Assert.That(viewModel.MindStartedAt, Is.EqualTo(checking));
        }
    }

    // Nothing started (a window whose start never reached the mind): a turn ends as «mind_unavailable» at once, it does
    // not wait for a mind that is not coming (the W1 suite hung here with a state that counted as on its way).
    [Test]
    public void WithNoStartUnderWayTheModelIsNotSaidToBeOnItsWay()
    {
        var viewModel = new MainWindowViewModel();

        Assert.That(viewModel.IsMindPreparing, Is.False);
    }
}
