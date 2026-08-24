using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class MemoryPanelBridgeTests
{
    private const string Selector = "goal10.color";
    private const string FirstValue = "verde-panel";
    private const string EditedValue = "azul-panel";

    [Test]
    public async Task PanelSaveEditDeleteRereadsTheSameStore()
    {
        using var temporary = new TemporaryDirectory();
        string? previous = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.That(viewModel.IsReady, Is.True);

            FieldHttpResponse initiallyDisabled = await viewModel.MemoryPanel.HandleAsync(
                "GET",
                "/memory",
                body: null,
                CancellationToken.None);
            Assert.That(initiallyDisabled.Status, Is.EqualTo(200));
            Assert.That(ItemValue(initiallyDisabled, Selector), Is.Null);

            FieldHttpResponse created = await viewModel.MemoryPanel.HandleAsync(
                "POST",
                "/memory",
                new JsonObject { ["key"] = Selector, ["value"] = FirstValue }.ToJsonString(),
                CancellationToken.None);
            Assert.That(created.Status, Is.EqualTo(200));
            Assert.That(ItemValue(created, Selector), Is.EqualTo(FirstValue));
            Assert.That(StoreValue(temporary.Path, Selector), Is.EqualTo(FirstValue));

            FieldHttpResponse listed = await viewModel.MemoryPanel.HandleAsync(
                "GET",
                "/memory",
                body: null,
                CancellationToken.None);
            Assert.That(ItemValue(listed, Selector), Is.EqualTo(FirstValue));

            FieldHttpResponse edited = await viewModel.MemoryPanel.HandleAsync(
                "POST",
                "/memory",
                new JsonObject { ["key"] = Selector, ["value"] = EditedValue }.ToJsonString(),
                CancellationToken.None);
            Assert.That(ItemValue(edited, Selector), Is.EqualTo(EditedValue));
            Assert.That(StoreValue(temporary.Path, Selector), Is.EqualTo(EditedValue));

            FieldHttpResponse deleted = await viewModel.MemoryPanel.HandleAsync(
                "DELETE",
                "/memory/" + Uri.EscapeDataString(Selector),
                body: null,
                CancellationToken.None);
            Assert.That(ItemValue(deleted, Selector), Is.Null);
            Assert.That(StoreValue(temporary.Path, Selector), Is.Null);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previous);
        }
    }

    private static string? ItemValue(FieldHttpResponse response, string key)
    {
        using JsonDocument document = JsonDocument.Parse(response.Body);
        if (!document.RootElement.TryGetProperty("items", out JsonElement items)
            || items.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        foreach (JsonElement item in items.EnumerateArray())
        {
            string current = item.TryGetProperty("key", out JsonElement name)
                ? name.GetString() ?? string.Empty
                : string.Empty;
            if (string.Equals(current, key, StringComparison.OrdinalIgnoreCase))
            {
                return item.TryGetProperty("value", out JsonElement value)
                    ? value.GetString()
                    : null;
            }
        }

        return null;
    }

    private static string? StoreValue(string dataRoot, string selector)
    {
        var store = new LocalMemoryStore(
            Path.Combine(dataRoot, "memory-store"),
            new WindowsProtectedPayload(
                Path.Combine(dataRoot, "security", "private-payload.v1.key")));
        MemoryRecord[] records = store.Recall(new MemoryRecallRequest(selector)).Records
            .ToArray();
        return records.Length == 0 ? null : records[0].Value;
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal TemporaryDirectory()
        {
            Path = PrivateDataRootTestSupport.NewPath("memory-panel");
            Directory.CreateDirectory(Path);
        }

        internal string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
