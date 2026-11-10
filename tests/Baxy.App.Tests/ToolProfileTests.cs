using System.IO;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Perfiles de herramientas (owner, 2026-11-08): the person chooses how many of BAXY's tools the model sees. A tool off
/// is neither offered to the mind nor run when the model names it anyway; Completo, the factory's, is today's request.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class ToolProfileTests
{
    private string _root = "";

    [SetUp]
    public void SetUp() => _root = Directory.CreateTempSubdirectory("baxy-tool-profile-").FullName;

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    private static List<OperationDescriptor> Catalog() =>
        [.. ProductCatalog.ToolDescriptors.Select(static descriptor =>
            ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor)))];

    private static string[] Names => [.. ProductCatalog.ToolDescriptors.Select(static d => d.Name)];

    // actualizar-ordenes-app: + 1 in every profile, baxy.update (BAXY itself, level 0).
    [Test]
    public void EveryOperationSaysTheFirstProfileThatHasIt()
    {
        FieldStepProjection.Validate();
        int[] levels = [.. Names.Select(FieldStepProjection.ProfileLevel)];
        Assert.Multiple(() =>
        {
            Assert.That(levels, Has.All.InRange(0, ToolProfile.Highest));
            // ESE3: alarms and reminders are Esencial's (schedule.alarms, level 1).
            Assert.That(levels.Count(static l => l <= 1), Is.EqualTo(45), "Esencial");
            Assert.That(levels.Count(static l => l <= 2), Is.EqualTo(127), "Diario");
            Assert.That(levels.Count(static l => l <= 3), Is.EqualTo(177), "Avanzado");
        });
    }

    [Test]
    public void TheFactorysProfileIsCompletoAndWithholdsNothing()
    {
        var profile = new ToolProfile(_root);
        Assert.Multiple(() =>
        {
            Assert.That(profile.Profile, Is.EqualTo(ToolProfile.Completo));
            Assert.That(profile.Withheld(Names), Is.Empty);
            Assert.That(Names.All(name => profile.Refusal(name) is null));
        });
    }

    [Test]
    public void WithCompletoTheMindsRequestIsTheOneSentBefore()
    {
        string before = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), applicationCatalog: null).ToJsonString();
        string now = MindSidecarClient.CreateCatalogConfigureRequest(
            Catalog(), null, null, null, new ToolProfile(_root).Withheld(Names)).ToJsonString();
        Assert.That(now, Is.EqualTo(before));
    }

    [Test]
    public void WithAProfileTheModelIsToldOnlyTheThemesItKeepsHalfOf()
    {
        // VIVO1 F8, 2.ª vuelta (09-11): with Esencial the areas line said «Memoria» (BAXY's conversations, always on) and
        // «Alarmas, notas y tareas» (the clock alone), and the 4B promised to remember and to set alarms it could not.
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        JsonObject request = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), null, null, null, profile.Withheld(Names));
        string?[] groups = [.. request["capabilities"]!.AsArray().Select(static c => (string?)c!["group"]).Distinct()];
        Assert.Multiple(() =>
        {
            Assert.That(groups, Does.Not.Contain(FieldStepProjection.Group("memory.save")));
            Assert.That(groups, Does.Not.Contain(FieldStepProjection.Group("note.create")));
            Assert.That(groups, Does.Contain(FieldStepProjection.Group("app.open")).And.Contain(FieldStepProjection.Group("audio.volume")));
            Assert.That(request["capabilities"]!.AsArray().Count(static c => c!["name"]!.GetValue<string>() == "conversation.new"), Is.EqualTo(1),
                "the tool stays; only its theme is not told");
        });
    }

    [Test]
    public void AProfileWithholdsWhatItLacksFromTheMindAndRefusesItWhenNamed()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        IReadOnlySet<string> withheld = new ToolProfile(_root).Withheld(Names);
        JsonObject request = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), null, null, null, withheld);
        string[] offered = [.. request["capabilities"]!.AsArray().Select(static c => (string)c!["name"]!)];
        Assert.Multiple(() =>
        {
            Assert.That(withheld, Has.Count.EqualTo(191 - 45));
            Assert.That(offered, Has.Length.EqualTo(45));
            Assert.That(offered, Does.Contain("app.open").And.Contain("web.search").And.Contain("baxy.settings.set")
                .And.Contain("schedule.alarms"));
            Assert.That(offered, Does.Not.Contain("file.write").And.Not.Contain("package.install"));
            Assert.That(request["withheld"]!.AsArray().Select(static n => (string?)n!["name"]), Is.EquivalentTo(withheld));
            // VIVO1 F8: each one with its English title, the mind's stub for it.
            Assert.That(request["withheld"]!.AsArray().First(static n => (string?)n!["name"] == "package.install")!["title"]!
                .GetValue<string>(), Is.EqualTo(FieldStepProjection.EnglishTitle("package.install")));
            // VIVO1 F8, 2.ª vuelta (09-11): a memory tool has no stub («ficha»: false), named without its title.
            Assert.That(request["withheld"]!.AsArray().First(static n => (string?)n!["name"] == "memory.save")!["title"], Is.Null);
            Assert.That(profile.Refusal("package.install"), Is.EqualTo("tool_off_in_profile"));
            Assert.That(profile.Refusal("window.focus"), Is.Null);
            Assert.That(profile.Refusal("not.a.tool"), Is.Null, "an unknown name is the App's unknown_operation");
        });
    }

    [Test]
    public void ARefusalAsOffTellsTheModelNothingRanAndNothingWasRead()
    {
        // Banco 1/16 y 2/16 (08-11, juez ciego): with only the code the model read a refused look as «no window» (5 of 41
        // answers in Diario) and a refused recall as «no record» (2 of 63 in Esencial).
        JsonNode off = JsonNode.Parse(NativeTurnLoop.Refused(ToolProfile.OffCode))!;
        // COR1: «Búsqueda web» says whose switch it is (OwnBrakesTests); the weather's is still its bare code.
        JsonNode other = JsonNode.Parse(NativeTurnLoop.Refused("weather_disabled_by_owner"))!;
        Assert.Multiple(() =>
        {
            Assert.That(((string?)off["status"], (string?)off["error"]), Is.EqualTo(("rejected", ToolProfile.OffCode)));
            Assert.That((string?)off["next"], Does.Contain("nothing ran and nothing was read"));
            Assert.That(other.ToJsonString(), Is.EqualTo("""{"status":"rejected","error":"weather_disabled_by_owner"}"""));
        });
    }

    // ESE1 (VIVO5 fila 7: «Read a web page» off in Esencial was told as «Búsqueda web» switched off, which was on): the two
    // causes read differently, and the profile's names the tool, the profile and where it turns on.
    [Test]
    public void ARefusalAsOffInTheProfileNamesTheToolTheProfileAndWhereItTurnsOnNotTheWebSwitch()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        JsonNode off = JsonNode.Parse(NativeTurnLoop.Refused(ToolProfile.OffCode, null, profile.OffFacts("web.fetch")))!;
        JsonNode web = JsonNode.Parse(NativeTurnLoop.Refused(FieldSettings.WebOff))!;
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        JsonNode diario = JsonNode.Parse(NativeTurnLoop.Refused(ToolProfile.OffCode, null, profile.OffFacts("package.install")))!;
        Assert.Multiple(() =>
        {
            Assert.That((string?)off["tool"], Is.EqualTo(FieldStepProjection.EnglishTitle("web.fetch")));
            Assert.That((string?)off["profile"], Is.EqualTo("Esencial"));
            Assert.That((string?)off["turnOn"], Is.EqualTo(
                "Settings → Tools («Ajustes → Herramientas»): the profile Diario, Avanzado or Completo, or Personalizado with «Leer una página web» ticked"));
            Assert.That((string?)off["next"], Does.Contain("off in the person's tool profile, not by any other setting")
                .And.Contain("how they turn it on"));
            Assert.That((string?)diario["profile"], Is.EqualTo("Diario"));
            Assert.That((string?)diario["turnOn"], Does.StartWith("Settings → Tools («Ajustes → Herramientas»): the profile ").And.Not.Contain("Diario"));
            Assert.That(web["profile"] ?? web["tool"] ?? web["turnOn"], Is.Null);
            Assert.That((string?)web["next"], Does.Contain("web search").And.Not.Contain("profile"));
            Assert.That((string?)off["next"], Does.Not.Contain("web search"));
        });
    }

    // ESE3 (VIVO7 fila 4, P2: «activa la opción "Alarmas o recordatorios"», an option Settings → Tools never shows): where
    // a tool turns on is told with the names the view shows, the profiles and the tool's box in Personalizado, in Spanish
    // and in English.
    [Test]
    public void WhereAToolTurnsOnIsToldWithTheNamesTheViewShowsInItsLanguage()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        JsonObject spanish = profile.OffFacts("note.create");
        UiLanguage.Use(UiLanguage.English);
        JsonObject english = profile.OffFacts("note.create");
        UiLanguage.Use(UiLanguage.Spanish);
        Assert.Multiple(() =>
        {
            Assert.That((string?)spanish["profile"], Is.EqualTo("Esencial"));
            Assert.That((string?)spanish["turnOn"], Is.EqualTo(
                "Settings → Tools («Ajustes → Herramientas»): the profile Diario, Avanzado or Completo, or Personalizado with «Crear nota» ticked"));
            Assert.That((string?)english["profile"], Is.EqualTo("Essential"));
            Assert.That((string?)english["turnOn"], Is.EqualTo(
                "Settings → Tools: the profile Everyday, Advanced or Complete, or Custom with «Create a note» ticked"));
            Assert.That((string?)english["tool"], Is.EqualTo((string?)spanish["tool"]), "the tool as the model knows it");
        });
    }

    [Test]
    public void WithAlarmsOffInTheProfileWhatAlreadyRingsIsStillStoppedOrSnoozed()
    {
        // ALR5 (M2, uso real 09-11): with Esencial an alarm set before rang and no words stopped it; only the card's
        // buttons did. Setting, listing and cancelling stay off, and so does a stop with nothing ringing. ESE3: Esencial
        // keeps alarms now; a Personalizado without them is where they are off.
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "personalizado", ["on"] = new JsonArray("app.open") }), Is.Null);
        JsonObject stop = new() { ["action"] = "stop", ["id"] = "89abcdef" };
        JsonObject snooze = new() { ["action"] = "snooze", ["inMinutes"] = 5 };
        JsonObject create = new() { ["action"] = "create", ["inMinutes"] = 5, ["title"] = "x" };
        Assert.Multiple(() =>
        {
            Assert.That(profile.Refusal("schedule.alarms"), Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Refusal("schedule.alarms", stop, ringing: true), Is.Null);
            Assert.That(profile.Refusal("schedule.alarms", snooze, ringing: true), Is.Null);
            Assert.That(profile.Refusal("schedule.alarms", stop, ringing: false), Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Refusal("schedule.alarms", create, ringing: true), Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Refusal("schedule.alarms", new JsonObject { ["action"] = "cancel" }, ringing: true),
                Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Refusal("schedule.alarms", new JsonObject { ["action"] = 3 }, ringing: true),
                Is.EqualTo(ToolProfile.OffCode));
            // Another tool off stays off whatever rings, also with those arguments.
            Assert.That(profile.Refusal("package.install", stop, ringing: true), Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Refusal("app.open", stop, ringing: true), Is.Null);
        });
    }

    [Test]
    public void PersonalizadoKeepsOnlyTheToolsTurnedOnAndBaxysOwnAlways()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject
        {
            ["profile"] = "personalizado",
            ["on"] = new JsonArray("app.open", "file.read"),
        }), Is.Null);
        IReadOnlySet<string> withheld = new ToolProfile(_root).Withheld(Names);
        string[] always = [.. Names.Where(static n => FieldStepProjection.ProfileLevel(n) == 0)];
        Assert.Multiple(() =>
        {
            Assert.That(Names.Except(withheld), Is.EquivalentTo(always.Concat(["app.open", "file.read"])));
            Assert.That(always, Does.Contain("baxy.settings.set").And.Contain("conversation.new"));
        });
    }

    [Test]
    public void AnUnknownProfileOrToolIsRefusedAndNothingIsKept()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        Assert.Multiple(() =>
        {
            Assert.That(profile.Apply(new JsonObject { ["profile"] = "turbo" }), Is.EqualTo("tool_profile_invalid"));
            Assert.That(profile.Apply(new JsonObject { ["profile"] = "personalizado", ["on"] = new JsonArray("no.such") }),
                Is.EqualTo("tool_profile_invalid"));
            Assert.That(new ToolProfile(_root).Profile, Is.EqualTo("diario"));
        });
    }

    [Test]
    public void AChangeAfterTheMindStartedAsksForASwitchOnce()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.NeedsSwitch, Is.False, "before any mind came up");
        profile.Started(profile.Withheld(Names));
        Assert.That(profile.NeedsSwitch, Is.False);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "avanzado" }), Is.Null);
        Assert.That(profile.NeedsSwitch, Is.True);
        profile.Started(profile.Withheld(Names));
        Assert.That(profile.NeedsSwitch, Is.False);
    }

    [Test]
    public void ItsStateSaysTheProfileAndWhatIsOn()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        JsonObject json = profile.Json();
        Assert.Multiple(() =>
        {
            Assert.That((string?)json["profile"], Is.EqualTo("diario"));
            Assert.That(json["on"]!.AsArray(), Has.Count.EqualTo(127));
        });
    }

    // VIVO1 F4 (2026-11-09): mistral:latest admits 32.768 tokens; with Completo BAXY's prompt does not fit and every turn was
    // refused. Each profile needs its prompt and a turn; the largest that fits a model's own context is the one offered.
    [Test]
    public void EachProfileNeedsItsPromptAndATurnAndTheLargestThatFitsIsOffered()
    {
        Assert.Multiple(() =>
        {
            // The measured prefixes (PERFILES_HERRAMIENTAS.md) and LocalContext's turn room.
            Assert.That(ToolProfile.NeededContext("completo", null, null), Is.EqualTo(49575 + LocalContext.TurnRoomTokens));
            Assert.That(ToolProfile.NeededContext("esencial", null, null), Is.EqualTo(23816 + LocalContext.TurnRoomTokens));
            // One the running mind read for its profile scales them: the apps installed change them.
            Assert.That(ToolProfile.NeededContext("esencial", 99150, "completo"), Is.EqualTo(47632 + LocalContext.TurnRoomTokens));
            Assert.That(ToolProfile.NeededContext("personalizado", 20000, "personalizado"), Is.EqualTo(20000 + LocalContext.TurnRoomTokens));
            Assert.That(ToolProfile.NeededContext("personalizado", null, null), Is.EqualTo(49575 + LocalContext.TurnRoomTokens));
            Assert.That(ToolProfile.LargestFitting(32768, null, null), Is.EqualTo("esencial"));
            Assert.That(ToolProfile.LargestFitting(16384, null, null), Is.Null);
        });
    }

    // INT20 (2026-11-09): the tools a profile keeps off go to the model as stubs (VIVO1 F8), and its prompt grew with them:
    // Diario's by 3.633 tokens, Esencial's by 7.694 (Qwen3.5's tokenizer and its GGUF's template). A model of Ollama that
    // admits 40.960 (qwen3's) has room for Diario's prompt without its stubs (34.055 + a turn) but not with them.
    [Test]
    public void APromptThatShowsTheToolsKeptOffAsStubsIsTheOneThatMustFit()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ToolProfile.NeededContext("diario", null, null), Is.GreaterThan(40960));
            Assert.That(ToolProfile.LargestFitting(40960, null, null), Is.EqualTo("esencial"));
            Assert.That(ToolProfile.LargestFitting(45056, null, null), Is.EqualTo("diario"));
            // A mind that read Esencial's prompt with its stubs scales the others by the apps alone, not by the stubs.
            Assert.That(ToolProfile.NeededContext("completo", 23816, "esencial"), Is.EqualTo(49575 + LocalContext.TurnRoomTokens));
        });
    }
}
