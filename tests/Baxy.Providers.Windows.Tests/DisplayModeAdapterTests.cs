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

        public int Apply(string device, DisplayModeValue mode)
        {
            _applied.Add(mode);
            _current = Shows(mode);
            return 0;
        }
    }
}
