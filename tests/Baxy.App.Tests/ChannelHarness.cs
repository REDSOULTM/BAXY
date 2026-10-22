using System.Text.Json.Nodes;
using Baxy.App;

namespace Baxy.App.Tests;

/// <summary>The view's channel (FieldProductChannel) on a view model, with what it publishes kept for the test.</summary>
internal sealed class ChannelHarness : IAsyncDisposable
{
    private readonly FieldTelemetrySampler _telemetry = new(static () => null);

    internal ChannelHarness(MainWindowViewModel viewModel)
    {
        Channel = new FieldProductChannel(viewModel, Sink, _telemetry, CancellationToken.None);
    }

    internal FieldProductChannel Channel { get; }

    internal RecordingSink Sink { get; } = new();

    internal async Task<(int Status, JsonObject Body)> SendAsync(string method, string path, JsonObject? body = null)
    {
        FieldHttpResponse response = await Channel.HandleHttpAsync(method, path, body?.ToJsonString());
        return (response.Status, (JsonObject)JsonNode.Parse(response.Body)!);
    }

    public async ValueTask DisposeAsync()
    {
        await Channel.DisposeAsync();
        await _telemetry.DisposeAsync();
    }

    internal sealed class RecordingSink : IFieldEventSink
    {
        private readonly List<JsonObject> _events = [];

        internal IReadOnlyList<JsonObject> Events
        {
            get
            {
                lock (_events)
                {
                    return [.. _events];
                }
            }
        }

        /// <summary>The conversation's items as published (each one's last version).</summary>
        internal IReadOnlyList<JsonObject> Items =>
        [
            .. Events.Where(static e => (string?)e["type"] == "item")
                .Select(static e => (JsonObject)e["item"]!)
                .GroupBy(static i => (string?)i["id"])
                .Select(static g => g.Last()),
        ];

        public bool Publish(JsonObject eventData)
        {
            lock (_events)
            {
                _events.Add((JsonObject)eventData.DeepClone());
            }

            return true;
        }
    }
}
