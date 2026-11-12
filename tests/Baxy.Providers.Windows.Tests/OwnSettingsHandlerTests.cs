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
    [TestCase("screen", "off", "screen", false)]
    [TestCase("wake_sound", "off", "wakeSound", false)]
    [TestCase("echo_cancel", "off", "echoCancel", false)]
    [TestCase("wait_notice", "off", "waitNotice", false)]
    [TestCase("update_notice", "off", "updateNotice", false)]
    [TestCase("close_to_tray", "off", "closeToTray", false)]
    [TestCase("minimize_to_tray", "on", "minimizeToTray", true)]
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
    [TestCase("tool_profile", "on", "value", new[] { "esencial", "diario", "avanzado", "completo" })]
    [TestCase("voice", "diario", "value", new[] { "on", "off" })]

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

    // A setting BAXY does not have: with more settings than a refusal lists (OperationArgumentValidator.AllowedShown), the
    // nearest one it has (TPV1: Ajustes' other switches made them 18).
    [Test]
    public async Task ASettingBaxyDoesNotHaveIsRefusedWithTheNearestItHas()
    {
        using JsonDocument facts = JsonDocument.Parse(await Set("web", "on"));
        JsonElement problem = facts.RootElement.GetProperty("argumentProblems")[0];

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("invalid_arguments"));
            Assert.That(problem.GetProperty("argument").GetString(), Is.EqualTo("setting"));
            Assert.That(problem.GetProperty("nearest").GetString(), Is.EqualTo("web_search"));
            Assert.That(File.Exists(Path.Combine(_root, FieldSettingsStore.FileName)), Is.False);
        });
    }

    // Encargo 25 (G2, uso real 02-11: «activa el modo Bypass» → «eso no es una opción que BAXY tenga»): the confirmation
    // mode is one of BAXY's own settings. TPV1 (dueño, 10-11: everything by voice; the person may have no hands): the chat
    // switches it on too, once the person said «sí» (the App always asks it, OwnBrakes), written and read back.
    [Test]
    public async Task BypassOnByChatTurnsItOnAndReadsItBack()
    {
        JsonElement observed = Observed(await Set("confirmation_bypass", "on"), out string status);

        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That(observed.GetProperty("setting").GetString(), Is.EqualTo("confirmation_bypass"));
            Assert.That(observed.GetProperty("value").GetString(), Is.EqualTo("on"));
            Assert.That(observed.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(ConfirmationModeStore.Read(_root), Is.EqualTo(ConfirmationMode.Bypass));
        });
    }

    // TPV1 (dueño, 10-11: «pásate al perfil Completo» by voice): a ready-made tool profile lands in the file Settings →
    // Tools keeps, read back; Completo is the file's absence; and the receipt says when its tools come, so a reply never
    // claims a tool this turn does not have. MUS1 (VIVO13: «BAXY se reiniciará en unos segundos», and the App did not
    // restart): what happens is typed, the model gets ready again after the reply while the App and the conversation
    // stay, with no prose about a restart to paraphrase.
    [Test]
    public async Task AToolProfileIsKeptReadBackAndSaysWhenItsToolsCome()
    {
        string path = Path.Combine(_root, ToolProfileStore.FileName);
        JsonElement diario = Observed(await Set("tool_profile", "diario"), out string status);
        string kept = File.ReadAllText(path);
        JsonElement again = Observed(await Set("tool_profile", "diario"), out _);
        JsonElement completo = Observed(await Set("tool_profile", "completo"), out _);

        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That(diario.GetProperty("value").GetString(), Is.EqualTo("diario"));
            Assert.That(diario.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(diario.GetProperty("toolsFrom").GetString(), Is.EqualTo("next_request"));
            Assert.That(diario.GetProperty("modelGetsReady").GetString(), Is.EqualTo("after_this_reply"));
            Assert.That(diario.GetProperty("appStaysOpen").GetBoolean(), Is.True);
            Assert.That(diario.GetProperty("conversationKept").GetBoolean(), Is.True);
            Assert.That(diario.TryGetProperty("applies", out _), Is.False);
            Assert.That(diario.GetRawText(), Does.Not.Contain("restart"));
            Assert.That(kept, Is.EqualTo("""{"profile":"diario"}"""));
            Assert.That(again.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(again.TryGetProperty("toolsFrom", out _), Is.False);
            Assert.That(completo.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(File.Exists(path), Is.False);
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

    // APP2 (REV11 A-4): a tool profile file that names no profile (a broken write) was read as Completo: «pásate a
    // Completo» answered «unchanged» while the App, which keeps the last profile read, withheld the tools. REM1 (REV12
    // B-2): it then answered baxy_setting_unreadable to every «pásate a…», for good, and the voice could not mend it.
    // Reading it again will not mend it either: the profile the person asks for is written over it, read back, changed.
    [TestCase("""{"profile":"esenc""", "diario")]
    [TestCase("""["esencial"]""", "diario")]
    [TestCase("""{"profile":"esenc""", "completo")]
    public async Task ABrokenToolProfileFileIsReplacedByTheProfileAskedFor(string written, string asked)
    {
        string path = Path.Combine(_root, ToolProfileStore.FileName);
        File.WriteAllText(path, written);

        JsonElement set = Observed(await Set("tool_profile", asked), out string status);
        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That(set.GetProperty("value").GetString(), Is.EqualTo(asked));
            Assert.That(set.GetProperty("repaired").GetBoolean(), Is.True);
            Assert.That(ToolProfileStore.TryRead(_root, out string now) && now == asked, Is.True);
        });
    }

    // REM3 (REV13 D-1): the file broke with BAXY running and the person asked for the profile the App had kept: the
    // receipt said changed and that the model gets ready after the reply, and nothing restarted (ToolProfile.NeedsSwitch
    // compares with what the mind started with, which this process does not know). What is known is typed: the file
    // was repaired; whether the tools in effect change is not known here, and the model gets ready only if they do.
    [Test]
    public async Task ARepairedToolProfileFileDoesNotPromiseARestartItCannotKnow()
    {
        File.WriteAllText(Path.Combine(_root, ToolProfileStore.FileName), """{"profile":"esenc""");

        JsonElement set = Observed(await Set("tool_profile", "diario"), out string status);
        JsonElement again = Observed(await Set("tool_profile", "diario"), out _);

        Assert.Multiple(() =>
        {
            Assert.That(status, Is.EqualTo("completed"));
            Assert.That(set.GetProperty("repaired").GetBoolean(), Is.True);
            Assert.That(set.TryGetProperty("changed", out _), Is.False, "not known here");
            Assert.That(set.GetProperty("modelGetsReady").GetString(), Is.EqualTo("after_this_reply_if_its_tools_differ"));
            Assert.That(set.GetProperty("appStaysOpen").GetBoolean(), Is.True);
            Assert.That(again.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(again.TryGetProperty("repaired", out _), Is.False);
        });
    }

    // The control: a tool profile file another program holds a moment is not broken: nothing is written over it.
    [Test]
    public async Task ALockedToolProfileFileIsNotOverwritten()
    {
        string path = Path.Combine(_root, ToolProfileStore.FileName);
        File.WriteAllText(path, """{"profile":"esencial"}""");
        string message;
        using (new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            message = await Set("tool_profile", "completo");
        }

        using JsonDocument facts = JsonDocument.Parse(message);
        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("baxy_setting_unreadable"));
            Assert.That(File.ReadAllText(path), Is.EqualTo("""{"profile":"esencial"}"""));
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
