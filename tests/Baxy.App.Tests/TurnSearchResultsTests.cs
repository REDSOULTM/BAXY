using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Uso real 2026-11-02: a web.fetch of one search result came back web_fetch_status_403 and the model gave up with
/// the turn's other results unread (src/Baxy.App/TurnSearchResults.cs, aid fetch_other_results).
/// </summary>
[TestFixture]
public sealed class TurnSearchResultsTests
{
    private const string Forbidden = """{"status":"failed","error":"web_fetch_status_403"}""";

    [Test]
    public void AFailedFetchListsTheTurnsSearchResultsNotYetRead()
    {
        var results = new TurnSearchResults();
        results.Observed("web.search", new JsonObject { ["query"] = "x" },
            Search("https://uno.example/a", "https://dos.example/b", "https://tres.example/c", "https://uno.example/a"));
        results.Observed("web.fetch", Fetch("https://tres.example/c"), """{"status":"completed","text":"..."}""");

        JsonNode? told = JsonNode.Parse(results.Observed("web.fetch", Fetch("uno.example/a"), Forbidden));

        Assert.Multiple(() =>
        {
            Assert.That((string?)told?["error"], Is.EqualTo("web_fetch_status_403"));
            Assert.That(told?["unreadResults"]?.AsArray().Select(static url => (string?)url),
                Is.EqualTo(new[] { "https://dos.example/b" }));
        });
    }

    [Test]
    public void AFetchThatReadsOrASearchOfAnotherTurnListsNothing()
    {
        var results = new TurnSearchResults();
        results.Observed("web.search", new JsonObject(), Search("https://uno.example/a", "https://dos.example/b"));
        const string Read = """{"status":"completed","text":"..."}""";
        Assert.That(results.Observed("web.fetch", Fetch("https://uno.example/a"), Read), Is.EqualTo(Read));

        results.NewTurn();
        Assert.That(results.Observed("web.fetch", Fetch("https://x.example/"), Forbidden), Is.EqualTo(Forbidden));
    }

    [Test]
    public void WhenEveryResultWasReadAFailedFetchSaysWhatItSaidBefore()
    {
        var results = new TurnSearchResults();
        results.Observed("web.search", new JsonObject(), Search("https://uno.example/a"));
        Assert.That(results.Observed("web.fetch", Fetch("https://uno.example/a"), Forbidden), Is.EqualTo(Forbidden));
    }

    [Test]
    [NonParallelizable]
    public void WithTheAidOffAFailedFetchSaysWhatItSaidBefore()
    {
        string? before = Environment.GetEnvironmentVariable("BAXY_AYUDAS");
        Environment.SetEnvironmentVariable("BAXY_AYUDAS", "result_hosts");
        try
        {
            var results = new TurnSearchResults();
            results.Observed("web.search", new JsonObject(), Search("https://uno.example/a", "https://dos.example/b"));
            Assert.That(results.Observed("web.fetch", Fetch("https://uno.example/a"), Forbidden), Is.EqualTo(Forbidden));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_AYUDAS", before);
        }
    }

    private static JsonObject Fetch(string url) => new() { ["url"] = url };

    private static string Search(params string[] urls) =>
        new JsonObject
        {
            ["status"] = "completed",
            ["observed"] = new JsonObject
            {
                ["results"] = new JsonArray([.. urls.Select(static url => (JsonNode)new JsonObject
                {
                    ["title"] = "t",
                    ["url"] = url,
                })]),
            },
        }.ToJsonString();
}
