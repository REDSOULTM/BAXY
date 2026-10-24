using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.Devices.Radios;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (w8): a switched radio is read back every 100 ms until it shows the asked state, for 2 s at most,
/// through the radio seam (no real radio is touched).
/// </summary>
[TestFixture]
public sealed class RadioRereadTests
{
    [Test]
    public async Task BluetoothThatSettlesOnTheThirdReadIsVerified()
    {
        var bluetooth = new FakeRadio(RadioKind.Bluetooth, "Bluetooth", RadioState.Off, readsToSettle: 3);
        var delays = new List<TimeSpan>();
        WindowsDeviceControlAdapter adapter = Adapter(delays, bluetooth);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "bluetooth.radio.set", Json("""{"state":true}"""), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(receipt.EffectObserved, Is.True);
        Assert.That(bluetooth.Sets, Is.EqualTo(new[] { RadioState.On }));
        Assert.That(delays, Has.Count.EqualTo(2));
        Assert.That(delays, Is.All.EqualTo(TimeSpan.FromMilliseconds(100)));
    }

    [Test]
    public async Task WifiThatNeverSettlesFailsAfterTheHorizonWithTheLastRead()
    {
        var wifi = new FakeRadio(RadioKind.WiFi, "Wi-Fi", RadioState.On, readsToSettle: int.MaxValue);
        var delays = new List<TimeSpan>();
        WindowsDeviceControlAdapter adapter = Adapter(delays, wifi);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.radio.set", Json("""{"state":false}"""), CancellationToken.None);

        Assert.That(receipt.Verified, Is.False);
        Assert.That(receipt.ErrorCode, Is.EqualTo("wifi_radio_postread_failed"));
        Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        Assert.That(delays, Has.Count.EqualTo(20));
        JsonElement after = receipt.Result!.Value.GetProperty("stateAfter");
        Assert.That(after.GetProperty("requestedStateReached").GetBoolean(), Is.False);
        Assert.That(after.GetProperty("radios")[0].GetProperty("state").GetString(), Is.EqualTo("On"));
    }

    [Test]
    public async Task AirplaneModeWaitsForTheSlowestRadio()
    {
        var wifi = new FakeRadio(RadioKind.WiFi, "Wi-Fi", RadioState.On, readsToSettle: 1);
        var bluetooth = new FakeRadio(RadioKind.Bluetooth, "Bluetooth", RadioState.On, readsToSettle: 2);
        var delays = new List<TimeSpan>();
        WindowsDeviceControlAdapter adapter = Adapter(delays, wifi, bluetooth);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.set", Json("""{"setting":"airplane_mode","value":1}"""), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(receipt.Result!.Value.GetProperty("allRadiosOff").GetBoolean(), Is.True);
        Assert.That(delays, Has.Count.EqualTo(1));
    }

    [Test]
    public async Task ARadioAlreadyAsAskedIsReadOnceAndNotSwitched()
    {
        var bluetooth = new FakeRadio(RadioKind.Bluetooth, "Bluetooth", RadioState.On, readsToSettle: 0);
        var delays = new List<TimeSpan>();
        WindowsDeviceControlAdapter adapter = Adapter(delays, bluetooth);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "bluetooth.radio.set", Json("""{"state":true}"""), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True);
        Assert.That(receipt.StateAlreadyReached, Is.True);
        Assert.That(bluetooth.Sets, Is.Empty);
        Assert.That(delays, Is.Empty);
    }

    private static WindowsDeviceControlAdapter Adapter(List<TimeSpan> delays, params FakeRadio[] radios)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-radio-reread");
        return new WindowsDeviceControlAdapter(root, root, new NoProcessRunner(), (delay, token) =>
        {
            token.ThrowIfCancellationRequested();
            delays.Add(delay);
            return ValueTask.CompletedTask;
        })
        {
            Radios = new FakeRadioSet(radios),
        };
    }

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private sealed class FakeRadioSet(IReadOnlyList<FakeRadio> radios) : IRadioSet
    {
        public ValueTask<RadioAccessStatus> RequestAccessAsync() => ValueTask.FromResult(RadioAccessStatus.Allowed);

        public ValueTask<IReadOnlyList<IRadioHandle>> ListAsync()
        {
            foreach (FakeRadio radio in radios)
                radio.Listed();
            return ValueTask.FromResult<IReadOnlyList<IRadioHandle>>(radios.ToArray());
        }
    }

    // A radio whose SetStateAsync returns at once and whose state shows the change only from the n-th list after it.
    private sealed class FakeRadio(RadioKind kind, string name, RadioState state, int readsToSettle) : IRadioHandle
    {
        private RadioState? _pending;
        private int _reads;

        internal List<RadioState> Sets { get; } = [];

        public RadioKind Kind => kind;

        public string Name => name;

        public RadioState State { get; private set; } = state;

        internal void Listed()
        {
            if (_pending is { } pending && ++_reads >= readsToSettle)
            {
                State = pending;
                _pending = null;
            }
        }

        public ValueTask<RadioAccessStatus> SetStateAsync(RadioState requested)
        {
            Sets.Add(requested);
            _pending = requested;
            _reads = 0;
            return ValueTask.FromResult(RadioAccessStatus.Allowed);
        }
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            throw new AssertionException("no process is started for a radio");
    }
}
