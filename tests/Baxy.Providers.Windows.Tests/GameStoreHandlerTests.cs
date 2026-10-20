using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C04 variant, C05): the store's search and a game's page are app.open of the game catalog's
/// application at that place, in front, with what was asked as its value; nothing else.
/// </summary>
[TestFixture]
public sealed class GameStoreHandlerTests
{
    [TestCase("game.store.search", "results", "query", "zombis")]
    [TestCase("game.store.page", "game", "title", "Celeste")]
    public async Task AStoreActIsTheApplicationsPlaceOpenedInFront(string operation, string place, string argument, string value)
    {
        var opened = new List<JsonElement>();
        var handler = new GameStoreHandler(operation, place, argument, (invocation, _) =>
        {
            opened.Add(invocation.Arguments.Clone());
            return ValueTask.FromResult(OperationOutcome.Success(Element("""{"placeRequested":true}""")));
        });

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation($$"""{"{{argument}}":"{{value}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(opened, Has.Count.EqualTo(1));
            Assert.That(opened[0].GetProperty("appId").GetString(), Is.EqualTo("Steam"));
            Assert.That(opened[0].GetProperty("place").GetString(), Is.EqualTo(place));
            Assert.That(opened[0].GetProperty("placeValue").GetString(), Is.EqualTo(value));
            Assert.That(opened[0].GetProperty("foreground").GetBoolean(), Is.True);
        });
    }

    [Test]
    public void TheirSchemasTakeOnlyWhatIsAskedFor()
    {
        ProductOperationDescriptor search = ProductCatalog.GetRequired("game.store.search");
        ProductOperationDescriptor page = ProductCatalog.GetRequired("game.store.page");

        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.IsValid(Element("""{"query":"zombis"}"""), search.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(Element("{}"), search.ArgumentsSchema), Is.False);
            Assert.That(OperationArgumentValidator.IsValid(Element("""{"title":"Celeste"}"""), page.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(Element("""{"title":"Celeste","appId":"1"}"""), page.ArgumentsSchema), Is.False);
            Assert.That(ApplicationPlaces.ApplicationOfCatalog("steam"), Is.EqualTo("Steam"));
            Assert.That(ApplicationPlaces.ApplicationOfCatalog("epic"), Is.Null);
        });
    }

    private static JsonElement Element(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        return document.RootElement.Clone();
    }

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", Element(arguments));
}
