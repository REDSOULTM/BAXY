using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// display.mode.set (auditoría de los pedidos reales, 2026-10-17) against a fake display: no test changes the real
/// screen. Only a listed mode is applied, after CDS_TEST; the mode is read back, and a read-back that is not the mode
/// asked for puts the previous one back and says so.
/// </summary>
[TestFixture]
public sealed class DisplayModeAdapterTests
{
    private static readonly DisplayModeValue Now = new(1920, 1080, 144, 32);

    private static readonly DisplayModeValue[] Modes =
    [
        new(1920, 1080, 144, 32), new(1920, 1080, 60, 32), new(1920, 1080, 120, 32), new(1920, 1080, 75, 16),
        new(1280, 720, 60, 32), new(1280, 720, 100, 32), new(1600, 900, 144, 32),
    ];

    private static Task<ExternalCapabilityReceipt> Invoke(FakeDisplay display, object arguments) =>
        new WindowsDisplayModeAdapter(display).InvokeAsync(
            "display.mode.set", JsonSerializer.SerializeToElement(arguments), CancellationToken.None).AsTask();

    [Test]
    public async Task ListedRefreshRateIsTestedAppliedAndReadBack()
    {
        var display = new FakeDisplay(Now, Modes);

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(display.Tested, Is.EqualTo(new[] { new DisplayModeValue(1920, 1080, 60, 32) }));
            Assert.That(display.Applied, Is.EqualTo(new[] { new DisplayModeValue(1920, 1080, 60, 32) }));
            Assert.That(receipt.Result?.GetProperty("previous").GetProperty("refreshHz").GetUInt32(), Is.EqualTo(144u));
            Assert.That(receipt.Result?.GetProperty("final").GetProperty("refreshHz").GetUInt32(), Is.EqualTo(60u));
            Assert.That(receipt.Result?.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("windows_display_settings_readback"));
            Assert.That(receipt.Result?.GetProperty("monitor").GetString(), Is.EqualTo("primary"));
        });
    }

    [TestCase(75)] // listed only at another color depth
    [TestCase(30)] // not listed at all
    public async Task ModeTheDriverDoesNotListIsRefusedWithoutTouchingAnything(int hertz)
    {
        var display = new FakeDisplay(Now, Modes);

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = hertz });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("display_mode_not_listed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(display.Tested, Is.Empty);
            Assert.That(display.Applied, Is.Empty);
        });
    }

    [Test]
    public async Task FailedCdsTestChangesNothing()
    {
        var display = new FakeDisplay(Now, Modes) { TestResult = -2 };

        ExternalCapabilityReceipt receipt = await Invoke(display, new { width = 1280, height = 720, refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("display_mode_test_failed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(display.Tested, Has.Length.EqualTo(1));
            Assert.That(display.Applied, Is.Empty);
        });
    }

    [Test]
    public async Task ReadBackThatDiffersRevertsToThePreviousModeAndSaysSo()
    {
        // The driver accepts the mode but the screen reads back something else.
        var display = new FakeDisplay(Now, Modes) { Shows = mode => mode.RefreshHz == 60 ? mode with { RefreshHz = 59 } : mode };

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("display_mode_not_verified_reverted"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(display.Applied, Is.EqualTo(new[] { new DisplayModeValue(1920, 1080, 60, 32), Now }));
            Assert.That(display.Current("\\\\.\\DISPLAY1"), Is.EqualTo(Now));
        });
    }

    // FT/proveedores goal (review of receipts): Windows answers DISP_CHANGE_RESTART and keeps showing the old mode.
    // Renew al máximo (B-SYS-5): the change is only dynamic, so nothing was saved for the next sign-in either, and the
    // receipt says nothing changed.
    [Test]
    public async Task AModeWindowsWouldOnlyShowAfterARestartIsNeitherShownNorSaved()
    {
        var display = new FakeDisplay(Now, Modes) { AppliesNow = false, ApplyResults = new Queue<int>([1]) };

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("display_mode_not_applied"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(display.Applied, Is.EqualTo(new[] { new DisplayModeValue(1920, 1080, 60, 32) }));
            Assert.That(display.Saves, Is.Empty);
            Assert.That(display.Saved("\\\\.\\DISPLAY1"), Is.EqualTo(Now));
        });
    }

    // Renew al máximo (w8): Windows says DISP_CHANGE_SUCCESSFUL and the screen still reads the old mode: the change may
    // land later, so the receipt does not say nothing happened, and it keeps the mode read.
    [Test]
    public async Task ASuccessWindowsDoesNotShowYetMayHaveHappened()
    {
        var display = new FakeDisplay(Now, Modes) { AppliesNow = false };

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("display_mode_not_verified"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("stateAfter").GetProperty("shown").GetProperty("refreshHz").GetUInt32(),
                Is.EqualTo(144u));
        });
    }

    // Renew al máximo (w8): a mode not listed says what is listed, so the model can offer it.
    [Test]
    public async Task AModeNotListedSaysTheRatesOrResolutionsListed()
    {
        ExternalCapabilityReceipt rate = await Invoke(new FakeDisplay(Now, Modes), new { refreshHz = 59 });
        ExternalCapabilityReceipt size = await Invoke(new FakeDisplay(Now, Modes), new { width = 1024, height = 768 });

        Assert.Multiple(() =>
        {
            Assert.That(rate.ErrorCode, Is.EqualTo("display_mode_not_listed"));
            Assert.That(rate.EffectMayHaveOccurred, Is.False);
            Assert.That(rate.Result?.GetProperty("listedRefreshHz").EnumerateArray().Select(static hz => hz.GetUInt32()),
                Is.EqualTo(new uint[] { 144, 120, 60 }));
            Assert.That(size.ErrorCode, Is.EqualTo("display_mode_not_listed"));
            Assert.That(size.Result?.GetProperty("listedResolutions").EnumerateArray().Select(static r => r.GetString()),
                Is.EqualTo(new[] { "1920x1080", "1600x900", "1280x720" }));
        });
    }

    [Test]
    public async Task RevertThatDoesNotReadBackIsReportedAsAnObservedChange()
    {
        var display = new FakeDisplay(Now, Modes) { Shows = mode => mode with { RefreshHz = 59 } };

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("display_mode_revert_not_verified"));
            Assert.That(receipt.EffectObserved, Is.True);
        });
    }

    [Test]
    public async Task ResolutionAloneKeepsTheRefreshRateWhenListedElseTakesTheHighest()
    {
        var keeps = new FakeDisplay(Now, Modes);
        var highest = new FakeDisplay(Now, Modes);

        ExternalCapabilityReceipt kept = await Invoke(keeps, new { width = 1600, height = 900 });
        ExternalCapabilityReceipt top = await Invoke(highest, new { width = 1280, height = 720 });

        Assert.Multiple(() =>
        {
            Assert.That(keeps.Applied, Is.EqualTo(new[] { new DisplayModeValue(1600, 900, 144, 32) }));
            Assert.That(kept.Result?.GetProperty("refreshChosen").GetString(), Is.EqualTo("kept"));
            Assert.That(highest.Applied, Is.EqualTo(new[] { new DisplayModeValue(1280, 720, 100, 32) }));
            Assert.That(top.Result?.GetProperty("refreshChosen").GetString(), Is.EqualTo("highest_listed"));
        });
    }

    [Test]
    public async Task ModeAlreadyShownIsNotAppliedAgain()
    {
        var display = new FakeDisplay(Now, Modes);

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = 144 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result?.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(display.Applied, Is.Empty);
        });
    }

    // Renew al máximo (B-SYS-5): the read-back is what the graphics card took, not what the monitor shows. A mode the
    // monitor cannot show (a cable or adapter short of bandwidth) left the screen black, saved for every restart. The
    // change is now shown only (a restart brings back the saved mode); asking for the mode again while it is shown is
    // what saves it, and the saved mode is read back.
    [Test]
    public async Task AChangedModeIsShownButSavedOnlyWhenAskedAgainWhileShown()
    {
        var display = new FakeDisplay(Now, Modes);
        var sixty = new DisplayModeValue(1920, 1080, 60, 32);

        ExternalCapabilityReceipt shown = await Invoke(display, new { refreshHz = 60 });
        DisplayModeValue? savedAfterChange = display.Saved("\\\\.\\DISPLAY1");
        ExternalCapabilityReceipt kept = await Invoke(display, new { refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(savedAfterChange, Is.EqualTo(Now), "the change alone saves nothing");
            Assert.That(shown.Verified, Is.True);
            Assert.That(shown.Result?.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(shown.Result?.GetProperty("savedForRestart").GetBoolean(), Is.False);
            Assert.That(kept.Verified, Is.True);
            Assert.That(kept.EffectObserved, Is.True);
            Assert.That(kept.Result?.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(kept.Result?.GetProperty("savedForRestart").GetBoolean(), Is.True);
            Assert.That(display.Saves, Is.EqualTo(new[] { sixty }));
            Assert.That(display.Saved("\\\\.\\DISPLAY1"), Is.EqualTo(sixty));
        });
    }

    // Renew al máximo (w5): a mode shown and not saved was told «done» as if kept; with the aid display_restart the
    // result says a restart shows the saved mode again and how this one is kept. With BAXY_AYUDAS=none, the facts alone.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AModeShownButNotSavedSaysARestartShowsTheSavedOne(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var display = new FakeDisplay(Now, Modes);

        ExternalCapabilityReceipt shown = await Invoke(display, new { refreshHz = 60 });
        ExternalCapabilityReceipt kept = await Invoke(display, new { refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(shown.Result!.Value.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("1920x1080 at 60 Hz is shown now and not saved: the next restart "
                    + "or sign-in shows the mode Windows has saved; display_mode_set with this same mode again keeps it"));
            }
            Assert.That(kept.Result!.Value.TryGetProperty("next", out _), Is.False, "a saved mode needs no word");
        });
    }

    [Test]
    public async Task AModeShownAndAlreadySavedIsNeitherAppliedNorSaved()
    {
        var display = new FakeDisplay(Now, Modes);

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = 144 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result?.GetProperty("savedForRestart").GetBoolean(), Is.True);
            Assert.That(display.Applied, Is.Empty);
            Assert.That(display.Saves, Is.Empty);
        });
    }

    [Test]
    public async Task ASaveWindowsRefusesLeavesTheShownModeAndSaysItWasNotSaved()
    {
        var display = new FakeDisplay(Now, Modes) { SaveResult = -1 };
        await Invoke(display, new { refreshHz = 60 });

        ExternalCapabilityReceipt receipt = await Invoke(display, new { refreshHz = 60 });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("display_mode_not_saved"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(display.Saved("\\\\.\\DISPLAY1"), Is.EqualTo(Now));
        });
    }

    [TestCase("{}", "display_mode_not_given")]
    [TestCase("{\"width\":1280}", "display_resolution_needs_width_and_height")]
    public async Task IncompleteArgumentsAreRefusedBeforeReadingTheScreen(string json, string code)
    {
        var display = new FakeDisplay(Now, Modes);

        ExternalCapabilityReceipt receipt = await new WindowsDisplayModeAdapter(display).InvokeAsync(
            "display.mode.set", JsonDocument.Parse(json).RootElement, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(display.Applied, Is.Empty);
        });
    }

    private sealed class FakeDisplay(DisplayModeValue current, DisplayModeValue[] listed) : IDisplayModePlatform
    {
        private DisplayModeValue _current = current;
        private readonly List<DisplayModeValue> _tested = [];
        private readonly List<DisplayModeValue> _applied = [];

        internal int TestResult { get; init; }

        /// <summary>What the screen reads back after a mode is applied (by default, the mode itself).</summary>
        internal Func<DisplayModeValue, DisplayModeValue> Shows { get; init; } = static mode => mode;

        internal DisplayModeValue[] Tested => [.. _tested];

        internal DisplayModeValue[] Applied => [.. _applied];

        public string? PrimaryDevice() => "\\\\.\\DISPLAY1";

        public DisplayModeValue? Current(string device) => _current;

        public IReadOnlyList<DisplayModeValue> Listed(string device) => listed;

        public int Test(string device, DisplayModeValue mode)
        {
            _tested.Add(mode);
            return TestResult;
        }

        /// <summary>What Apply returns, in order (by default 0, DISP_CHANGE_SUCCESSFUL, every time).</summary>
        internal Queue<int> ApplyResults { get; init; } = new();

        /// <summary>Whether an applied mode shows now (false: Windows keeps it for a restart and the screen stays).</summary>
        internal bool AppliesNow { get; init; } = true;

        public int Apply(string device, DisplayModeValue mode)
        {
            _applied.Add(mode);
            if (AppliesNow)
                _current = Shows(mode);
            return ApplyResults.Count > 0 ? ApplyResults.Dequeue() : 0;
        }

        private DisplayModeValue _saved = current;
        private readonly List<DisplayModeValue> _saves = [];

        /// <summary>Every mode written to the registry (CDS_UPDATEREGISTRY), in order.</summary>
        internal DisplayModeValue[] Saves => [.. _saves];

        /// <summary>What Save returns (by default 0); a failed save writes nothing.</summary>
        internal int SaveResult { get; init; }

        public DisplayModeValue? Saved(string device) => _saved;

        // CDS_UPDATEREGISTRY also changes the screen, as Apply does.
        public int Save(string device, DisplayModeValue mode)
        {
            _saves.Add(mode);
            int result = Apply(device, mode);
            if (SaveResult != 0)
                return SaveResult;
            _saved = mode;
            return result;
        }
    }
}
