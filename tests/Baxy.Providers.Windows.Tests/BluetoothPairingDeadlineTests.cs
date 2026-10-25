using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión nb-q-apps2: a pairing nobody answers (Windows' dialog left open) no longer holds the turn: the wait is
/// bounded and follows the turn's cancel. Fakes only: nothing is paired.
/// </summary>
[TestFixture]
public sealed class BluetoothPairingDeadlineTests
{
    [Test]
    public async Task APairingNobodyAnswersIsNotConfirmedWithinTheBound()
    {
        var pairing = new UnansweredPairing();
        (WindowsDeviceControlAdapter adapter, string deviceId) = await ListedAsync(pairing, TimeSpan.FromMilliseconds(100));

        Task<ExternalCapabilityReceipt> pair = adapter.InvokeAsync(
            "bluetooth.device.pair", Json($$"""{"deviceId":"{{deviceId}}"}"""), CancellationToken.None).AsTask();
        Task finished = await Task.WhenAny(pair, Task.Delay(TimeSpan.FromSeconds(10)));

        Assert.That(finished, Is.SameAs(pair), "the pairing held the turn");
        ExternalCapabilityReceipt receipt = await pair;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("bluetooth_pairing_not_confirmed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("pairingConfirmed").GetBoolean(), Is.False);
            Assert.That(pairing.Canceled, Is.True, "the unanswered pairing is given up");
        });
    }

    [Test]
    public async Task ACanceledTurnStopsWaitingForThePairing()
    {
        var pairing = new UnansweredPairing();
        (WindowsDeviceControlAdapter adapter, string deviceId) = await ListedAsync(pairing, TimeSpan.FromMinutes(5));
        using var turn = new CancellationTokenSource();

        Task<ExternalCapabilityReceipt> pair = adapter.InvokeAsync(
            "bluetooth.device.pair", Json($$"""{"deviceId":"{{deviceId}}"}"""), turn.Token).AsTask();
        await pairing.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
        turn.Cancel();
        Task finished = await Task.WhenAny(pair, Task.Delay(TimeSpan.FromSeconds(10)));

        Assert.That(finished, Is.SameAs(pair), "the canceled turn kept waiting for the pairing");
        ExternalCapabilityReceipt receipt = await pair;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    private static async Task<(WindowsDeviceControlAdapter, string)> ListedAsync(UnansweredPairing pairing, TimeSpan bound)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-bluetooth-pairing");
        var adapter = new WindowsDeviceControlAdapter(root, root, new NoProcessRunner(), new OneDeviceInventory())
        {
            BluetoothPairing = pairing,
            BluetoothPairTimeout = bound,
        };
        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "bluetooth.device.list", Json("{}"), CancellationToken.None);
        return (adapter, listed.Result!.Value.GetProperty("devices")[0].GetProperty("deviceId").GetString()!);
    }

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private sealed class OneDeviceInventory : IBluetoothDeviceInventory
    {
        public ValueTask<IReadOnlyList<BluetoothDeviceSnapshot>> ListAsync(CancellationToken cancellationToken) =>
            ValueTask.FromResult<IReadOnlyList<BluetoothDeviceSnapshot>>(
                [new BluetoothDeviceSnapshot("fake-native-id", "Auriculares", IsPaired: false, CanPair: true)]);
    }

    // Windows showing its pairing dialog and nobody answering it: PairAsync never completes by itself.
    private sealed class UnansweredPairing : IBluetoothPairing
    {
        internal TaskCompletionSource Started { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);

        internal bool Canceled { get; private set; }

        public ValueTask<BluetoothPairingState> ReadAsync(string nativeId, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new BluetoothPairingState("Auriculares", IsPaired: false, CanPair: true));

        public async ValueTask<bool> PairAsync(string nativeId, CancellationToken cancellationToken)
        {
            Started.TrySetResult();
            var unanswered = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            using CancellationTokenRegistration registration = cancellationToken.Register(() =>
            {
                Canceled = true;
                unanswered.TrySetCanceled(cancellationToken);
            });
            return await unanswered.Task;
        }
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            throw new AssertionException("no process is started for a pairing");
    }
}
