using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización M (comprobación en vivo de identidad §3a: el panel MEMORY decía «La memoria privada se gestiona
/// mediante el chat de BAXY.» con 0 entradas aunque había datos; editar y borrar daban 409). El canal de la interfaz
/// lista, edita y borra la memoria real de un perfil temporal con las mismas operaciones del catálogo que el chat: cada
/// cambio queda en el journal y el contador es el número del almacén.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class MemoryPanelTests
{
    [Test]
    public async Task ThePanelListsEditsAndForgetsTheStoreThroughTheCatalogOperations()
    {
        string dataRoot = PrivateDataRootTestSupport.NewPath("memory-panel");
        Directory.CreateDirectory(dataRoot);
        string? previous = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", dataRoot);
        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.That(viewModel.IsReady, Is.True);
            var sink = new CollectingFieldEventSink();
            await using var telemetry = new FieldTelemetrySampler();
            await using var channel = new FieldProductChannel(viewModel, sink, telemetry, CancellationToken.None);

            // Off by default: viewing the empty memory is no error and never switches it on.
            JsonElement empty = Body(await channel.HandleHttpAsync("GET", "/memory", null));
            Assert.Multiple(() =>
            {
                Assert.That(empty.GetProperty("enabled").GetBoolean(), Is.False);
                Assert.That(empty.GetProperty("items").GetArrayLength(), Is.Zero);
                Assert.That(empty.TryGetProperty("error", out _), Is.False);
                Assert.That(Store(dataRoot).Status(new MemoryStatusRequest()).Enabled, Is.False);
            });

            int revisionBefore = Body(await channel.HandleHttpAsync("GET", "/surfaces", null))
                .GetProperty("memory_revision").GetInt32();
            await SubmitAsync(viewModel, "recuerda que mi color favorito es turquesa");
            await SubmitAsync(viewModel, "recuerda que mi bebida favorita es el mate");
            string journal = Path.Combine(dataRoot, "journal", "missions.jsonl");

            // The count is the store's, read when the view asks for its surfaces after the chat changed it.
            JsonElement surfaces = Body(await channel.HandleHttpAsync("GET", "/surfaces", null));
            Assert.That(surfaces.GetProperty("memory").GetInt32(), Is.EqualTo(2));
            Assert.That(sink.Snapshot().Last(static item => (string?)item["type"] == "surfaces")["memory"]!
                .GetValue<int>(), Is.EqualTo(2));
            Assert.That(
                channel.CreateSocketBootstrap().Single(static item => (string?)item["type"] == "surfaces")["memory"]!
                    .GetValue<int>(),
                Is.EqualTo(2));

            // Encargo I2 (identidad redpc: the open panel listed 3 while the counter said 4): the counter's own event
            // numbers the chat's change of the store, so the open list reads itself again with it (MemoryPanel.tsx).
            int revision = surfaces.GetProperty("memory_revision").GetInt32();
            int published = sink.Snapshot().Count(static item => (string?)item["type"] == "surfaces");
            Assert.Multiple(() =>
            {
                Assert.That(revision, Is.GreaterThan(revisionBefore));
                Assert.That(sink.Snapshot().Last(static item => (string?)item["type"] == "surfaces")["memory_revision"]!
                    .GetValue<int>(), Is.EqualTo(revision));
            });

            // Contracaso: asked again with no change, the number stays and no event is published.
            JsonElement unchanged = Body(await channel.HandleHttpAsync("GET", "/surfaces", null));
            Assert.Multiple(() =>
            {
                Assert.That(unchanged.GetProperty("memory_revision").GetInt32(), Is.EqualTo(revision));
                Assert.That(sink.Snapshot().Count(static item => (string?)item["type"] == "surfaces"),
                    Is.EqualTo(published));
            });

            JsonElement listed = Body(await channel.HandleHttpAsync("GET", "/memory", null));
            JsonElement color = Item(listed, "turquesa");
            string colorKey = color.GetProperty("key").GetString()!;
            Assert.Multiple(() =>
            {
                Assert.That(listed.GetProperty("enabled").GetBoolean(), Is.True);
                Assert.That(listed.GetProperty("items").GetArrayLength(), Is.EqualTo(2));
                Assert.That(color.GetProperty("updated_at").GetString(), Has.Length.EqualTo(16));
            });

            // Edit one: memory.correct on the record the store names; the journal records it.
            long beforeEdit = new FileInfo(journal).Length;
            FieldHttpResponse edited = await channel.HandleHttpAsync(
                "POST", "/memory", new JsonObject { ["key"] = colorKey, ["value"] = "verde" }.ToJsonString());
            Assert.Multiple(() =>
            {
                Assert.That(edited.Status, Is.EqualTo(200));
                Assert.That(Item(Body(edited), "verde").GetProperty("key").GetString(), Is.EqualTo(colorKey));
                Assert.That(Values(dataRoot), Is.EquivalentTo(new[] { "verde", "mate" }));
                Assert.That(Journal(journal), Does.Contain("memory.correct"));
                Assert.That(new FileInfo(journal).Length, Is.GreaterThan(beforeEdit));
            });

            // Contracaso: a key the store does not hold is not created by an edit, and nothing changes.
            FieldHttpResponse missing = await channel.HandleHttpAsync(
                "POST", "/memory", new JsonObject { ["key"] = "no_such_datum", ["value"] = "x" }.ToJsonString());
            Assert.Multiple(() =>
            {
                Assert.That(missing.Status, Is.EqualTo(404));
                Assert.That(Body(missing).GetProperty("error").GetString(), Is.EqualTo("memory_not_found"));
                Assert.That(Values(dataRoot), Is.EquivalentTo(new[] { "verde", "mate" }));
            });

            // Forget one: memory.forget of that selector, confirmed by the panel for that exact invocation.
            FieldHttpResponse forgotten = await channel.HandleHttpAsync(
                "DELETE", "/memory/" + Uri.EscapeDataString(colorKey), null);
            Assert.Multiple(() =>
            {
                Assert.That(forgotten.Status, Is.EqualTo(200));
                Assert.That(Body(forgotten).GetProperty("items").GetArrayLength(), Is.EqualTo(1));
                Assert.That(Body(forgotten).GetProperty("total").GetInt32(), Is.EqualTo(1));
                Assert.That(Values(dataRoot), Is.EqualTo(new[] { "mate" }));
                Assert.That(Journal(journal), Does.Contain("memory.forget"));
                Assert.That(sink.Snapshot().Last(static item => (string?)item["type"] == "surfaces")["memory"]!
                    .GetValue<int>(), Is.EqualTo(1));
            });

            // Revisión M H7: no entry's key means «everything»; a value the chat would refuse is not kept here either.
            foreach ((string method, string route, string? body) in new (string, string, string?)[]
            {
                ("DELETE", "/memory/%2A", null), ("DELETE", "/memory/", null), ("DELETE", "/memory/%20", null),
                ("DELETE", "/memory", null), ("DELETE", "/memory", "{\"scope\":\"exact\"}"),
            })
            {
                Assert.That((await channel.HandleHttpAsync(method, route, body)).Status, Is.EqualTo(400), route);
            }

            FieldHttpResponse secret = await channel.HandleHttpAsync("POST", "/memory",
                new JsonObject { ["key"] = "FAVORITE_DRINK", ["value"] = "sk-proj-abcdefgh12345678" }.ToJsonString());
            Assert.Multiple(() =>
            {
                Assert.That(secret.Status, Is.EqualTo(409));
                Assert.That(Body(secret).GetProperty("error").GetString(), Is.EqualTo("memory_value_refused"));
                Assert.That(Values(dataRoot), Is.EqualTo(new[] { "mate" }));
            });

            // Forget everything, by its own request.
            FieldHttpResponse cleared = await channel.HandleHttpAsync(
                "DELETE", "/memory", new JsonObject { ["scope"] = "all" }.ToJsonString());
            JsonElement countedAfter = Body(await channel.HandleHttpAsync("GET", "/surfaces", null));
            Assert.Multiple(() =>
            {
                Assert.That(cleared.Status, Is.EqualTo(200));
                Assert.That(Body(cleared).GetProperty("items").GetArrayLength(), Is.Zero);
                Assert.That(Store(dataRoot).Status(new MemoryStatusRequest()).TotalRecords, Is.Zero);
                Assert.That(countedAfter.GetProperty("memory").GetInt32(), Is.Zero);
            });
            Assert.That(new DurableRetryStore(Path.Combine(dataRoot, "shell", "retry-outbox.v1.json")).Load(),
                Is.Empty);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previous);
            if (Directory.Exists(dataRoot))
            {
                Directory.Delete(dataRoot, recursive: true);
            }
        }
    }

    [Test]
    public void OnlyTheAppsOwnDocumentReachesTheChannel()
    {
        // The protection the old 409 stood for (ADR-0008 §5: no direct authority over the private memory for content
        // the view did not author): the bridge hands the channel only messages of the App's own document.
        Assert.Multiple(() =>
        {
            Assert.That(HistoricalFieldOriginPolicy.IsTrustedDocumentSource(HistoricalFieldOriginPolicy.EntryPoint),
                Is.True);
            Assert.That(HistoricalFieldOriginPolicy.IsTrustedDocumentSource("https://example.com/index.html"), Is.False);
            Assert.That(HistoricalFieldOriginPolicy.IsTrustedDocumentSource("https://baxy.local/other.html"), Is.False);
            Assert.That(HistoricalFieldOriginPolicy.IsTrustedDocumentSource("http://baxy.local/index.html"), Is.False);
        });
    }

    private static LocalMemoryStore Store(string dataRoot) => new(
        Path.Combine(dataRoot, "memory-store"),
        new WindowsProtectedPayload(Path.Combine(dataRoot, "security", "private-payload.v1.key")));

    private static string[] Values(string dataRoot) =>
        Store(dataRoot).List(new MemoryListRequest(null)).Records.Select(static record => record.Value).ToArray();

    // The Core keeps its journal open while it runs; it is read as a reader beside it.
    private static string Journal(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd();
    }

    private static JsonElement Body(FieldHttpResponse response) =>
        JsonDocument.Parse(response.Body).RootElement.Clone();

    private static JsonElement Item(JsonElement listed, string value) =>
        listed.GetProperty("items").EnumerateArray()
            .Single(item => item.GetProperty("value").GetString() == value);

    private static async Task SubmitAsync(MainWindowViewModel viewModel, string text)
    {
        viewModel.Draft = text;
        await viewModel.SubmitAsync(CancellationToken.None);
    }
}
