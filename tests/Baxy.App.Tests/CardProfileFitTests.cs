using System.IO;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// VRAM4B (2026-11-12, the leader's decision on what VRAM4 left open; the identity: «Listo para usar desde 4 GB de VRAM…
/// sin configurar nada»): the factory's tool profile, Completo, fits a card of 4 GB in all at no context, so a new install
/// went to the breakdown on its first start. While the person never chose a profile the App gives the mind what each
/// smaller ready-made one needs too, the mind starts in the largest the card holds and says which in its hello, and the App
/// runs this start with that profile's tools. VRAM4C (the leader's decision on VRAM4B's §7.2: «un asistente tiene que
/// portarse igual todos los días»): that profile is kept for this PC as BAXY's choice, never the person's (the file says
/// «byCard»), so another day with video memory to spare does not bring the factory's back by itself; the notice is said
/// on the start that chose it only, and why stays a fact the model can tell; changing it stays the person's.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class CardProfileFitTests
{
    private string _root = "";
    private string? _needs;

    [SetUp]
    public void SetUp()
    {
        _root = Directory.CreateTempSubdirectory("baxy-cardfit-").FullName;
        _needs = Environment.GetEnvironmentVariable(LocalContext.NeedsVariable);
        Environment.SetEnvironmentVariable(LocalContext.NeedsVariable, null);
    }

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable(LocalContext.NeedsVariable, _needs);
        Directory.Delete(_root, recursive: true);
    }

    private static IEnumerable<string> Catalog => ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name);

    private string ProfileFile => Path.Combine(_root, Baxy.Kernel.Policy.ToolProfileStore.FileName);

    [Test]
    public void ANewInstallIsToldToTheMindWithEverySmallerProfilesNeed()
    {
        IReadOnlyList<(string Profile, int Need)> smaller = ToolProfile.Smaller(null, null);
        Assert.That(smaller.Select(static one => one.Profile), Is.EqualTo(new[] { "avanzado", "diario", "esencial" }));
        Assert.That(smaller.Select(static one => one.Need), Is.Ordered.Descending);
        int factory = ToolProfile.NeededContext(ToolProfile.Completo, null, null);
        var context = new LocalContext(_root);
        context.ApplyEnvironment("cuda", factory, smaller.Select(static one => one.Need));
        Assert.That(Environment.GetEnvironmentVariable(LocalContext.NeedsVariable),
            Is.EqualTo(string.Join(',', new[] { factory }.Concat(smaller.Select(static one => one.Need)))));
        // a profile the person chose goes alone: the mind never takes another for them
        context.ApplyEnvironment("cuda", factory, []);
        Assert.That(Environment.GetEnvironmentVariable(LocalContext.NeedsVariable), Is.EqualTo(factory.ToString(System.Globalization.CultureInfo.InvariantCulture)));
    }

    [Test]
    public void WhatTheMindsHelloSaysOfTheCardIsReadWholeOrNotAtAll()
    {
        LocalContext.CardFit? fit = LocalContext.CardFit.From(JsonNode.Parse(
            """{"freeMb":3400,"needMb":3880,"needs":30073,"context":32768}"""));
        Assert.That(fit, Is.EqualTo(new LocalContext.CardFit(3400, 3880, 30073, 32768)));
        Assert.That(LocalContext.CardFit.From(null), Is.Null);
        Assert.That(LocalContext.CardFit.From(JsonNode.Parse("""{"freeMb":3400,"needMb":3880,"context":32768}""")), Is.Null);
        Assert.That(LocalContext.CardFit.From(JsonNode.Parse("""{"freeMb":"3400","needMb":3880,"needs":30073,"context":32768}""")), Is.Null);
    }

    [Test]
    public void TheProfileTheCardHoldsIsKeptForThisPcAsBaxysChoiceNotThePersons()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Chosen, Is.False);
        Assert.That(profile.Profile, Is.EqualTo(ToolProfile.Completo));
        IReadOnlySet<string> factory = profile.Withheld(Catalog);

        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);

        Assert.That(profile.Profile, Is.EqualTo("esencial"));
        Assert.That(profile.Withheld(Catalog), Has.Count.GreaterThan(factory.Count));
        Assert.That(profile.Fitted, Is.EqualTo(new ToolProfile.CardFitted("esencial", 3400, 3880)));
        Assert.That(profile.Chosen, Is.False, "VRAM4D: BAXY's, not the person's");
        Assert.That(profile.KeptForTheCard, Is.EqualTo(new ToolProfile.CardFitted("esencial", 3400, 3880)),
            "kept: the next start takes no other profile for a short card");
        JsonObject kept = JsonNode.Parse(File.ReadAllText(ProfileFile))!.AsObject();
        Assert.That((string?)kept["profile"], Is.EqualTo("esencial"));
        Assert.That(kept["byCard"]!.ToJsonString(), Is.EqualTo("""{"factory":"completo","freeMb":3400,"needMb":3880}"""),
            "written as BAXY's choice for this PC, to say why: not the person's");
        JsonObject said = profile.Json();
        Assert.That((string?)said["profile"], Is.EqualTo("esencial"));
        Assert.That(said["byCard"]!.ToJsonString(), Is.EqualTo("""{"factory":"completo","freeMb":3400,"needMb":3880}"""));
        Assert.That(profile.CardProfileFact()!.ToJsonString(), Does.Contain("\"freeMb\":3400").And.Contain("\"needMb\":3880"));

        // BAXY closed and opened again, or updated (the data folder stays), on a day with video memory to spare: the
        // mind says nothing of the card, and the profile is the one BAXY chose for this PC, why included.
        var again = new ToolProfile(_root);
        again.FitCard(null);
        Assert.That(again.Profile, Is.EqualTo("esencial"));
        Assert.That(again.Withheld(Catalog), Is.EquivalentTo(profile.Withheld(Catalog)));
        Assert.That(again.Fitted, Is.EqualTo(new ToolProfile.CardFitted("esencial", 3400, 3880)));
        Assert.That(again.Json()["byCard"]!.ToJsonString(), Is.EqualTo("""{"factory":"completo","freeMb":3400,"needMb":3880}"""));
        Assert.That(again.CardProfileFact(), Is.Not.Null, "why stays a fact the model can tell");
        Assert.That(Baxy.Kernel.Policy.ToolProfileStore.TryRead(_root, out string read), Is.True);
        Assert.That(read, Is.EqualTo("esencial"), "what the core, and a version before this one, read: the profile");
    }

    [Test]
    public void AProfileThePersonChoseIsNeverChangedByTheCard()
    {
        var profile = new ToolProfile(_root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        Assert.That(profile.Chosen, Is.True);

        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);

        Assert.That(profile.Profile, Is.EqualTo("diario"));
        Assert.That(profile.Fitted, Is.Null);
        Assert.That(profile.Json()["byCard"], Is.Null);
        Assert.That(profile.CardProfileFact(), Is.Null);
    }

    [Test]
    public void ChoosingAProfileWhileTheCardsRunsMakesItThePersons()
    {
        var profile = new ToolProfile(_root);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        Assert.That(profile.Chosen, Is.True);
        Assert.That(profile.Profile, Is.EqualTo("esencial"));
        Assert.That(profile.Fitted, Is.Null, "chosen, it is theirs: nothing says «by the card» any more");
        Assert.That(JsonNode.Parse(File.ReadAllText(ProfileFile))!["byCard"], Is.Null);
    }

    [Test]
    public void CompletoChosenOverTheCardsChoiceIsKeptAsThePersonsInSettingsAndByVoice()
    {
        // Settings → Tools (PUT /settings/tools)
        var profile = new ToolProfile(_root);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        Assert.That(profile.Profile, Is.EqualTo(ToolProfile.Completo));
        Assert.That(profile.Fitted, Is.Null);
        Assert.That(profile.Chosen, Is.True,
            "theirs: a start the card cannot hold says so with the ways out, and takes no other profile by itself");

        // by voice (baxy.settings.set → OwnSettingsHandler → ToolProfileStore.WritePreset)
        File.Delete(ProfileFile);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        Baxy.Kernel.Policy.ToolProfileStore.WritePreset(_root, ToolProfile.Completo);
        var heard = new ToolProfile(_root);
        Assert.That(heard.Profile, Is.EqualTo(ToolProfile.Completo));
        Assert.That(heard.Chosen, Is.True);
        Assert.That(heard.Fitted, Is.Null);

        // VRAM4D (REV18 R18-1): over a profile of the person's too, Completo is written, theirs (it was removed, and the
        // next start on a card of 4 GB took a smaller one by itself)
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        Baxy.Kernel.Policy.ToolProfileStore.WritePreset(_root, ToolProfile.Completo);
        Assert.That((string?)JsonNode.Parse(File.ReadAllText(ProfileFile))!["profile"], Is.EqualTo(ToolProfile.Completo));
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
        Assert.That((string?)JsonNode.Parse(File.ReadAllText(ProfileFile))!["profile"], Is.EqualTo(ToolProfile.Completo));
        Assert.That(new ToolProfile(_root).Profile, Is.EqualTo(ToolProfile.Completo));
        Assert.That(new ToolProfile(_root).Chosen, Is.True);
    }

    [Test]
    public void TheCardsProfilePutBackIsStillBaxysChoice()
    {
        // MainWindowViewModel puts back Json() after a change that was refused (a profile lent to another model).
        var profile = new ToolProfile(_root);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        JsonObject before = profile.Json();
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
        Assert.That(profile.Apply(before), Is.Null);
        Assert.That(profile.Profile, Is.EqualTo("esencial"));
        Assert.That(profile.Fitted, Is.EqualTo(new ToolProfile.CardFitted("esencial", 3400, 3880)));
        Assert.That(new ToolProfile(_root).Fitted, Is.EqualTo(new ToolProfile.CardFitted("esencial", 3400, 3880)), "kept");
    }

    [Test]
    public void OnlyASmallerReadyMadeProfileIsTaken()
    {
        var profile = new ToolProfile(_root);
        foreach (string notOne in new[] { ToolProfile.Completo, ToolProfile.Personalizado, "otro" })
        {
            profile.FitCard(new ToolProfile.CardFitted(notOne, 3400, 3880));
            Assert.That(profile.Fitted, Is.Null, notOne);
            Assert.That(profile.Profile, Is.EqualTo(ToolProfile.Completo), notOne);
            Assert.That(File.Exists(ProfileFile), Is.False, notOne);
        }
    }

    [Test]
    public void TheMindIsToldTheCardsProfileOnlyWhenThereIsOne()
    {
        using System.Text.Json.JsonDocument schema = System.Text.Json.JsonDocument.Parse("""{"type":"object","properties":{}}""");
        IReadOnlyList<OperationDescriptor> capabilities = [new OperationDescriptor("note.create", schema.RootElement.Clone(),
            OperationRisks.LowReversible, "note.create.v1", "Create a note with a title and its content.")];
        JsonObject plain = MindSidecarClient.CreateCatalogConfigureRequest(capabilities, null);
        JsonObject none = MindSidecarClient.CreateCatalogConfigureRequest(capabilities, null, cardProfile: null);
        Assert.That(none.ToJsonString(), Is.EqualTo(plain.ToJsonString()), "where the card has room the request is byte for byte the one of before");
        Assert.That(plain.ContainsKey("cardProfile"), Is.False);

        var profile = new ToolProfile(_root);
        profile.FitCard(new ToolProfile.CardFitted("esencial", 3400, 3880), shortCard: true);
        JsonObject told = MindSidecarClient.CreateCatalogConfigureRequest(capabilities, null, cardProfile: profile.CardProfileFact());
        Assert.That(told["cardProfile"]!.ToJsonString(), Is.EqualTo(profile.CardProfileFact()!.ToJsonString()));
        Assert.That((string?)told["cardProfile"]!["factory"], Is.AnyOf("Completo", "Complete"));
        Assert.That((string?)told["cardProfile"]!["profile"], Is.AnyOf("Esencial", "Essential"));
    }

    [Test]
    public async Task TheWholeAppKeepsTheCardsProfileAndSaysItOnlyOnTheStartThatChoseIt()
    {
        // VRAM4B §7.4: the App's own start with a mind whose hello says the card (FakeMind), twice, as BAXY closed and
        // opened again on a day with video memory to spare.
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["hello_card"] = new JsonObject { ["freeMb"] = 3400, ["needMb"] = 3880, ["needs"] = "last", ["context"] = 32768 },
            ["hello_card_memory"] = new JsonObject { ["totalMb"] = 4096, ["short"] = true },
        });
        string file = Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        MainWindowViewModel first = await ViewModelHarness.WithMindAsync();
        await using (first)
        await using (var view = new ChannelHarness(first))
        {
            Assert.That(Environment.GetEnvironmentVariable(LocalContext.NeedsVariable), Does.Contain(","),
                "never chosen: what each smaller profile needs goes to the mind too");
            Assert.That(first.ToolProfileState.Profile, Is.EqualTo("esencial"));
            Assert.That((string?)view.Channel.BootEvent()["cardProfile"]?["profile"], Is.EqualTo("esencial"), "said on this start");
            Assert.That((int?)fake.Requests("catalog.configure")[^1]["cardProfile"]?["freeMb"], Is.EqualTo(3400));
            Assert.That((string?)JsonNode.Parse(File.ReadAllText(file))!["profile"], Is.EqualTo("esencial"));
        }

        fake.Script(new JsonObject { ["hello_card_memory"] = new JsonObject { ["totalMb"] = 4096, ["short"] = true } });
        MainWindowViewModel second = await ViewModelHarness.WithMindAsync();
        await using (second)
        await using (var view = new ChannelHarness(second))
        {
            Assert.That(Environment.GetEnvironmentVariable(LocalContext.KeptVariable),
                Is.EqualTo(Environment.GetEnvironmentVariable(LocalContext.NeedsVariable)!.Split(',')[^1]),
                "kept for this PC: the mind serves its need alone while the card is short (VRAM4D)");
            Assert.That(second.ToolProfileState.Profile, Is.EqualTo("esencial"), "the card had room today: it stays");
            Assert.That(view.Channel.BootEvent()["cardProfile"], Is.Null, "the notice is said once");
            Assert.That((int?)fake.Requests("catalog.configure")[^1]["cardProfile"]?["freeMb"], Is.EqualTo(3400),
                "why stays a fact the model can tell");
            (int status, JsonObject tools) = await view.SendAsync("GET", "/settings/tools");
            Assert.That(status, Is.EqualTo(200));
            Assert.That((int?)tools["byCard"]?["needMb"], Is.EqualTo(3880), "Settings → Tools says why");
        }
    }
}
