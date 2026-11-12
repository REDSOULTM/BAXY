using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// RUT2: display.status and display.monitor.set against a fake display topology: no test turns a real screen off. A
/// monitor is chosen by its position among the ones on or by being the primary one; the only monitor on is never turned
/// off; an unclear choice changes nothing; the topology is read back, and turning one back on says whether it came back
/// as it was.
/// </summary>
[TestFixture]
public sealed class MonitorAdapterTests
{
    private static MonitorState Left => new("m-left", "Corvia 24", true, false, -1920, 0, 1920, 1080, 60);

    private static MonitorState Main => new("m-main", "Lumo 27", true, true, 0, 0, 2560, 1440, 144);

    private static Task<ExternalCapabilityReceipt> Invoke(WindowsMonitorAdapter adapter, string operation, object arguments) =>
        adapter.InvokeAsync(operation, JsonSerializer.SerializeToElement(arguments), CancellationToken.None).AsTask();

    [Test]
    public async Task TheStatusSaysWhereEachMonitorIsAndWhichIsTheMainOne()
    {
        var display = new FakeTopology(Left, Main, new MonitorState("m-off", "Strato 22", false, false, 0, 0, 0, 0, 0));

        ExternalCapabilityReceipt receipt = await Invoke(new WindowsMonitorAdapter(display), "display.status", new { });

        JsonElement monitors = receipt.Result!.Value.GetProperty("monitors");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("monitorCount").GetInt32(), Is.EqualTo(2));
            Assert.That(monitors[0].GetProperty("position").GetString(), Is.EqualTo("left"));
            Assert.That(monitors[1].GetProperty("position").GetString(), Is.EqualTo("right"));
            Assert.That(monitors[1].GetProperty("primary").GetBoolean(), Is.True);
            Assert.That(monitors[2].GetProperty("active").GetBoolean(), Is.False);
        });
    }

    [TestCase("left")]
    [TestCase("secondary")]
    public async Task TheMonitorNamedByPlaceIsTurnedOffAndReadBack(string which)
    {
        var display = new FakeTopology(Left, Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = which });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(display.Calls, Is.EqualTo(new[] { ("m-left", false) }));
            Assert.That(receipt.Result!.Value.GetProperty("monitor").GetString(), Is.EqualTo("Corvia 24"));
            Assert.That(receipt.Result!.Value.GetProperty("position").GetString(), Is.EqualTo("left"));
            Assert.That(receipt.Result!.Value.TryGetProperty("baxyWindowThere", out _), Is.False);
        });
    }

    [Test]
    public async Task TheOnlyMonitorOnIsNeverTurnedOff()
    {
        var display = new FakeTopology(Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "primary" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.OnlyMonitor));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(display.Calls, Is.Empty);
        });
    }

    [Test]
    public async Task AnUnclearChoiceChangesNothingAndListsTheMonitors()
    {
        var right = new MonitorState("m-right", "Corvia 24", true, false, 2560, 0, 1920, 1080, 60);
        var display = new FakeTopology(Left, Main, right);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "secondary" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.Ambiguous));
            Assert.That(display.Calls, Is.Empty);
            Assert.That(receipt.Result!.Value.GetProperty("monitors").GetArrayLength(), Is.EqualTo(3));
            Assert.That(receipt.Result!.Value.GetProperty("monitors")[1].GetProperty("position").GetString(), Is.EqualTo("middle"));
        });
    }

    [Test]
    public async Task BaxysWindowOnTheMonitorTurnedOffIsSaid()
    {
        var display = new FakeTopology(Left, Main) { Windows = [(-1500, 100, 800, 600)] };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "left" });

        Assert.That(receipt.Result!.Value.GetProperty("baxyWindowThere").GetBoolean(), Is.True);
    }

    [Test]
    public async Task TurnedBackOnItSaysWhetherItCameBackAsItWas()
    {
        var display = new FakeTopology(Left, Main);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false, monitor = "left" });

        ExternalCapabilityReceipt receipt = await Invoke(adapter, "display.monitor.set", new { active = true });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(display.Calls, Is.EqualTo(new[] { ("m-left", false), ("m-left", true) }));
            Assert.That(receipt.Result!.Value.GetProperty("asBefore").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("position").GetString(), Is.EqualTo("left"));
        });
    }

    [Test]
    public async Task ATopologyThatDidNotChangeIsNoSuccess()
    {
        var display = new FakeTopology(Left, Main) { Ignores = true };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.NotVerified));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task AllOnAlreadyIsTheStateReached()
    {
        var display = new FakeTopology(Left, Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = true, monitor = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(display.Calls, Is.Empty);
        });
    }

    // Revisión ciega RUT2 (1): the one monitor off is turned back on only when what was asked does not contradict
    // where it was when BAXY turned it off.
    [Test]
    public async Task TurningOnTheOtherSideThanTheOneOffChangesNothing()
    {
        var display = new FakeTopology(Left, Main);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false, monitor = "left" });

        ExternalCapabilityReceipt receipt = await Invoke(adapter, "display.monitor.set", new { active = true, monitor = "right" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.NotFound));
            Assert.That(display.Calls, Is.EqualTo(new[] { ("m-left", false) }));
        });
    }

    // Revisión ciega RUT2 (6): with no monitor named and more than one it could be, the choice is unclear.
    [Test]
    public async Task TurningOffWithNoMonitorNamedIsAmbiguous()
    {
        var display = new FakeTopology(Left, Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.Ambiguous));
            Assert.That(display.Calls, Is.Empty);
        });
    }

    // Revisión ciega RUT2 (3): a monitor the read-back does not find is not «turned off».
    [Test]
    public async Task AMonitorMissingFromTheReadBackIsNoSuccess()
    {
        var display = new FakeTopology(Left, Main) { Vanishes = true };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.NotVerified));
        });
    }

    [Test]
    public void StackedMonitorsAreAboveAndBelow()
    {
        var top = new MonitorState("a", "A", true, false, 0, -1080, 1920, 1080, 60);
        var bottom = new MonitorState("b", "B", true, true, 0, 0, 1920, 1080, 60);

        Assert.Multiple(() =>
        {
            Assert.That(WindowsMonitorAdapter.Position(top, [top, bottom]), Is.EqualTo("above"));
            Assert.That(WindowsMonitorAdapter.Position(bottom, [top, bottom]), Is.EqualTo("below"));
            Assert.That(WindowsMonitorAdapter.Position(bottom, [bottom]), Is.EqualTo("only"));
        });
    }

    [Test]
    public void ARowWithOneUnderItIsLeftRightAndBelow()
    {
        var left = new MonitorState("l", "L", true, false, -1920, 0, 1920, 1080, 60);
        var main = new MonitorState("m", "M", true, true, 0, 0, 1920, 1080, 60);
        var under = new MonitorState("u", "U", true, false, -1000, 1080, 1920, 1080, 60);
        MonitorState[] on = [left, main, under];

        Assert.Multiple(() =>
        {
            Assert.That(WindowsMonitorAdapter.Position(left, on), Is.EqualTo("left"));
            Assert.That(WindowsMonitorAdapter.Position(main, on), Is.EqualTo("right"));
            Assert.That(WindowsMonitorAdapter.Position(under, on), Is.EqualTo("below"));
        });
    }

    private sealed class FakeTopology(params MonitorState[] monitors) : IMonitorPlatform
    {
        private readonly List<MonitorState> _monitors = [.. monitors];

        public List<(string, bool)> Calls { get; } = [];

        public bool Ignores { get; init; }

        public bool Vanishes { get; init; }

        public IReadOnlyList<(int X, int Y, int Width, int Height)> Windows { get; init; } = [];

        public IReadOnlyList<MonitorState> Monitors() => [.. _monitors];

        public int SetActive(string key, bool active)
        {
            Calls.Add((key, active));
            if (Vanishes)
            {
                _monitors.RemoveAll(monitor => monitor.Key == key);
                return 0;
            }

            if (!Ignores)
            {
                int index = _monitors.FindIndex(monitor => monitor.Key == key);
                _monitors[index] = active
                    ? monitors.First(monitor => monitor.Key == key)
                    : _monitors[index] with { Active = false, Primary = false, X = 0, Y = 0, Width = 0, Height = 0 };
            }

            return 0;
        }

        public IReadOnlyList<(int X, int Y, int Width, int Height)> ProductWindows() => Windows;
    }
}
