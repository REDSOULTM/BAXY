using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

// M53 (paso 6 del goal v3, D35): la respuesta escrita desde una página consultada no la
// nombra; el mensaje publicado lleva su dirección y la vista la muestra como «fuente».
[TestFixture]
[NonParallelizable]
public sealed class ConsultedSourceTests
{
    private const string RecipeUrl = "https://es.wikibooks.org/wiki/Artes_culinarias/Recetas/Sopaipilla";

    [TearDown]
    public void TearDown() => FieldPublicationInjection.Reset();

    // The situation as the App hands it to the mind (compose-audit of the official window):
    // a JSON string with the verified receipt under «observed».
    private static JsonObject Facts(string authority, string url, bool verified = true) => new()
    {
        ["situation"] = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "web.search",
            ["polarity"] = verified ? "success" : "failure",
            ["verified"] = verified,
            ["succeeded"] = verified,
            ["observed"] = new JsonObject
            {
                ["version"] = 1,
                ["query"] = "receta sopaipillas",
                ["count"] = 1,
                ["results"] = new JsonArray(new JsonObject
                {
                    ["title"] = "Sopaipilla",
                    ["url"] = url,
                    ["snippet"] = "Ingredientes (para 4 personas):\n- 3 tazas de harina",
                }),
                ["reference"] = "recipe",
                ["authority"] = authority,
            },
        }.ToJsonString(),
    };

    [Test]
    public void OnlyAVerifiedWikimediaReadIsASource()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ConsultedSource.From(Facts("wikibooks_es_api", RecipeUrl)), Is.EqualTo(RecipeUrl));
            Assert.That(ConsultedSource.From(Facts("wikipedia_es_api", "https://es.wikipedia.org/wiki/El_hobbit")),
                Is.EqualTo("https://es.wikipedia.org/wiki/El_hobbit"));
            // Nothing consulted, another kind of source, or an address outside Wikimedia: no link.
            Assert.That(ConsultedSource.From(Facts("wikibooks_es_api", RecipeUrl, verified: false)), Is.Null);
            Assert.That(ConsultedSource.From(Facts("duckduckgo_lite_https", "https://example.com/receta")), Is.Null);
            Assert.That(ConsultedSource.From(Facts("wikibooks_es_api", "http://es.wikibooks.org/wiki/X")), Is.Null);
            Assert.That(ConsultedSource.From(Facts("wikibooks_es_api", "https://es.wikibooks.org.evil.test/wiki/X")),
                Is.Null);
            Assert.That(ConsultedSource.From(new JsonObject { ["situation"] = "{\"kind\":\"conversation\"}" }), Is.Null);
            Assert.That(ConsultedSource.From(new JsonObject()), Is.Null);
        });
    }

    [Test]
    public async Task TheComposedAnswerCarriesItsSourceAndTheViewOpensOnlyThatOne()
    {
        await using MainWindowViewModel viewModel = ReadyViewModel();
        var sink = new CollectingFieldEventSink();
        await using var telemetry = new FieldTelemetrySampler();
        await using var channel = new FieldProductChannel(viewModel, sink, telemetry, CancellationToken.None);
        var opened = new List<string>();
        channel.SourceOpener = url =>
        {
            opened.Add(url);
            return true;
        };
        const string answer = "La sopaipilla es una masa frita.\nIngredientes:\n- 3 tazas de harina";
        var pending = new PendingModelMessage(
            new UserMessageDraft("{}", "status", null), "receta de sopaipillas", Facts("wikibooks_es_api", RecipeUrl), "t1");
        var fallback = new PendingModelMessage(
            new UserMessageDraft("{}", "status", null), "receta de sopaipillas", Facts("wikibooks_es_api", RecipeUrl), "t2");

        await InvokeCallbackAsync(viewModel, "PublishComposedMessageAsync", answer, null, pending);
        await InvokeCallbackAsync(viewModel, "PublishComposedMessageAsync", "No lo encontré.",
            "model_response_rejected;deterministic_fallback", fallback);

        List<JsonObject> activity = sink.Snapshot().Where(item => (string?)item["type"] == "activity").ToList();
        FieldHttpResponse unknown = await channel.HandleHttpAsync(
            "POST", "/source/open", new JsonObject { ["url"] = "https://es.wikipedia.org/wiki/Otra" }.ToJsonString());
        FieldHttpResponse known = await channel.HandleHttpAsync(
            "POST", "/source/open", new JsonObject { ["url"] = RecipeUrl }.ToJsonString());

        Assert.Multiple(() =>
        {
            Assert.That(activity, Has.Count.EqualTo(2));
            Assert.That((string?)activity[0]["entry"]?["msg"], Is.EqualTo(answer));
            Assert.That((string?)activity[0]["entry"]?["source"], Is.EqualTo(RecipeUrl));
            // The body — what the voice reads — never carries the address.
            Assert.That(viewModel.Messages[^2].Body, Does.Not.Contain("http"));
            Assert.That(viewModel.Messages[^2].SourceUrl, Is.EqualTo(RecipeUrl));
            // A fallback line was not written from the page: no link.
            Assert.That(activity[1]["entry"]?["source"], Is.Null);
            Assert.That(unknown.Status, Is.EqualTo(404));
            Assert.That(known.Status, Is.EqualTo(200));
            Assert.That(opened, Is.EqualTo(new[] { RecipeUrl }));
        });
    }

    private static MainWindowViewModel ReadyViewModel()
    {
        var viewModel = new MainWindowViewModel();
        PropertyInfo ready = typeof(MainWindowViewModel).GetProperty(nameof(MainWindowViewModel.IsReady))!;
        ready.SetValue(viewModel, true);
        return viewModel;
    }

    private static async Task InvokeCallbackAsync(
        MainWindowViewModel viewModel, string methodName, params object?[] arguments)
    {
        MethodInfo callback = typeof(MainWindowViewModel).GetMethod(
            methodName, BindingFlags.Instance | BindingFlags.NonPublic)!;
        await (Task)callback.Invoke(viewModel, arguments)!;
    }
}
