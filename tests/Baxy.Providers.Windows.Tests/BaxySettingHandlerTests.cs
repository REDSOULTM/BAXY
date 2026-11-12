using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Infrastructure;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class BaxySettingHandlerTests
{
    // pc-ayudas: the accessible mode switched from the chat says what it changes (BAXY's own window) and which modes do
    // not exist yet, in the message the model reads, so «activé el modo para ciegos» has nothing to stand on. Since
    // actualizar-ordenes-app it is baxy.settings.set's, with BAXY's other own switches.
    [Test]
    public async Task TheAccessibleModeSaysWhatItChangesAndWhatIsNotThereYet()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-accessible-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            string accessible = await OwnMessage(root, """{"setting":"accessible_mode","value":"on"}""");
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

    // With the aid off (BAXY_AYUDAS=none) the switch says what it said before: setting, value, changed.
    [Test]
    public async Task TheAccessibleModeWithTheAidOffSaysOnlyTheSwitch()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-accessible-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            using IDisposable off = ModelAids.Use("none");
            using JsonDocument facts = JsonDocument.Parse(
                await OwnMessage(root, """{"setting":"accessible_mode","value":"on"}"""));
            JsonElement observed = facts.RootElement.GetProperty("observed");

            Assert.Multiple(() =>
            {
                Assert.That(observed.GetProperty("changed").GetBoolean(), Is.True);
                Assert.That(observed.TryGetProperty("scope", out _), Is.False);
                Assert.That(observed.TryGetProperty("notAvailableYet", out _), Is.False);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // Revisión 2026-10-22 (C-3): a setting file another program holds locked cannot be read, and «I could not read it»
    // was taken for «off»: switching it off answered changed:false, done, while the file still said on. Unreadable is
    // its own failure, and nothing is written.
    [TestCase("baxy.settings.set", """{"setting":"accessible_mode","value":"off"}""", "presentation-mode", "accessible")]
    [TestCase("system.settings.set", """{"setting":"confirmation_bypass","value":0}""", "confirmation-mode", "bypass")]
    public async Task ASettingThatCannotBeReadIsNotTakenForOff(string operation, string arguments, string fileName, string stored)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-accessible-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        string path = Path.Combine(root, fileName);
        File.WriteAllText(path, stored);
        try
        {
            string message;
            using (new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.None))
            {
                message = operation == "baxy.settings.set" ? await OwnMessage(root, arguments) : await SettingMessage(root, arguments);
            }

            using JsonDocument facts = JsonDocument.Parse(message);
            Assert.Multiple(() =>
            {
                Assert.That(facts.RootElement.GetProperty("status").GetString(), Is.EqualTo("failed"));
                Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("baxy_setting_unreadable"));
                Assert.That(facts.RootElement.TryGetProperty("effectUncertain", out _), Is.False);
                Assert.That(File.ReadAllText(path), Is.EqualTo(stored));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // Encargo 25 (G2): switching bypass on through system.settings.set stays refused, with what is true instead of a bare
    // code: the mode it is in and (TPV1) the call that switches it on by voice with the person's «sí»; where BAXY's own
    // window turns it on stays beside.
    [Test]
    public async Task BypassOnSaysTheModeAndWhereTheWindowTurnsItOn()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-bypass-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            using JsonDocument facts = JsonDocument.Parse(
                await SettingMessage(root, """{"setting":"confirmation_bypass","value":1}"""));
            JsonElement observed = facts.RootElement.GetProperty("observed");

            Assert.Multiple(() =>
            {
                Assert.That(facts.RootElement.GetProperty("error").GetString(),
                    Is.EqualTo("confirmation_bypass_interface_only"));
                Assert.That(observed.GetProperty("mode").GetString(), Is.EqualTo("normal"));
                Assert.That(observed.GetProperty("turnOnIn").GetString(), Does.Contain("Ajustes > Confirmación"));
                Assert.That(observed.GetProperty("turnOnBySpeaking").GetString(), Is.EqualTo(
                    """baxy_settings_set {"setting":"confirmation_bypass","value":"on"} switches it on: BAXY asks the person's yes itself"""));
                Assert.That(observed.TryGetProperty("valuesByChat", out _), Is.False);
                Assert.That(File.Exists(Path.Combine(root, "confirmation-mode")), Is.False);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // BAXY_AYUDAS: unset or «all» turns every aid on, «none» or «0» none, a list only the ids it names.
    [TestCase("all", true, true)]
    [TestCase("", true, true)]
    [TestCase("none", false, false)]
    [TestCase("0", false, false)]
    [TestCase("accessible_scope", true, false)]
    [TestCase(" calculator_next , ACCESSIBLE_SCOPE", true, true)]
    public void TheAidsSettingTurnsOnTheAidsItNames(string setting, bool accessible, bool calculator)
    {
        using IDisposable use = ModelAids.Use(setting);
        Assert.Multiple(() =>
        {
            Assert.That(ModelAids.On(ModelAids.AccessibleScope), Is.EqualTo(accessible));
            Assert.That(ModelAids.On(ModelAids.CalculatorNext), Is.EqualTo(calculator));
        });
    }

    private static async Task<string> SettingMessage(string dataRoot, string arguments)
    {
        const string operation = "system.settings.set";
        var windows = new ExternalCapabilityHandler(operation, new NoWindowsSetting());
        OperationOutcome outcome = await new BaxySettingHandler(windows, dataRoot).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", Json(arguments)), CancellationToken.None);
        return OperationVisibleFacts.FromOutcome(operation, outcome);
    }

    private static async Task<string> OwnMessage(string dataRoot, string arguments)
    {
        OperationOutcome outcome = await new OwnSettingsHandler(dataRoot).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", Json(arguments)), CancellationToken.None);
        return OperationVisibleFacts.FromOutcome(OwnSettingsHandler.Operation, outcome);
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
