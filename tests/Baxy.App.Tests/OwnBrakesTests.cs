using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// COR1 (VIVO3 A3, 2026-11-10, 2 de 2): BAXY's own brakes are the person's to relax (src/Baxy.App/OwnBrakes.cs,
/// NetworkEgress.Holds). The phrases here are not the held-out ones of the bench (casos/cor1_ho.json).
/// </summary>
[TestFixture]
public sealed class OwnBrakesTests
{
    private const string Refused = "{\"status\":\"rejected\",\"error\":\"web_disabled_by_owner\"}";

    private static JsonObject Set(string setting, string value) => new() { ["setting"] = setting, ["value"] = value };

    // The row of the live test: the video is refused, and the model's next call switches the web search back on.
    [Test]
    public void ABrakeRelaxedAfterAnotherCallOfTheTurnWaits()
    {
        var egress = new NetworkEgress();
        egress.Heard("Busca en YouTube un vídeo de cómo hacer pan amasado");
        egress.Observed("media.play.youtube", Refused);

        Assert.That(egress.Holds(OwnBrakes.Operation, Set("web_search", "on")), Is.EqualTo(OwnBrakes.Cause));
    }

    // A clause of this turn's words ends in the setting's own name, and nothing was called before: the person asked for it.
    [TestCase("Enciende la búsqueda web", "web_search", "on")]
    [TestCase("Oye, activa de nuevo la busqueda web, por favor.", "web_search", "on")]
    [TestCase("please turn on web search", "web_search", "on")]
    [TestCase("ya puedes usar tu voz", "voice", "on")]
    [TestCase("vuelve a hacerme propuestas", "proposals", "on")]
    [TestCase("puedes hablarme durante las llamadas", "no_interrupt_calls", "off")]
    [TestCase("you can interrupt me in games", "no_interrupt_games", "off")]
    public void ABrakeThePersonNamedNowGoes(string words, string setting, string value)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);

        Assert.That(egress.Holds(OwnBrakes.Operation, Set(setting, value)), Is.Null);
    }

    // Their words name no setting, or name another one: the change is the model's own idea, first call or not.
    [TestCase("pon un vídeo de recetas de pan", "web_search", "on")]
    [TestCase("cuéntame qué tiempo hará mañana", "web_search", "on")]
    [TestCase("avísame cuando termine la descarga", "proposals", "on")]
    [TestCase("lee esto que te escribo", "voice", "on")]
    [TestCase("enciende la búsqueda web", "no_interrupt_calls", "off")]
    // Revisión ciega del diff: the name said as the way to ask for something else, with the change as the turn's first
    // call (a model that already knows the switch is off), and its words apart or followed by more.
    [TestCase("haz una búsqueda web de panaderías abiertas hoy", "web_search", "on")]
    [TestCase("search the web for bakeries open today", "web_search", "on")]
    [TestCase("pues haz una búsqueda en la web de panaderías", "web_search", "on")]
    [TestCase("activa la busqueda en la web por favor", "web_search", "on")]
    [TestCase("sube la voz de la película", "voice", "on")]
    public void ABrakeThePersonDidNotNameWaits(string words, string setting, string value)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);

        Assert.That(egress.Holds(OwnBrakes.Operation, Set(setting, value)), Is.EqualTo(OwnBrakes.Cause));
    }

    // Named while asking for something else («haz una búsqueda web de…»): the search is refused first, so the change
    // that comes after it waits. Named in an earlier turn only, it waits too.
    [Test]
    public void TheNameSaidForSomethingElseOrInAnotherTurnDoesNotRelaxIt()
    {
        var after = new NetworkEgress();
        after.Heard("haz una búsqueda web de panaderías abiertas hoy");
        after.Observed("web.search", Refused);

        var earlier = new NetworkEgress();
        earlier.Heard("enciende la búsqueda web");
        earlier.Heard("pon un vídeo de recetas de pan");

        Assert.Multiple(() =>
        {
            Assert.That(after.Holds(OwnBrakes.Operation, Set("web_search", "on")), Is.EqualTo(OwnBrakes.Cause));
            Assert.That(earlier.Holds(OwnBrakes.Operation, Set("web_search", "on")), Is.EqualTo(OwnBrakes.Cause));
        });
    }

    // Tightening a brake, and the settings that are none, never wait: whatever the words.
    [TestCase("web_search", "off")]
    [TestCase("voice", "off")]
    [TestCase("proposals", "tomorrow")]
    [TestCase("no_interrupt_calls", "on")]
    [TestCase("overlay", "on")]
    [TestCase("accessible_mode", "on")]
    [TestCase("confirmation_bypass", "off")]
    public void TighteningABrakeOrASettingThatIsNoneGoes(string setting, string value)
    {
        var egress = new NetworkEgress();
        egress.Heard("pon un vídeo de recetas de pan");
        egress.Observed("media.play.youtube", Refused);

        Assert.That(egress.Holds(OwnBrakes.Operation, Set(setting, value)), Is.Null);
    }

    // Every setting the catalog's baxy.settings.set takes is either a brake here, with the value that relaxes it, or
    // named as none: a new one cannot be left out by omission.
    [Test]
    public void EverySettingOfTheCatalogIsWeighed()
    {
        Assert.That(Baxy.Kernel.Operations.ProductCatalog.TryGet(OwnBrakes.Operation, out var descriptor), Is.True);
        string[] settings = [.. descriptor!.ArgumentsSchema.Properties
            .Single(static property => property.Name == "setting").AllowedValues!];
        string[] brakes = [.. settings.Where(static setting => OwnBrakes.Relaxed(OwnBrakes.Operation, Set(setting, Relaxing(setting))) is not null)];

        Assert.Multiple(() =>
        {
            Assert.That(brakes, Is.EquivalentTo(new[]
            {
                "confirmation_bypass", "no_interrupt_calls", "no_interrupt_games", "no_interrupt_videos", "proposals",
                "screen", "tool_profile", "update_notice", "voice", "weather", "web_search",
            }));
            Assert.That(settings.Except(brakes), Is.EquivalentTo(new[]
            {
                "accessible_mode", "close_to_tray", "echo_cancel", "minimize_to_tray", "overlay",
                "wait_notice", "wake_sound",
            }));
            foreach (string setting in settings)
            {
                string value = setting == OwnBrakes.ToolProfile ? "diario" : "on";
                Assert.That(OwnBrakes.Shown(OwnBrakes.Operation, Set(setting, value), english: false), Is.Not.Null, setting);
                Assert.That(OwnBrakes.Shown(OwnBrakes.Operation, Set(setting, value), english: true), Is.Not.Null, setting);
                Assert.That(OwnBrakes.Names(setting, Set(setting, value)), setting == OwnBrakes.ToolProfile || brakes.Contains(setting)
                    ? Is.Not.Empty : Is.Empty, setting);
            }
        });
    }

    // APP2 (REV11 A-3): «Avisar de versiones nuevas» switched off is a brake: on, BAXY asks GitHub at every start
    // (PRIVACIDAD.md, «Sin que lo pidas»), so the model turning it back on by itself waits for the person's «sí».
    [Test]
    public void TheNoticeOfNewVersionsSwitchedOffIsABrake()
    {
        string root = Directory.CreateTempSubdirectory("baxy-own-brakes-").FullName;
        try
        {
            var settings = new FieldSettings(root);
            Assert.That(settings.BrakeOn("update_notice"), Is.False, "on, the factory's");
            settings.ApplyGeneral(new JsonObject { ["updateNotice"] = false });
            Assert.Multiple(() =>
            {
                Assert.That(settings.BrakeOn("update_notice"), Is.True);
                Assert.That(OwnBrakes.Relaxed(OwnBrakes.Operation, Set("update_notice", "on")), Is.EqualTo("update_notice"));
                Assert.That(OwnBrakes.Relaxed(OwnBrakes.Operation, Set("update_notice", "off")), Is.Null);
                Assert.That(OwnBrakes.Names("update_notice", Set("update_notice", "on")),
                    Is.EqualTo(new[] { "Avisar de versiones nuevas", "Tell me about new versions" }));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // The value of each setting that would relax it, if it is a brake: «off» for not interrupting, a profile for the tools.
    private static string Relaxing(string setting) =>
        setting.StartsWith("no_interrupt_", StringComparison.Ordinal) ? "off" : setting == OwnBrakes.ToolProfile ? "diario" : "on";

    // TPV1: a tool profile is asked for by that profile's name, in each language, and Bypass waits for the «sí» even
    // when named (the identity's conscious setting, said aloud).
    [Test]
    public void AProfileIsNamedByItselfAndBypassAlwaysAsks()
    {
        Assert.Multiple(() =>
        {
            Assert.That(OwnBrakes.Names(OwnBrakes.ToolProfile, Set(OwnBrakes.ToolProfile, "completo")),
                Is.EqualTo(new[] { "Completo", "Complete" }));
            Assert.That(OwnBrakes.Relaxed(OwnBrakes.Operation, Set(OwnBrakes.ToolProfile, "esencial")), Is.EqualTo(OwnBrakes.ToolProfile));
            Assert.That(OwnBrakes.Relaxed(OwnBrakes.Operation, Set(OwnBrakes.ToolProfile, "on")), Is.Null);
            Assert.That(OwnBrakes.Relaxed(OwnBrakes.Operation, Set(OwnBrakes.Bypass, "off")), Is.Null);
            Assert.That(OwnBrakes.AlwaysAsks(OwnBrakes.Bypass), Is.True);
            Assert.That(OwnBrakes.AlwaysAsks("web_search"), Is.False);
            Assert.That(OwnBrakes.Shown(OwnBrakes.Operation, Set(OwnBrakes.ToolProfile, "diario"), english: false),
                Is.EqualTo("Perfil de herramientas: Diario"));
        });
    }

    // The card of the held change says why it asks, which setting it is and to what, in the view's language.
    [Test]
    public void TheCardSaysWhichSettingChangesAndToWhat()
    {
        JsonObject spanish = FieldStepProjection.Card("k1", "confirmation", OwnBrakes.Operation, Set("web_search", "on"),
            "low_reversible", DateTimeOffset.UtcNow.AddMinutes(1), null, english: false, cause: OwnBrakes.Cause);
        JsonObject english = FieldStepProjection.Card("k1", "confirmation", OwnBrakes.Operation, Set("web_search", "on"),
            "low_reversible", DateTimeOffset.UtcNow.AddMinutes(1), null, english: true, cause: OwnBrakes.Cause);

        Assert.Multiple(() =>
        {
            Assert.That((string?)spanish["target"], Is.EqualTo("Búsqueda web: activar"));
            Assert.That((string?)spanish["risk"], Is.EqualTo("cambia un ajuste que no pediste"));
            Assert.That((string?)english["target"], Is.EqualTo("Web search: turn on"));
            Assert.That((string?)english["risk"], Is.EqualTo("changes a setting you did not ask for"));
        });
    }

    // A setting of BAXY's own that changed in the turn is shown with the steps open and by its name (the row of the
    // live test hid it inside «Qué hice · 3 pasos»); one that was already so is a step like any other.
    [TestCase("readback", true)]
    [TestCase("unchanged", false)]
    public void ASettingThatChangedIsShownWithTheStepsOpen(string verification, bool pinned)
    {
        var step = new NativeTurnStep(OwnBrakes.Operation, Set("web_search", "on"), "completed", true, null, 5,
            new JsonObject
            {
                ["status"] = "completed",
                ["verification"] = verification,
                ["observed"] = new JsonObject { ["setting"] = "web_search", ["value"] = "on", ["changed"] = pinned },
            }.ToJsonString(), "c1", Sent: true);

        JsonObject? view = FieldStepProjection.Finished("c1", step, net: null, english: false);

        Assert.Multiple(() =>
        {
            Assert.That((string?)view?["label"], Is.EqualTo("Cambiar un ajuste de BAXY · Búsqueda web: activar"));
            Assert.That(view?["pin"] is JsonValue pin && pin.GetValue<bool>(), Is.EqualTo(pinned));
        });
    }

    // Revisión ciega del diff: a change that may have happened (the write failed past its start) is not left folded either.
    [Test]
    public void ASettingThatMayHaveChangedIsShownWithTheStepsOpen()
    {
        var step = new NativeTurnStep(OwnBrakes.Operation, Set("web_search", "on"), "failed", false,
            "baxy_setting_write_failed", 5,
            new JsonObject
            {
                ["status"] = "failed",
                ["error"] = "baxy_setting_write_failed",
                ["effectUncertain"] = true,
            }.ToJsonString(), "c1", Sent: true);

        JsonObject? view = FieldStepProjection.Finished("c1", step, net: null, english: false);

        Assert.Multiple(() =>
        {
            Assert.That((string?)view?["status"], Is.EqualTo("maybe"));
            Assert.That(view?["pin"] is JsonValue pin && pin.GetValue<bool>(), Is.True);
        });
    }

    // What the model reads when a switch of Privacidad refuses a call: whose switch it is, and (TPV1, dueño 10-11:
    // never «do it yourself in Settings») the call that switches it on with their «sí», never a way around it.
    [TestCase("web_disabled_by_owner", "web_search", "Búsqueda web")]
    [TestCase("weather_disabled_by_owner", "weather", "Clima")]
    [TestCase("screen_disabled_by_owner", "screen", "Mirar la pantalla")]
    public void ACallAPrivacySwitchRefusesSaysWhoseSwitchItIsAndHowBaxyTurnsItOn(string code, string setting, string name)
    {
        JsonNode? refused = JsonNode.Parse(NativeTurnLoop.Refused(code));

        Assert.Multiple(() =>
        {
            Assert.That((string?)refused?["status"], Is.EqualTo("rejected"));
            Assert.That((string?)refused?["error"], Is.EqualTo(code));
            Assert.That((string?)refused?["next"], Is.EqualTo(NativeTurnLoop.OwnerOffNext(setting, name)));
            Assert.That((string?)refused?["next"], Does.Contain($"the person switched «{name}» off")
                .And.Contain($"baxy_settings_set {{\"setting\":\"{setting}\",\"value\":\"on\"}} asks their yes itself")
                .And.Contain("instead of asking in words or sending them to Settings"));
        });
    }
}
