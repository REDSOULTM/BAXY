using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The App's client of the mind (src/Baxy.App/MindSidecarClient.cs) against the fake mind.</summary>
[TestFixture]
public sealed class MindSidecarClientTests
{
    [Test]
    public async Task ReleasingTheMicrophoneAndReadingTheVoiceDoNotWaitForATurn()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["hold"] = new JsonObject { ["turn.decide"] = "go" } });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        Task<MindStep?> turn = mind.DecideAsync("hola", null, CancellationToken.None);
        Assert.That(await fake.WaitSeenAsync("turn.decide"), Is.True);

        // The mind answers both on its reader, as it reads them; behind the turn they waited for the model.
        using var meanwhile = new CancellationTokenSource(TimeSpan.FromSeconds(3));
        bool released = await Within(() => mind.VoiceReleaseAsync(TimeSpan.FromSeconds(3), meanwhile.Token));
        bool status = await Within(async () =>
            await mind.VoiceStatusAsync(TimeSpan.FromSeconds(3), meanwhile.Token) is not null);

        fake.Open("go");
        Assert.That(await turn, Is.Not.Null);
        Assert.That(released, Is.True, "voice.release waited behind the turn");
        Assert.That(status, Is.True, "voice.status waited behind the turn");
    }

    [Test]
    public void TheCatalogTheMindReadsCarriesEachToolsEffects()
    {
        // Al máximo 5.1: «corrige» reads them; a tool without one carries no field, as the saved catalogs.
        JsonObject request = MindSidecarClient.CreateCatalogConfigureRequest(
            [.. ProductCatalog.ToolDescriptors.Select(static descriptor =>
                ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor)))],
            applicationCatalog: null);
        JsonObject Tool(string name) => request["capabilities"]!.AsArray().OfType<JsonObject>()
            .Single(tool => (string?)tool["name"] == name);

        Assert.Multiple(() =>
        {
            Assert.That(Tool("input.key.press")["effects"]!.ToJsonString(), Is.EqualTo("[\"window_input\"]"));
            Assert.That(Tool("web.search")["effects"]!.ToJsonString(), Is.EqualTo("[\"network\"]"));
            Assert.That(Tool("note.create").ContainsKey("effects"), Is.False);
        });
    }

    // A request that is still waiting when its caller gives up is a false, not an exception.
    private static async Task<bool> Within(Func<Task<bool>> request)
    {
        try
        {
            return await request();
        }
        catch (OperationCanceledException)
        {
            return false;
        }
    }
}
