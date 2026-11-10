using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The credit a search's source asks of whoever shows its results, from the provider's result to the step the view
/// receives: the result as WebBrowserAdapter's SearchReceipt writes it (ExternalAdaptersTests pins that shape), the
/// engine's message (OperationVisibleFacts.FromOutcome, which nests it in «observed»), the turn loop's step and the
/// view's channel (FieldProductChannel.OnStepCompleted).
/// </summary>
[TestFixture]
public sealed class SourceCreditTests
{
    [TearDown]
    public void BackToSpanish() => UiLanguage.Use(UiLanguage.Spanish);

    // DEP5 (2026-11-08, the App on the owner's PC): 0 of 2 DuckDuckGo searches showed «Fuente: DuckDuckGo»; the chip
    // read «answeredBy» at the root of the step's result, and the engine's message keeps it inside «observed». LIC2's
    // sources: DuckDuckGo's partnerships page («Please give us attribution where it makes sense»), OpenStreetMap's
    // copyright page («credit OpenStreetMap and its contributors»), Wikipedia's CC BY-SA 4.0 (attribution).
    [TestCase("web", "duckduckgo_html_hidden_webview2", "DuckDuckGo", false, "Leído · Fuente: DuckDuckGo")]
    [TestCase("web", "duckduckgo_html_hidden_webview2", "DuckDuckGo", true, "Read · Source: DuckDuckGo")]
    [TestCase("places", "openstreetmap_photon", "OpenStreetMap", false, "Leído · Fuente: OpenStreetMap")]
    [TestCase("encyclopedia", "wikipedia_es_api", "Wikipedia", false, "Leído · Fuente: Wikipedia")]
    public async Task TheViewCreditsTheSourceThatAnsweredASearch(
        string source, string authority, string answeredBy, bool english, string obs)
    {
        JsonObject shown = await ShownAsync(SearchResult(source, authority, answeredBy, results: 3, snippet: 80), english);

        Assert.That((string?)shown["obs"], Is.EqualTo(obs));
    }

    // Ten results with long snippets go past the engine's 8 KiB and are projected (observedLimit): the credit, a short
    // fact of the result, is kept.
    [Test]
    public async Task TheCreditSurvivesAResultCutToFitTheMessage()
    {
        JsonElement result = SearchResult("web", "duckduckgo_html_hidden_webview2", "DuckDuckGo", results: 10, snippet: 1_200);
        string message = OperationVisibleFacts.FromOutcome("web.search", OperationOutcome.Success(result));
        Assert.That(JsonNode.Parse(message)!["observedLimit"], Is.Not.Null, "the result was cut to fit");

        JsonObject shown = await ShownAsync(result, english: false);

        Assert.That((string?)shown["obs"], Is.EqualTo("Leído · Fuente: DuckDuckGo"));
    }

    // The one receipt shape of web.search (WebBrowserAdapter.SearchReceipt).
    private static JsonElement SearchResult(string source, string authority, string answeredBy, int results, int snippet)
    {
        var shape = new JsonObject
        {
            ["version"] = 1,
            ["source"] = source,
            ["query"] = "farmacias",
        };
        if (source == "places")
        {
            shape["sent"] = new JsonObject { ["kind"] = "pharmacy", ["place"] = "Plaza Mayor" };
        }

        shape["results"] = new JsonArray([.. Enumerable.Range(1, results).Select(index => (JsonNode)new JsonObject
        {
            ["title"] = "Resultado " + index,
            ["url"] = "https://example.org/" + index,
            ["snippet"] = new string('x', snippet),
        })]);
        shape["resultCount"] = results;
        shape["authority"] = authority;
        shape["answeredBy"] = answeredBy;
        return JsonDocument.Parse(shape.ToJsonString()).RootElement.Clone();
    }

    // The step the view got for a web.search whose provider returned this result.
    private static async Task<JsonObject> ShownAsync(JsonElement result, bool english)
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            UiLanguage.Use(english ? UiLanguage.English : UiLanguage.Spanish);
            string message = OperationVisibleFacts.FromOutcome("web.search", OperationOutcome.Success(result));
            var step = new NativeTurnStep("web.search", new JsonObject { ["query"] = "farmacias" },
                OperationStatuses.Completed, true, null, 12, message, "c1", Sent: true);
            const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
            object loop = typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
            var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
            host.StepCompleted!(step);
            return view.Sink.Items.Single(static i => (string?)i["who"] == "baxy")["steps"]!.AsArray()
                .OfType<JsonObject>().Single();
        }
    }
}
