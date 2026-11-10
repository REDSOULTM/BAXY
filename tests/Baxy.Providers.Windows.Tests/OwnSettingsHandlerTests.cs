using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// pc-f6-ajustes (APLAZADOS f4-accesibilidad, «los ajustes del host sólo se cambian en la vista»): baxy.settings.set
/// writes the same file as the view's Settings and Proposals panels (FieldSettingsStore), keeps every other choice in
/// it, reads it back, and its result says the setting, its new value and, for a silence, until when.
/// </summary>
[TestFixture]
public sealed class OwnSettingsHandlerTests
{
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-own-settings-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    // Each switch lands on the view's own key (the voice is kept as voiceMuted), and what the view had chosen stays.
    [TestCase("voice", "off", "voiceMuted", true)]
    [TestCase("voice", "on", "voiceMuted", false)]
    [TestCase("overlay", "off", "overlay", false)]
    [TestCase("web_search", "off", "web", false)]
    [TestCase("no_interrupt_games", "off", "ctx.game", false)]
    [TestCase("no_interrupt_calls", "off", "ctx.call", false)]
    [TestCase("no_interrupt_videos", "off", "ctx.video", false)]
    public async Task ASwitchWritesTheViewsKeyAndSaysItsNewValue(string setting, string value, string key, bool stored)
    {
        FieldSettingsStore.Write(_root, new JsonObject { ["weather"] = false, ["voiceMuted"] = value == "on" });

        JsonElement observed = Observed(await Set(setting, value), out string status);
        JsonObject file = Read();

        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That(observed.GetProperty("setting").GetString(), Is.EqualTo(setting));
            Assert.That(observed.GetProperty("value").GetString(), Is.EqualTo(value));
            Assert.That(observed.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(observed.TryGetProperty("until", out _), Is.False);
            Assert.That((bool?)file[key], Is.EqualTo(stored));
            Assert.That((bool?)file["weather"], Is.False);
        });
    }

    // Already so: done, changed false (the view says «ya estaba así»).
    [Test]
    public async Task ASwitchAlreadySoSaysUnchanged()
    {
        JsonElement observed = Observed(await Set("web_search", "on"), out string status);

        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That(observed.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That((bool?)Read()["web"], Is.True);
        });
    }

    // «No me propongas nada hasta mañana»: silent until 08:00 local tomorrow, the span the view shows, and the result
    // says until when; «on» ends the silence.
    [Test]
    public async Task TheProposalsSilenceSaysUntilWhenAndOnEndsIt()
    {
        var now = new DateTimeOffset(2026, 10, 25, 23, 10, 0, TimeZoneInfo.Local.GetUtcOffset(new DateTime(2026, 10, 25, 23, 10, 0)));
        var clock = new FixedTime(now);
        DateTimeOffset expected = FieldSettingsStore.QuietUntil("tomorrow", now)!.Value;

        JsonElement silenced = Observed(await Set("proposals", "tomorrow", clock), out string status);
        JsonObject file = Read();
        JsonElement ended = Observed(await Set("proposals", "on", clock), out string endStatus);
        JsonObject after = Read();

        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That(silenced.GetProperty("value").GetString(), Is.EqualTo("tomorrow"));
            Assert.That(silenced.GetProperty("until").GetString(), Is.EqualTo("2026-10-26T08:00"));
            Assert.That((string?)file["quiet"], Is.EqualTo("tomorrow"));
            Assert.That((long?)file["quietUntil"], Is.EqualTo(expected.ToUnixTimeMilliseconds()));
            Assert.That(endStatus, Is.EqualTo("completed"));
            Assert.That(ended.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(ended.TryGetProperty("until", out _), Is.False);
            Assert.That(after["quietUntil"], Is.Null);
            Assert.That(after["quiet"], Is.Null);
        });
    }

    [Test]
    public async Task HalfAnHourIsThirtyMinutesFromNow()
    {
        var now = new DateTimeOffset(2026, 10, 25, 22, 0, 0, TimeSpan.Zero);
        Observed(await Set("proposals", "30m", new FixedTime(now)), out string status);

        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That((long?)Read()["quietUntil"], Is.EqualTo(now.AddMinutes(30).ToUnixTimeMilliseconds()));
        });
    }

    // A value that is not this setting's (the proposals have no «off» without a span; a switch has no span) changes
    // nothing. Encargo 25 (G2, uso real 02-11: proposals «off» answered a bare code and the reply was «BAXY siempre te
    // las propone»): the refusal names the argument and the values this setting takes; a setting BAXY does not have,
    // the settings it has.
    [TestCase("proposals", "off", "value", new[] { "30m", "1h", "tomorrow", "on" })]
    [TestCase("voice", "1h", "value", new[] { "on", "off" })]
    [TestCase("web_search", "tomorrow", "value", new[] { "on", "off" })]
    [TestCase("weather", "off", "setting", new[]
    {
        "accessible_mode", "confirmation_bypass", "no_interrupt_calls", "no_interrupt_games", "no_interrupt_videos", "overlay", "proposals",
        "voice", "web_search",
    })]
    public async Task AValueThatIsNotTheSettingsChangesNothing(string setting, string value, string argument, string[] allowed)
    {
        using JsonDocument facts = JsonDocument.Parse(await Set(setting, value));
        JsonElement problem = facts.RootElement.GetProperty("argumentProblems")[0];

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("status").GetString(), Is.EqualTo("failed"));
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("invalid_arguments"));
            Assert.That(problem.GetProperty("argument").GetString(), Is.EqualTo(argument));
            Assert.That(problem.GetProperty("allowed").EnumerateArray().Select(static item => item.GetString()),
                Is.EqualTo(allowed));
            Assert.That(File.Exists(Path.Combine(_root, FieldSettingsStore.FileName)), Is.False);
        });
    }

    // Encargo 25 (G2, uso real 02-11: «activa el modo Bypass» → «eso no es una opción que BAXY tenga»): the confirmation
    // mode is one of BAXY's own settings. Switching it on stays a gesture in BAXY's own window (identity), so from the
    // chat it is refused, nothing written, with what is true: the mode it is in and where the person turns it on.
    [Test]
    public async Task BypassOnIsRefusedWithTheModeAndWhereTheWindowTurnsItOn()
    {
        using JsonDocument facts = JsonDocument.Parse(await Set("confirmation_bypass", "on"));
        JsonElement observed = facts.RootElement.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("status").GetString(), Is.EqualTo("failed"));
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("confirmation_bypass_interface_only"));
            Assert.That(observed.GetProperty("setting").GetString(), Is.EqualTo("confirmation_bypass"));
            Assert.That(observed.GetProperty("mode").GetString(), Is.EqualTo("normal"));
            Assert.That(observed.GetProperty("valuesByChat").EnumerateArray().Select(static item => item.GetString()),
                Is.EqualTo(new[] { "off" }));
            Assert.That(observed.GetProperty("turnOnIn").GetString(), Does.Contain("Ajustes > Confirmación"));
            Assert.That(File.Exists(Path.Combine(_root, ConfirmationModeStore.FileName)), Is.False);
        });
    }

    // Switching it off is what the chat may do (as system.settings.set does): written, read back, changed.
    [Test]
    public async Task BypassOffByChatTurnsItOffAndReadsItBack()
    {
        ConfirmationModeStore.Write(_root, ConfirmationMode.Bypass);

        JsonElement observed = Observed(await Set("confirmation_bypass", "off"), out string status);
        JsonElement again = Observed(await Set("confirmation_bypass", "off"), out string againStatus);

        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That(observed.GetProperty("setting").GetString(), Is.EqualTo("confirmation_bypass"));
            Assert.That(observed.GetProperty("value").GetString(), Is.EqualTo("off"));
            Assert.That(observed.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(ConfirmationModeStore.Read(_root), Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(againStatus, Is.EqualTo("completed"));
            Assert.That(again.GetProperty("changed").GetBoolean(), Is.False);
        });
    }

    // A file another program holds locked is not «every switch at its default»: nothing is written over it.
    [Test]
    public async Task AFileThatCannotBeReadIsNotOverwritten()
    {
        string path = Path.Combine(_root, FieldSettingsStore.FileName);
        File.WriteAllText(path, """{"web":false}""");
        string message;
        using (new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            message = await Set("voice", "off");
        }

        using JsonDocument facts = JsonDocument.Parse(message);
        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("baxy_setting_unreadable"));
            Assert.That(File.ReadAllText(path), Is.EqualTo("""{"web":false}"""));
        });
    }

    private async Task<string> Set(string setting, string value, TimeProvider? time = null)
    {
        OperationOutcome outcome = await new OwnSettingsHandler(_root, time).ExecuteAsync(
            new OperationInvocation(
                "request", "mission", "invocation",
                JsonDocument.Parse($$"""{"setting":"{{setting}}","value":"{{value}}"}""").RootElement.Clone()),
            CancellationToken.None);
        return OperationVisibleFacts.FromOutcome(OwnSettingsHandler.Operation, outcome);
    }

    private static JsonElement Observed(string message, out string status)
    {
        using JsonDocument facts = JsonDocument.Parse(message);
        status = facts.RootElement.GetProperty("status").GetString() ?? string.Empty;
        return facts.RootElement.GetProperty("observed").Clone();
    }

    private JsonObject Read() =>
        FieldSettingsStore.TryRead(_root, out JsonObject values) ? values : throw new AssertionException("unreadable");

    private sealed class FixedTime(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now.ToUniversalTime();
    }
}
