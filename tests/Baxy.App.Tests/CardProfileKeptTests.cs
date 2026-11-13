using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// VRAM4D (REV18, 13-11-2026, the two findings that held the 1.5.1 back): the App's own start with a mind whose hello
/// says the card (FakeMind), in the scenarios REV18 tells. R18-1: on a card of 4 GB, Completo the person asks for over a
/// profile they chose removed the file, and the next start took Esencial by itself and said BAXY chose it. R18-2: on a
/// card with room, a start while a game held its memory wrote BAXY's choice, and the card stayed in Esencial for good.
/// The leader's decision: what the person chooses is theirs and always kept, Completo included; BAXY keeps a choice of
/// its own only on a card short in all (the hello's «cardMemory»); elsewhere a fit is that start's alone.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class CardProfileKeptTests
{
    private static readonly JsonObject EsencialFits = new()
    {
        ["freeMb"] = 3400, ["needMb"] = 3880, ["needs"] = "last", ["context"] = 32768,
    };

    private static JsonObject Script(bool card, int? totalMb, bool? shortCard)
    {
        var script = new JsonObject();
        if (card)
        {
            script["hello_card"] = EsencialFits.DeepClone();
        }

        if (totalMb is { } total && shortCard is { } isShort)
        {
            script["hello_card_memory"] = new JsonObject { ["totalMb"] = total, ["short"] = isShort };
        }

        return script;
    }

    private static string? Needs => Environment.GetEnvironmentVariable(LocalContext.NeedsVariable);

    [TestCase("diario")]
    [TestCase("esencial")]
    public async Task R18_1_CompletoThePersonAsksForOnAFourGigabyteCardIsKeptAndNeverBecomesBaxysChoice(string before)
    {
        using var fake = new FakeMind();
        string file = Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        foreach (bool byVoice in new[] { false, true })
        {
            // A profile of the person's own (Settings, «Arrancar en Esencial», a choice of the 1.5.0), then Completo
            // asked for in Settings → Tools or by voice (baxy.settings.set → ToolProfileStore.WritePreset).
            Directory.CreateDirectory(fake.DataRoot);
            File.WriteAllText(file, new JsonObject { ["profile"] = before }.ToJsonString());
            if (byVoice)
            {
                Baxy.Kernel.Policy.ToolProfileStore.WritePreset(fake.DataRoot, ToolProfile.Completo);
            }
            else
            {
                Assert.That(new ToolProfile(fake.DataRoot).Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
            }

            Assert.That(File.Exists(file), Is.True, "theirs: kept, Completo too");
            Assert.That((string?)JsonNode.Parse(File.ReadAllText(file))!["profile"], Is.EqualTo(ToolProfile.Completo));

            // BAXY opened again on the card of 4 GB, ~3,400 MiB free: the mind would take Esencial from a list.
            fake.Script(Script(card: true, 4096, shortCard: true));
            MainWindowViewModel app = await ViewModelHarness.WithMindAsync();
            await using (app)
            await using (var view = new ChannelHarness(app))
            {
                Assert.That(Needs, Does.Not.Contain(","), "their profile goes alone: the mind takes no other for them");
                Assert.That(app.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo), byVoice ? "by voice" : "in Settings");
                Assert.That(view.Channel.BootEvent()["cardProfile"], Is.Null, "no «BAXY eligió»");
                Assert.That(fake.Requests("catalog.configure")[^1]["cardProfile"], Is.Null);
                Assert.That(JsonNode.Parse(File.ReadAllText(file))!["byCard"], Is.Null);
                Assert.That((string?)JsonNode.Parse(File.ReadAllText(file))!["profile"], Is.EqualTo(ToolProfile.Completo));
            }
        }
    }

    [Test]
    public async Task R18_2_AGameOpenAtOneStartOnACardWithRoomChangesThatStartAlone()
    {
        using var fake = new FakeMind();
        string file = Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);

        // A card of 8 GB, no profile ever chosen; at this start a game holds its memory and 3,400 MiB are free.
        fake.Script(Script(card: true, 8192, shortCard: false));
        MainWindowViewModel first = await ViewModelHarness.WithMindAsync();
        await using (first)
        await using (var view = new ChannelHarness(first))
        {
            Assert.That(first.ToolProfileState.Profile, Is.EqualTo("esencial"), "what fits, this start");
            Assert.That(File.Exists(file), Is.False, "nothing kept: the card has room");
            JsonNode? notice = view.Channel.BootEvent()["cardProfile"];
            Assert.That((string?)notice?["profile"], Is.EqualTo("esencial"), "said, truthfully");
            Assert.That((bool?)notice?["thisStart"], Is.True, "this start only");
            Assert.That(fake.Requests("catalog.configure")[^1]["cardProfile"], Is.Null,
                "the system text of an Esencial: the kept choice's fact would be false");
            (int status, JsonObject tools) = await view.SendAsync("GET", "/settings/tools");
            Assert.That(status, Is.EqualTo(200));
            Assert.That((bool?)tools["byCard"]?["thisStart"], Is.True);
        }

        // The game closed, BAXY opened again: the profile of always.
        fake.Script(Script(card: false, 8192, shortCard: false));
        MainWindowViewModel second = await ViewModelHarness.WithMindAsync();
        await using (second)
        await using (var view = new ChannelHarness(second))
        {
            Assert.That(Needs, Does.Contain(","), "never chosen: the factory's first, and the smaller ones");
            Assert.That(second.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo));
            Assert.That(view.Channel.BootEvent()["cardProfile"], Is.Null);
            Assert.That(File.Exists(file), Is.False);
        }
    }

    [Test]
    public async Task R18_2_BaxysChoiceTheOneFivePointOneWroteOnACardWithRoomGoesAtTheStart()
    {
        using var fake = new FakeMind();
        string file = Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        Directory.CreateDirectory(fake.DataRoot);
        File.WriteAllText(file, """{"profile":"esencial","byCard":{"factory":"completo","freeMb":3400,"needMb":3880}}""");

        fake.Script(Script(card: false, 8192, shortCard: false));
        MainWindowViewModel app = await ViewModelHarness.WithMindAsync();
        await using (app)
        await using (var view = new ChannelHarness(app))
        {
            Assert.That(Needs, Does.Contain(","), "the mind may serve the factory's: BAXY's choice is no person's");
            Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_CTX_KEPT"), Is.EqualTo(Needs!.Split(',')[^1]),
                "and which one BAXY kept, for a short card");
            Assert.That(app.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo));
            Assert.That(File.Exists(file), Is.False, "dropped at the start");
            Assert.That(view.Channel.BootEvent()["cardProfile"], Is.Null);
            Assert.That(fake.Requests("catalog.configure")[^1]["cardProfile"], Is.Null);
        }
    }

    [Test]
    public async Task OnAShortCardBaxysChoiceIsKeptAsVram4cDid()
    {
        using var fake = new FakeMind();
        string file = Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);
        fake.Script(Script(card: true, 4096, shortCard: true));
        MainWindowViewModel first = await ViewModelHarness.WithMindAsync();
        await using (first)
        await using (var view = new ChannelHarness(first))
        {
            Assert.That(first.ToolProfileState.Profile, Is.EqualTo("esencial"));
            Assert.That((string?)JsonNode.Parse(File.ReadAllText(file))!["byCard"]?["factory"], Is.EqualTo(ToolProfile.Completo));
            Assert.That(view.Channel.BootEvent()["cardProfile"]?["thisStart"], Is.Null, "kept: «se queda en él»");
            Assert.That((int?)fake.Requests("catalog.configure")[^1]["cardProfile"]?["freeMb"], Is.EqualTo(3400));
        }

        // Another day with memory to spare on that card: the choice stays, the notice is not said again.
        fake.Script(Script(card: false, 4096, shortCard: true));
        MainWindowViewModel second = await ViewModelHarness.WithMindAsync();
        await using (second)
        await using (var view = new ChannelHarness(second))
        {
            Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_CTX_KEPT"), Is.EqualTo(Needs!.Split(',')[^1]));
            Assert.That(second.ToolProfileState.Profile, Is.EqualTo("esencial"));
            Assert.That(view.Channel.BootEvent()["cardProfile"], Is.Null);
            Assert.That((int?)fake.Requests("catalog.configure")[^1]["cardProfile"]?["freeMb"], Is.EqualTo(3400));
        }
    }

    [Test]
    public async Task WithTheCardsWholeMemoryUnsaidNothingIsKept()
    {
        // A hello with no «cardMemory» (not measured): the fit is this start's, as it was in VRAM4B.
        using var fake = new FakeMind();
        fake.Script(Script(card: true, null, null));
        MainWindowViewModel app = await ViewModelHarness.WithMindAsync();
        await using (app)
        {
            Assert.That(app.ToolProfileState.Profile, Is.EqualTo("esencial"));
            Assert.That(File.Exists(Path.Combine(fake.DataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName)), Is.False);
        }
    }
}
