using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// REOPEN1957 H0170/H0376 «conectate al wifi de casa» (D24): «casa» is a place,
/// not a profile. Naming the profile and the place together connects it and
/// records the association; the place alone then connects the remembered
/// profile; an unknown place fails before any effect.
/// </summary>
[TestFixture]
public sealed class WifiPlaceAliasTests
{
    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private sealed class SequencedRunner(IReadOnlyList<string> outputs) : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            string output = outputs[Math.Min(Calls, outputs.Count - 1)];
            Calls++;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-wifi-place-tests-" + Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    [Test]
    public async Task UnknownPlaceFailsBeforeAnyEffectAndTheAnswerRecordsIt()
    {
        using TemporaryDirectory temporary = new();
        var runner = new SequencedRunner([
            "{\"profiles\":[\"Fibertel-2G\",\"Vecino\"]}",
            "{\"profiles\":[\"Fibertel-2G\",\"Vecino\"]}",
            "",
            "{\"connected\":true,\"profile\":\"Fibertel-2G\"}",
            "{\"profiles\":[\"Fibertel-2G\",\"Vecino\"]}",
            "",
            "{\"connected\":true,\"profile\":\"Fibertel-2G\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path, runner, static (_, _) => ValueTask.CompletedTask);

        ExternalCapabilityReceipt unknown = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"casa","place":"casa"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt answered = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"fibertel","place":"casa"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt remembered = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"casa","place":"casa"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(unknown.Verified, Is.False);
            Assert.That(unknown.EffectObserved, Is.False);
            Assert.That(unknown.ErrorCode, Is.EqualTo("wifi_place_unknown"));
            Assert.That(answered.Verified, Is.True);
            Assert.That(answered.Result?.GetProperty("place").GetString(), Is.EqualTo("casa"));
            Assert.That(answered.Result?.GetRawText(), Does.Not.Contain("Fibertel"));
            Assert.That(remembered.Verified, Is.True);
            Assert.That(remembered.Result?.GetProperty("connected").GetBoolean(), Is.True);
            Assert.That(remembered.Result?.GetProperty("place").GetString(), Is.EqualTo("casa"));
            Assert.That(runner.Calls, Is.EqualTo(7));
            Assert.That(File.ReadAllText(Path.Combine(temporary.Path, "wifi-places.v1.json")), Does.Contain("\"casa\":\"Fibertel-2G\""));
        });
    }

    [Test]
    public async Task ANameThatIsNotSavedStaysAnHonestNotFoundWithoutAPlace()
    {
        using TemporaryDirectory temporary = new();
        var runner = new SequencedRunner(["{\"profiles\":[\"Fibertel-2G\"]}"]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path, runner, static (_, _) => ValueTask.CompletedTask);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"la luna"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("wifi_profile_not_found"));
            Assert.That(File.Exists(Path.Combine(temporary.Path, "wifi-places.v1.json")), Is.False);
        });
    }
}
