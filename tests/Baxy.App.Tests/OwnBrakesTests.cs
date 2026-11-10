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
        string[] brakes = [.. settings.Where(static setting => OwnBrakes.Names(setting).Length > 0)];

        Assert.Multiple(() =>
        {
            Assert.That(brakes, Is.EquivalentTo(new[]
            {
                "no_interrupt_calls", "no_interrupt_games", "no_interrupt_videos", "proposals", "voice", "web_search",
            }));
            Assert.That(settings.Except(brakes), Is.EquivalentTo(new[] { "accessible_mode", "confirmation_bypass", "overlay" }));
            foreach (string setting in settings)
            {
                Assert.That(OwnBrakes.Shown(OwnBrakes.Operation, Set(setting, "on"), english: false), Is.Not.Null, setting);
                Assert.That(OwnBrakes.Shown(OwnBrakes.Operation, Set(setting, "on"), english: true), Is.Not.Null, setting);
            }
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

    // What the model reads when «Búsqueda web» refuses a call: whose switch it is and what to tell them, never a way
    // around it. The other owner's switches say what they said.
    [Test]
    public void ACallTheWebSwitchRefusesSaysWhoseSwitchItIs()
    {
        JsonNode? web = JsonNode.Parse(NativeTurnLoop.Refused(FieldSettings.WebOff));
        JsonNode? weather = JsonNode.Parse(NativeTurnLoop.Refused("weather_disabled_by_owner"));

        Assert.Multiple(() =>
        {
            Assert.That((string?)web?["status"], Is.EqualTo("rejected"));
            Assert.That((string?)web?["error"], Is.EqualTo("web_disabled_by_owner"));
            Assert.That((string?)web?["next"], Is.EqualTo(NativeTurnLoop.WebOffNext));
            Assert.That(NativeTurnLoop.WebOffNext, Does.Contain("the person switched web search off")
                .And.Contain("theirs to switch back on").And.Contain("tell them it is off"));
            Assert.That(weather?["next"], Is.Null);
        });
    }
}
