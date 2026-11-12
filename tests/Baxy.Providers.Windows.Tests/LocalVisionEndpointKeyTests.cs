using System.Net;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// PRV1 (revisión de privacidad 2026-11-09, PRIV-04): the mind's llama-server asks its key of every request
/// (llama.cpp, tools/server/README.md: «--api-key KEY … (env: LLAMA_API_KEY)»). The engine's own requests to it, the
/// vision question and the slot it sets aside and puts back around it, carry the key the App gave it for this start
/// (BAXY_VISION_API_KEY, MindRuntimeDiscovery). With a double: the server itself is tried on the notebook.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class LocalVisionEndpointKeyTests
{
    private static readonly string[] Touched = ["BAXY_VISION_API_KEY", "BAXY_VISION_SLOT", "BAXY_VISION_SLOT_DIR"];
    private readonly Dictionary<string, string?> _saved = [];

    [SetUp]
    public void SetUp()
    {
        foreach (string name in Touched)
        {
            _saved[name] = Environment.GetEnvironmentVariable(name);
            Environment.SetEnvironmentVariable(name, null);
        }
    }

    [TearDown]
    public void TearDown()
    {
        foreach ((string name, string? value) in _saved)
        {
            Environment.SetEnvironmentVariable(name, value);
        }
    }

    [Test]
    public async Task TheSlotSetAsideAndPutBackAndTheQuestionCarryTheServersKey()
    {
        Environment.SetEnvironmentVariable("BAXY_VISION_API_KEY", "clave-de-este-arranque");
        var seen = new Recording();
        using var http = new HttpClient(seen);
        var endpoint = new Uri("http://127.0.0.1:8077/v1/chat/completions");

        string? held = await LocalVisionEndpoint.HoldSlotAsync(http, endpoint, CancellationToken.None);
        await LocalVisionEndpoint.PutSlotBackAsync(http, endpoint, held!);
        using var question = new HttpRequestMessage(HttpMethod.Post, endpoint);
        LocalVisionEndpoint.Authorize(question);

        Assert.Multiple(() =>
        {
            Assert.That(seen.Requests.Select(static request => request.Path),
                Is.EqualTo(new[] { "/slots/0?action=save", "/slots/0?action=restore" }));
            Assert.That(seen.Requests.Select(static request => request.Authorization),
                Is.All.EqualTo("Bearer clave-de-este-arranque"));
            Assert.That(question.Headers.Authorization?.ToString(), Is.EqualTo("Bearer clave-de-este-arranque"));
        });
    }

    [Test]
    public void AServerThatWasGivenNoKeyIsAskedWithNone()
    {
        using var question = new HttpRequestMessage(HttpMethod.Post, "http://127.0.0.1:8077/v1/chat/completions");

        LocalVisionEndpoint.Authorize(question);

        Assert.That(question.Headers.Authorization, Is.Null);
    }

    private sealed class Recording : HttpMessageHandler
    {
        internal List<(string Path, string? Authorization)> Requests { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Requests.Add((request.RequestUri!.PathAndQuery, request.Headers.Authorization?.ToString()));
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK));
        }
    }
}
