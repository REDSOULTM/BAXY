using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class BaxySettingHandlerTests
{
    // pc-ayudas: the accessible mode switched from the chat says what it changes (BAXY's own window) and which modes do
    // not exist yet, in the message the model reads, so «activé el modo para ciegos» has nothing to stand on.
    [Test]
    public async Task TheAccessibleModeSaysWhatItChangesAndWhatIsNotThereYet()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-accessible-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            string accessible = await SettingMessage(root, """{"setting":"accessible_mode","value":1}""");
            string bypass = await SettingMessage(root, """{"setting":"confirmation_bypass","value":0}""");
            using JsonDocument facts = JsonDocument.Parse(accessible);
            using JsonDocument other = JsonDocument.Parse(bypass);
            JsonElement observed = facts.RootElement.GetProperty("observed");
            JsonElement otherObserved = other.RootElement.GetProperty("observed");

            Assert.Multiple(() =>
            {
                Assert.That(facts.RootElement.GetProperty("status").GetString(), Is.EqualTo("completed"));
                Assert.That(observed.GetProperty("changed").GetBoolean(), Is.True);
                Assert.That(observed.GetProperty("scope").GetString(),
                    Is.EqualTo("BAXY's own window only: larger text, more contrast, wider buttons"));
                Assert.That(observed.GetProperty("notAvailableYet").GetString(),
                    Is.EqualTo("a blind (screen reader) mode and a hands-free mobility mode"));
                // Contracaso: BAXY's other setting says nothing of the modes.
                Assert.That(otherObserved.GetProperty("setting").GetString(), Is.EqualTo("confirmation_bypass"));
                Assert.That(otherObserved.TryGetProperty("scope", out _), Is.False);
                Assert.That(otherObserved.TryGetProperty("notAvailableYet", out _), Is.False);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static async Task<string> SettingMessage(string dataRoot, string arguments)
    {
        const string operation = "system.settings.set";
        var windows = new ExternalCapabilityHandler(operation, new NoWindowsSetting());
        OperationOutcome outcome = await new BaxySettingHandler(windows, dataRoot).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", Json(arguments)), CancellationToken.None);
        return OperationVisibleFacts.FromOutcome(operation, outcome);
    }

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    // BAXY's own settings never reach Windows' provider.
    private sealed class NoWindowsSetting : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            throw new AssertionException("a BAXY setting reached the Windows provider");
    }
}
