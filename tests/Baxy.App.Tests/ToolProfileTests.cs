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
            // ESE3: alarms and reminders are Esencial's (schedule.alarms, level 1). RUT1: + baxy.routines, level 0.
            // RUT2: audio.device.list, audio.device.set and display.monitor.set are Esencial's (level 1), + 3 in each.
            // RUT6: media.control is Esencial's (level 1): pausing and resuming by voice. media.status stays at
            // level 2: with it in Esencial a ringing reminder asked to repeat later went to baxy.routines (3 of 3).
            Assert.That(levels.Count(static l => l <= 1), Is.EqualTo(50), "Esencial");
            Assert.That(levels.Count(static l => l <= 2), Is.EqualTo(131), "Diario");
            Assert.That(levels.Count(static l => l <= 3), Is.EqualTo(181), "Avanzado");
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

    // MEM3 (VIVO15 fila 3: Completo with the memory switched off, memory_save shown whole as if it saved, «ahora sé que…»
    // 5 of 5): switched off, only the memory's held call (memory.save) is withheld and refused as off, in any profile, and
    // the mind that came up before the switch needs to be relaunched; switched on again, Completo withholds nothing.
    [Test]
    public void WithTheMemorySwitchedOffOnlyItsHeldCallIsWithheldInCompletoAndTheMindIsRelaunched()
    {
        var profile = new ToolProfile(_root);
        profile.Started(profile.Withheld(Names));
        profile.MemoryOff = true;
        IReadOnlySet<string> off = profile.Withheld(Names);
        string request = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), null, null, null, off).ToJsonString();
        bool relaunch = profile.NeedsSwitch;
        profile.MemoryOff = false;
        Assert.Multiple(() =>
        {
            // REM7: the switch itself stays callable. INT33J: without 610be96d3 (reverted by INT33G) the sensitive save is
            // not shown whole, so it is not held either.
            Assert.That(off, Is.EquivalentTo(new[] { "memory.save" }));
            Assert.That(profile.Refusal("memory.enable"), Is.Null);
            Assert.That(profile.Refusal("memory.recall"), Is.Null);
            Assert.That(relaunch, Is.True);
            Assert.That(request, Does.Contain("\"whole\""), "shown off with its arguments (HeldWhole)");
            Assert.That(profile.Withheld(Names), Is.Empty);
            Assert.That(profile.Refusal("memory.save"), Is.Null);
            Assert.That(profile.NeedsSwitch, Is.False);
        });
    }

    // REM7 (REV15 D-1): the mind said «apagada… no hay nada guardado» whatever the switch was. The request says the switch
    // the App read when a memory call goes held (memoryOff), and nothing otherwise; and in Esencial, where the switch does
    // not change what is withheld, turning it on or off still relaunches the mind, so its fact follows.
    [Test]
    public void TheMindIsToldTheMemorysSwitchBesideItsHeldCallAndRelaunchedWhenItFlips()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        profile.MemoryOff = true;
        IReadOnlySet<string> off = profile.Withheld(Names);
        profile.Started(off);
        JsonObject on = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), null, null, null, off, null, false);
        JsonObject switchedOff = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), null, null, null, off, null, true);
        JsonObject completo = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), null, null, null,
            new HashSet<string>(), null, true);
        bool stillStarted = profile.NeedsSwitch;
        profile.MemoryOff = false;
        Assert.Multiple(() =>
        {
            Assert.That((bool?)on["memoryOff"], Is.False);
            Assert.That((bool?)switchedOff["memoryOff"], Is.True);
            Assert.That(completo.ContainsKey("memoryOff"), Is.False, "nothing held: the request is the one sent before");
            Assert.That(stillStarted, Is.False);
            Assert.That(profile.NeedsSwitch, Is.True, "the switch flipped in Esencial: the mind's fact must follow");
        });
    }

    // REM7 (union of mem3): mem3 reads memory.status before the core hands the mind its catalog, but the start read the
    // profile's withheld calls when the mind's client was made, beside the core's hello, so a Completo with the memory off
    // could start with nothing held. What goes to the mind is read when its catalog is configured.
    [Test]
    public async Task TheWithheldCallsAndTheSwitchAreReadWhenTheCatalogIsConfigured()
    {
        var profile = new ToolProfile(_root);
        using var fake = new FakeMind();
        var catalog = new TaskCompletionSource<MindStartupCatalog>(TaskCreationOptions.RunContinuationsAsynchronously);
        await using var mind = new MindSidecarClient
        {
            Withheld = profile.Withheld(Names),
            WithheldNow = () => profile.Withheld(Names),
            MemoryOffNow = () => profile.MemoryOff,
        };
        Task<bool> started = mind.TryStartAsync(catalog.Task, TimeSpan.FromSeconds(30), CancellationToken.None);
        profile.MemoryOff = true;
        catalog.SetResult(new MindStartupCatalog(Catalog(), null, null));
        Assert.That(await started, Is.True);
        JsonObject configured = fake.Requests("catalog.configure").Single();
        Assert.Multiple(() =>
        {
            Assert.That(configured["withheld"]?.AsArray().Select(static entry => (string?)entry?["name"]),
                Is.EquivalentTo(new[] { "memory.save" }));
            Assert.That((bool?)configured["memoryOff"], Is.True);
            Assert.That(mind.ConfiguredWithheld, Is.EquivalentTo(new[] { "memory.save" }));
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
            Assert.That(withheld, Has.Count.EqualTo(195 - 50));
            Assert.That(offered, Has.Length.EqualTo(50));
            Assert.That(offered, Does.Contain("app.open").And.Contain("web.search").And.Contain("baxy.settings.set")
                .And.Contain("schedule.alarms"));
            Assert.That(offered, Does.Not.Contain("file.write").And.Not.Contain("package.install"));
            Assert.That(request["withheld"]!.AsArray().Select(static n => (string?)n!["name"]), Is.EquivalentTo(withheld));
            // VIVO1 F8: each one with its English title, the mind's stub for it.
            Assert.That(request["withheld"]!.AsArray().First(static n => (string?)n!["name"] == "package.install")!["title"]!
                .GetValue<string>(), Is.EqualTo(FieldStepProjection.EnglishTitle("package.install")));
            // VIVO1 F8, 2.ª vuelta (09-11): a memory tool has no stub («ficha»: false), named without its title.
            Assert.That(request["withheld"]!.AsArray().First(static n => (string?)n!["name"] == "memory.recall")!["title"], Is.Null);
            // ESE6: but memory.save («ficha»: "entera"), with its title and whole: the mind shows it off with its
            // arguments, and its call is held with them (NativeTurnLoop.OffHeld).
            JsonNode save = request["withheld"]!.AsArray().First(static n => (string?)n!["name"] == "memory.save")!;
            Assert.That((string?)save["title"], Is.EqualTo("Save to memory"));
            Assert.That(save["whole"]?["argumentsSchema"]?["properties"]?["selector"], Is.Not.Null);
            Assert.That((string?)save["whole"]?["name"], Is.EqualTo("memory.save"));
            // ESE7: and the memory's switch, so «activa la memoria» with nothing to save has its own call.
            JsonNode enable = request["withheld"]!.AsArray().First(static n => (string?)n!["name"] == "memory.enable")!;
            Assert.That((string?)enable["title"], Is.EqualTo("Turn memory on"));
            Assert.That((string?)enable["whole"]?["name"], Is.EqualTo("memory.enable"));
            Assert.That(request["withheld"]!.AsArray().Where(static n => n!["whole"] is not null)
                .Select(static n => (string?)n!["name"]), Is.EquivalentTo(new[] { "memory.enable", "memory.save" }));
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
        // COR1: «Búsqueda web» says whose switch it is (OwnBrakesTests); TPV1: the weather's too, and how BAXY turns it on.
        JsonNode other = JsonNode.Parse(NativeTurnLoop.Refused("weather_disabled_by_owner"))!;
        Assert.Multiple(() =>
        {
            Assert.That(((string?)off["status"], (string?)off["error"]), Is.EqualTo(("rejected", ToolProfile.OffCode)));
            Assert.That((string?)off["next"], Does.Contain("nothing ran and nothing was read"));
            Assert.That((string?)other["next"], Is.EqualTo(NativeTurnLoop.OwnerOffNext("weather", "Clima")));
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
                .And.Contain("the call in turnOnBySpeaking asks their yes itself"));
            // TPV1 (dueño, 10-11: never «do it yourself in Settings»): the smallest profile that has it, switched by voice.
            Assert.That((string?)off["turnOnBySpeaking"], Is.EqualTo(
                """baxy_settings_set {"setting":"tool_profile","value":"diario"} switches to the profile Diario, which has it; BAXY asks the person's yes itself"""));
            Assert.That((string?)diario["profile"], Is.EqualTo("Diario"));
            Assert.That((string?)diario["turnOn"], Does.StartWith("Settings → Tools («Ajustes → Herramientas»): the profile ").And.Not.Contain("Diario"));
            Assert.That(web["profile"] ?? web["tool"] ?? web["turnOn"], Is.Null);
            Assert.That((string?)web["next"], Does.Contain("«Búsqueda web»").And.Not.Contain("profile"));
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

    // APP2 (REV11 A-4): a file that could not be read at that moment (another program holding it, a broken write) was
    // Completo, and every tool the person had off ran. The last profile read holds, and the file is read again at the
    // next look: what the person chose comes back as soon as it can be read.
    [Test]
    public void AnUnreadableFileKeepsTheLastProfileReadAndOpensNothing()
    {
        string path = Path.Combine(_root, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        string[] off = [.. profile.Withheld(Names)];
        Assert.That(off, Is.Not.Empty);

        File.WriteAllText(path, """{"profile":"esenc""");
        Assert.Multiple(() =>
        {
            Assert.That(profile.Profile, Is.EqualTo("esencial"), "broken");
            Assert.That(profile.Withheld(Names), Is.EquivalentTo(off), "broken");
            Assert.That(off.Select(profile.Refusal), Has.All.EqualTo(ToolProfile.OffCode), "broken");
        });

        File.WriteAllText(path, """{"profile":"esencial"}""");
        using (new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            Assert.That(profile.Withheld(Names), Is.EquivalentTo(off), "held by another program");
        }

        File.WriteAllText(path, """{"profile":"diario"}""");
        Assert.That(profile.Profile, Is.EqualTo("diario"), "read again");
    }

    // APP2 (REV11 A-4): with no profile read yet (BAXY starting while the file cannot be read, or one that names no
    // profile), the most closed: only BAXY's own tools, until the file can be read.
    [TestCase("""{"profile":"esenc""")]
    [TestCase("""{"profile":"turbo"}""")]
    [TestCase("""["esencial"]""")]
    public void WithNothingReadYetAFileThatSaysNoProfileKeepsOnlyBaxysOwn(string written)
    {
        string path = Path.Combine(_root, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        File.WriteAllText(path, written);
        var profile = new ToolProfile(_root);
        string[] own = [.. Names.Where(static name => FieldStepProjection.ProfileLevel(name) == 0)];

        Assert.That(profile.Withheld(Names), Is.EquivalentTo(Names.Except(own)));

        File.WriteAllText(path, """{"profile":"avanzado"}""");
        Assert.That(profile.Profile, Is.EqualTo("avanzado"), "read again");
    }

    // REM1 (APP2's A-4 medio): with nothing read yet, the most closed profile kept for the moment is not a choice. A model
    // change with a profile, refused, put back what Json() said before it, and wrote that profile as the person's.
    [Test]
    public void TheMostClosedProfileKeptForTheMomentIsNotWrittenBackAsAChoice()
    {
        string path = Path.Combine(_root, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        File.WriteAllText(path, """{"profile":"esenc""");
        var profile = new ToolProfile(_root);
        System.Text.Json.Nodes.JsonObject before = profile.Json();

        Assert.That(profile.Apply(new System.Text.Json.Nodes.JsonObject { ["profile"] = "diario" }), Is.Null);
        Assert.That(profile.Apply(before), Is.Null);
        Assert.That(File.ReadAllText(path), Is.EqualTo("""{"profile":"diario"}"""), "the provisional one is not written");

        // The control: a profile read from the file is put back.
        System.Text.Json.Nodes.JsonObject read = profile.Json();
        Assert.That(profile.Apply(new System.Text.Json.Nodes.JsonObject { ["profile"] = "esencial" }), Is.Null);
        Assert.That(profile.Apply(read), Is.Null);
        Assert.That(File.ReadAllText(path), Is.EqualTo("""{"profile":"diario"}"""));
        Assert.That(read.ContainsKey("provisional"), Is.False);

        // REM1 (revisión ciega): a profile lent to a model over the provisional one is not said given back to it.
        var external = new ExternalModel(_root);
        external.Lend("lumen:7b", "esencial", before);
        Assert.That(external.Settle(external.Lent!, "esencial"), Is.Null);
        Assert.That(external.Json()["profileBack"], Is.Null);
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
            Assert.That(json["on"]!.AsArray(), Has.Count.EqualTo(131));
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
            Assert.That(ToolProfile.NeededContext("completo", null, null), Is.EqualTo(51450 + LocalContext.TurnRoomTokens));
            Assert.That(ToolProfile.NeededContext("esencial", null, null), Is.EqualTo(26342 + LocalContext.TurnRoomTokens));
            // One the running mind read for its profile scales them: the apps installed change them.
            Assert.That(ToolProfile.NeededContext("esencial", 99150, "completo"), Is.EqualTo(50764 + LocalContext.TurnRoomTokens));
            Assert.That(ToolProfile.NeededContext("personalizado", 20000, "personalizado"), Is.EqualTo(20000 + LocalContext.TurnRoomTokens));
            Assert.That(ToolProfile.NeededContext("personalizado", null, null), Is.EqualTo(51450 + LocalContext.TurnRoomTokens));
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
            Assert.That(ToolProfile.NeededContext("completo", 26342, "esencial"), Is.EqualTo(51450 + LocalContext.TurnRoomTokens));
        });
    }
    // TPV5 (TPV4, revisión ciega): Esencial with the memory turned on is Personalizado; its need was weighed as
    // Completo's (49,575 + a turn = 53,159), so a context chosen for Esencial (32,768) went back to «Automático» (77,824 on
    // CUDA) at the relaunch. Its tools take about Esencial's prompt and the memory's: it still fits 32,768, and the chosen
    // context stays (LocalContext.KeepFitting).
    [Test]
    public void EsencialWithTheMemoryNeedsItsOwnToolsNotCompletos()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        int esencial = profile.Kept;
        // Esencial with the memory's tools ticked as well (Settings → Tools, Personalizado).
        JsonArray on = [.. profile.Json()["on"]!.AsArray().Select(static n => (JsonNode?)n!.GetValue<string>()),
            .. ProductCatalog.ToolDescriptors.Select(static d => d.Name)
                .Where(MemoryOperationProtector.IsMemoryOperation).Select(static n => (JsonNode?)n)];
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Personalizado, ["on"] = on }), Is.Null);
        int ticked = profile.Kept;
        // The «sí» that turns one memory tool on (KeepOn) leaves the same Personalizado.
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        Assert.That(profile.KeepOn("memory.save"), Is.Null);
        Assert.That(profile.Kept, Is.EqualTo(ticked));
        int need = ToolProfile.NeededContext(profile.Profile, null, null, profile.Kept);
        var context = new LocalContext(_root);
        Assert.That(context.Apply(new JsonObject { ["context"] = 32768 }, prefixTokens: 26342), Is.Null);

        Assert.Multiple(() =>
        {
            Assert.That(profile.Profile, Is.EqualTo(ToolProfile.Personalizado));
            Assert.That(profile.Kept, Is.GreaterThan(esencial));
            Assert.That(need, Is.GreaterThan(ToolProfile.NeededContext("esencial", null, null)));
            Assert.That(need, Is.LessThanOrEqualTo(32768));
            Assert.That(need, Is.LessThan(ToolProfile.NeededContext("diario", null, null)));
            Assert.That(context.KeepFitting(need), Is.False);
            Assert.That(context.Chosen(), Is.EqualTo(32768));
            // A larger change (Completo said aloud) grows it to the smallest preset that holds it, not to «Automático»
            // (INT33A: with the routines' tools Completo and a turn are 51,417 + 3,584 = 55,001 tokens, past 53,248).
            Assert.That(context.KeepFitting(ToolProfile.NeededContext(ToolProfile.Completo, null, null)), Is.True);
            Assert.That(context.Chosen(), Is.EqualTo(61440));
        });
    }

    // TPV5: the line between the presets passes through each one's measured prefix.
    [Test]
    public void APersonalizadoWithAPresetsToolsTakesThatPresetsPrefix()
    {
        var profile = new ToolProfile(_root);
        foreach ((string preset, int prefix) in new[] { ("esencial", 26342), ("diario", 40035), ("avanzado", 49708), ("completo", 51450) })
        {
            Assert.That(profile.Apply(new JsonObject { ["profile"] = preset }), Is.Null);
            Assert.That(ToolProfile.PersonalPrefix(profile.Kept), Is.EqualTo(prefix), preset);
        }
    }
}
