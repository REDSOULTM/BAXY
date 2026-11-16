using System.IO;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// ARR3 (VIVO23, 15-11-2026: with a card of 4 GB and the Completo profile chosen, «BAXY no logra arrancar … falta memoria
/// libre en la tarjeta gráfica», and choosing Esencial in Settings did not try again: it had to be closed and opened). The
/// identity: «cabe en 4 GB». BAXY starts whenever a profile fits: in the largest ready-made one the card's free memory holds
/// under the person's own, which stays theirs (the file is never written: the cause may pass, another program on the card),
/// and the start says so; choosing a profile in Settings or by voice tries the start again, without closing BAXY.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class CardProfileTheirsTests
{
    private string _root = "";

    [SetUp]
    public void SetUp() => _root = Directory.CreateTempSubdirectory("baxy-cardtheirs-").FullName;

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    private static IEnumerable<string> Catalog => ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name);

    private string ProfileFile => Path.Combine(_root, Baxy.Kernel.Policy.ToolProfileStore.FileName);

    private static IReadOnlySet<string> WithheldIn(string preset)
    {
        string other = Directory.CreateTempSubdirectory("baxy-cardtheirs-").FullName;
        try
        {
            var profile = new ToolProfile(other);
            Assert.That(profile.Apply(new JsonObject { ["profile"] = preset }), Is.Null);
            return profile.Withheld(Catalog);
        }
        finally
        {
            Directory.Delete(other, recursive: true);
        }
    }

    private static string? Needs =>Environment.GetEnvironmentVariable(LocalContext.NeedsVariable);

    [TestCase(false)]
    [TestCase(true)]
    public void ThePersonsProfileTheCardCannotHoldIsStoodInForThisStartAndKept(bool shortCard)
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        string chosen = File.ReadAllText(ProfileFile);

        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard);

        var standIn = new ToolProfile.CardFitted("esencial", 3400, 3880, ThisStart: true, Factory: ToolProfile.Completo, Theirs: true);
        Assert.Multiple(() =>
        {
            Assert.That(profile.Profile, Is.EqualTo("esencial"), "this start runs what fits");
            Assert.That(profile.Withheld(Catalog), Is.EquivalentTo(WithheldIn("esencial")), "with that profile's tools");
            Assert.That(profile.Chosen, Is.True, "the person's choice stays theirs");
            Assert.That(File.ReadAllText(ProfileFile), Is.EqualTo(chosen), "never written");
            Assert.That(profile.Fitted, Is.EqualTo(standIn));
            Assert.That(profile.SaidNow, Is.EqualTo(standIn), "the start says it");
            Assert.That(profile.Json()["byCard"]!.ToJsonString(),
                Is.EqualTo("""{"factory":"completo","freeMb":3400,"needMb":3880,"thisStart":true,"chosen":true}"""));
            Assert.That((bool?)profile.CardProfileFact()?["chosen"], Is.True, "and the model can tell it");
            Assert.That((string?)profile.CardProfileFact()?["factory"], Is.AnyOf("Completo", "Complete"));
        });

        // The next start tries the person's own profile again, and so does BAXY opened again.
        profile.StartAgain();
        Assert.That(profile.Profile, Is.EqualTo(ToolProfile.Completo));
        Assert.That(profile.Fitted, Is.Null);
        Assert.That(new ToolProfile(_root).Profile, Is.EqualTo(ToolProfile.Completo));
    }

    [Test]
    public void AskingAgainForTheProfileThatDidNotFitTriesItAgain()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        profile.Started(profile.Withheld(Catalog));
        Assert.That(profile.NeedsSwitch, Is.False);

        // By voice the file already says Completo (baxy.settings.set writes nothing): the App starts again.
        profile.StartAgain();
        Assert.That(profile.NeedsSwitch, Is.True, "the mind runs Esencial's tools, the person asked for Completo's");

        // In Settings: the person's choice written again.
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        Assert.That(profile.Profile, Is.EqualTo(ToolProfile.Completo));
        Assert.That(profile.NeedsSwitch, Is.True);

        // Esencial, what already runs: theirs now, and nothing to relaunch.
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        Assert.That(profile.NeedsSwitch, Is.False);
        Assert.That(profile.Fitted, Is.Null);
    }

    [Test]
    public void ProfileAskedByVoiceWhileItIsStoodInForIsToldWhatRuns()
    {
        // The live ARR3 run: «Cambia al perfil Completo.» → «Ya tenías el perfil Completo…», the engine's receipt saying
        // «changed»: false (their file named it) while Esencial ran.
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        var asked = new JsonObject { ["setting"] = "tool_profile", ["value"] = ToolProfile.Completo };
        Assert.That(profile.StandInNote(asked), Is.Null, "nothing stands in: the receipt is the truth");

        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);

        JsonObject? note = profile.StandInNote(asked);
        // MEN3: the whole fact, typed: which was asked, which is active, nothing applied, and why in figures.
        Assert.That(note, Is.Not.Null);
        Assert.That((bool?)note!["applied"], Is.False);
        Assert.That((string?)note["asked"], Is.EqualTo("Completo").Or.EqualTo("Complete"));
        Assert.That((string?)note["active"], Is.EqualTo("Esencial").Or.EqualTo("Essential"));
        Assert.That((double?)note["videoMemoryFreeGb"], Is.EqualTo(3.3));
        Assert.That((double?)note["askedNeedsGb"], Is.EqualTo(3.8));
        Assert.That((string?)note["next"], Does.StartWith("Not applied: the active profile is Es").And.Contain("tries it again"));
        Assert.That(note.ToJsonString(), Does.Not.Contain("alreadyChosen").And.Not.Contain("largest"));
        Assert.That(profile.StandInNote(new JsonObject { ["setting"] = "tool_profile", ["value"] = "diario" }), Is.Null,
            "another profile asked: the receipt says it changed");
        Assert.That(profile.StandInNote(new JsonObject { ["setting"] = "voice", ["value"] = "off" }), Is.Null);
    }

    [Test]
    public void TheEnginesChangedFalseIsToldAsAlreadyChosenNotAsRunning()
    {
        // The live ARR3 runs: «changed»: false (their file named it) was read as «Ya estás en el perfil Completo».
        string told = NativeTurnLoop.StoodIn("""{"setting":"tool_profile","value":"completo","changed":false}""",
            new JsonObject { ["applied"] = false, ["active"] = "Esencial" });
        JsonObject facts = JsonNode.Parse(told)!.AsObject();
        Assert.That(facts.ContainsKey("changed"), Is.False);
        Assert.That((string?)facts["status"], Is.EqualTo("failed"), "what was asked does not run now");
        Assert.That((string?)facts["error"], Is.EqualTo(ToolProfile.StoodInCode));
        Assert.That((bool?)facts["applied"], Is.False);
        Assert.That((string?)facts["active"], Is.EqualTo("Esencial"));
    }

    [Test]
    public void AToolOffOnlyBecauseOfTheCardNeverWritesAnotherProfileOverTheirs()
    {
        // Blind review of ARR3 (1): a «sí» to a tool off at this start wrote Personalizado over the person's Completo.
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        string chosen = File.ReadAllText(ProfileFile);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        string off = Catalog.First(name => profile.Refusal(name) == ToolProfile.OffCode);

        JsonObject facts = profile.OffFacts(off);
        Assert.That((string?)facts["offThisStart"], Does.Contain("chose the profile Complet"));
        Assert.That((string?)facts["turnOnBySpeaking"], Does.Contain("completo").And.Contain("tries"));
        Assert.That(profile.KeepOn(off), Is.EqualTo(ToolProfile.StoodInCode));
        Assert.That(File.ReadAllText(ProfileFile), Is.EqualTo(chosen), "theirs, never written");
        Assert.That(profile.Profile, Is.EqualTo("esencial"));
    }

    [Test]
    public void AskingByVoiceKeepsTheToolsThatRunUntilTheRelaunch()
    {
        // Blind review of ARR3 (5): the retry asked by voice left the turn's refusals reading Completo's tools.
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        IReadOnlySet<string> running = profile.Withheld(Catalog);
        profile.Started(running);

        profile.TryTheirsAgain();

        Assert.That(profile.NeedsSwitch, Is.True, "relaunched once the turn ends");
        Assert.That(profile.Withheld(Catalog), Is.EquivalentTo(running), "until then, the tools that run");
        Assert.That(profile.Profile, Is.EqualTo("esencial"));
        profile.Started(running);
        Assert.That(profile.NeedsSwitch, Is.False, "a start that stood in again asks for nothing more");
    }

    [Test]
    public void APersonalizadoStoodInForIsPutBackWithItsOwnList()
    {
        // Blind review of ARR3 (2): a put-back skipped Personalizado and its list was lost for good.
        var profile = new ToolProfile(_root);
        string[] mine = [.. Catalog.Where(name => profile.Refusal(name) is null).Take(3)];
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Personalizado, ["on"] = new JsonArray([.. mine.Select(static n => (JsonNode?)n)]) }), Is.Null);
        string chosen = File.ReadAllText(ProfileFile);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: false);
        Assert.That(profile.Profile, Is.EqualTo("esencial"));
        // ARR4 (REVX1 A3-1): Esencial's name, never a tool outside their list.
        Assert.That(profile.Withheld(Catalog), Is.SupersetOf(Catalog.Where(name => FieldStepProjection.ProfileLevel(name) > 0 && !mine.Contains(name))));
        Assert.That(profile.CardProfileFact()?["again"]?.GetValue<bool>(), Is.False, "not asked for by voice");
        JsonObject before = profile.Json();

        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        Assert.That(profile.Apply(before), Is.Null);

        Assert.That(File.ReadAllText(ProfileFile), Is.EqualTo(chosen), "their list, as it was");
        Assert.That(profile.Profile, Is.EqualTo("esencial"), "this start's");
    }

    [TestCase(false)]
    [TestCase(true)]
    public void AStandInForAPersonalizadoNeverTurnsOnWhatThePersonTurnedOff(bool shortCard)
    {
        // ARR4 (REVX1 A3-1): Personalizado = Diario without system.power and web.search, stood in for by Esencial: both
        // went to the model and ran. What a person turned off never turns on by itself: the stand-in keeps only the tools
        // of Esencial their list has.
        string[] off = ["system.power", "web.search"];
        IReadOnlySet<string> diarioOff = WithheldIn("diario"), esencialOff = WithheldIn("esencial");
        string[] mine = [.. Catalog.Where(name => !diarioOff.Contains(name) && !off.Contains(name))];
        Assert.That(off.All(name => Catalog.Contains(name) && !diarioOff.Contains(name) && !esencialOff.Contains(name)), "both in Diario and Esencial");
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Personalizado, ["on"] = new JsonArray([.. mine.Select(static n => (JsonNode?)n)]) }), Is.Null);
        string chosen = File.ReadAllText(ProfileFile);

        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard);

        IReadOnlySet<string> withheld = profile.Withheld(Catalog);
        Assert.Multiple(() =>
        {
            Assert.That(profile.Fitted?.Theirs, Is.True, "a stand-in");
            foreach (string name in off)
            {
                Assert.That(withheld, Does.Contain(name), $"{name}: not given to the model");
                Assert.That(profile.Refusal(name), Is.EqualTo(ToolProfile.OffCode), $"{name}: does not run");
            }

            Assert.That(Catalog.Where(name => !withheld.Contains(name)),
                Is.EquivalentTo(Catalog.Where(name => !esencialOff.Contains(name) && (mine.Contains(name) || FieldStepProjection.ProfileLevel(name) == 0))),
                "the intersection: Esencial's tools their list has");
            Assert.That(profile.Json()["on"]!.AsArray().Select(static n => n!.GetValue<string>()), Has.None.AnyOf(off), "Settings shows them off");
            Assert.That(File.ReadAllText(ProfileFile), Is.EqualTo(chosen), "their file untouched");
        });

        profile.StartAgain();
        Assert.That(profile.Withheld(Catalog), Is.EquivalentTo(Catalog.Where(name => !mine.Contains(name) && FieldStepProjection.ProfileLevel(name) > 0)),
            "the next start: their own list");
    }

    [Test]
    public void TheStandInPutBackKeepsThePersonsChoice()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: false);
        JsonObject before = profile.Json();
        Assert.That((string?)before["byCard"]?["factory"], Is.EqualTo("diario"));

        // A model change that was refused puts back what Settings had (MainWindowViewModel.UseModel).
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        Assert.That(profile.Apply(before), Is.Null);

        Assert.That(profile.Profile, Is.EqualTo("esencial"), "this start's");
        Assert.That((string?)JsonNode.Parse(File.ReadAllText(ProfileFile))!["profile"], Is.EqualTo("diario"), "theirs, as it was");
        Assert.That(JsonNode.Parse(File.ReadAllText(ProfileFile))!["byCard"], Is.Null);
    }

    [Test]
    public async Task CompletoChosenOnAFourGigabyteCardStartsInEsencialSaysWhyAndTriesCompletoAgainNextTime()
    {
        using var fake = new FakeMind();
        string file = Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        Directory.CreateDirectory(fake.DataRoot);
        File.WriteAllText(file, new JsonObject { ["profile"] = ToolProfile.Completo }.ToJsonString());
        fake.Script(new JsonObject
        {
            ["hello_card"] = new JsonObject { ["freeMb"] = 3400, ["needMb"] = 5200, ["needs"] = "last", ["context"] = 32768 },
            ["hello_card_memory"] = new JsonObject { ["totalMb"] = 4096, ["short"] = true },
        });
        MainWindowViewModel first = await ViewModelHarness.WithMindAsync();
        await using (first)
        await using (var view = new ChannelHarness(first))
        {
            int completo = ToolProfile.NeededContext(ToolProfile.Completo, null, null);
            Assert.That(Needs!.Split(',')[0], Is.EqualTo(completo.ToString(System.Globalization.CultureInfo.InvariantCulture)),
                "the person's profile first");
            Assert.That(Needs, Does.Contain(","), "and what fits under it, for the mind to start");
            Assert.That(first.ToolProfileState.Profile, Is.EqualTo("esencial"));
            JsonNode? notice = view.Channel.BootEvent()["cardProfile"];
            Assert.That((string?)notice?["profile"], Is.EqualTo("esencial"));
            Assert.That((string?)notice?["factory"], Is.EqualTo(ToolProfile.Completo));
            Assert.That((bool?)notice?["chosen"], Is.True, "said as the person's choice, never «BAXY eligió»");
            Assert.That((bool?)fake.Requests("catalog.configure")[^1]["cardProfile"]?["chosen"], Is.True);
            Assert.That(File.ReadAllText(file), Is.EqualTo("""{"profile":"completo"}"""), "theirs, never written");
        }

        fake.Script(new JsonObject());
        MainWindowViewModel second = await ViewModelHarness.WithMindAsync();
        await using (second)
        await using (var view = new ChannelHarness(second))
        {
            Assert.That(second.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo), "a card with room today: theirs");
            Assert.That(view.Channel.BootEvent()["cardProfile"], Is.Null);
        }
    }

    [Test]
    public async Task AStartThatFailsAfterStandingInSaysNoProfileRuns()
    {
        // Blind review of ARR3 (6): the hello stood in for Completo, then the server did not load; Settings still said
        // «en este arranque BAXY usa Esencial».
        using var fake = new FakeMind();
        string file = Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        Directory.CreateDirectory(fake.DataRoot);
        File.WriteAllText(file, new JsonObject { ["profile"] = ToolProfile.Completo }.ToJsonString());
        fake.Script(new JsonObject
        {
            ["hello_card"] = new JsonObject { ["freeMb"] = 3400, ["needMb"] = 5200, ["needs"] = "last", ["context"] = 32768 },
            ["hello_card_memory"] = new JsonObject { ["totalMb"] = 4096, ["short"] = true },
            ["reply"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject { ["type"] = "error", ["startup"] = new JsonObject { ["cause"] = "proceso_salio" } },
            },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.IsMindReady, Is.False);
            Assert.That(viewModel.ToolProfileState.Fitted, Is.Null, "no start runs: nothing stands in");
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo));
        }
    }

    [Test]
    public async Task ChoosingAProfileAfterAStartThatDidNotFitTriesTheStartAgain()
    {
        using var fake = new FakeMind();
        string file = Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        Directory.CreateDirectory(fake.DataRoot);
        File.WriteAllText(file, new JsonObject { ["profile"] = ToolProfile.Completo }.ToJsonString());
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject
                {
                    ["type"] = "error",
                    ["startup"] = new JsonObject
                    {
                        ["cause"] = "vram_insuficiente",
                        ["cardShort"] = new JsonObject { ["freeMb"] = 2000, ["needMb"] = 4400, ["context"] = 55296 },
                    },
                },
            },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(viewModel.Failure, Is.EqualTo(MainWindowViewModel.EngineUnavailable), "nothing fit: the breakdown");

            (int status, _) = await view.SendAsync("PUT", "/settings/tools", new JsonObject { ["profile"] = "esencial" });

            Assert.That(status, Is.EqualTo(200));
            Assert.That(viewModel.Failure, Is.Not.EqualTo(MainWindowViewModel.EngineUnavailable),
                "the profile chosen starts the model again, without closing BAXY");
        }
    }
}
