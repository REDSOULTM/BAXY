using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Network;

namespace Baxy.Core.Operations;

internal sealed class NetworkPortHandler(INetworkPortProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("network.port.list");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        int limit = 50;
        if (invocation.Arguments.ValueKind != JsonValueKind.Object
            || (invocation.Arguments.TryGetProperty("limit", out JsonElement value)
                && (!value.TryGetInt32(out limit) || limit is < 1 or > 100)))
            return OperationOutcome.Failure("invalid_arguments");

        NetworkPortSnapshot snapshot = await provider.ReadVerifiedAsync(
            limit, cancellationToken).ConfigureAwait(false);
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("firstObservationCount", snapshot.FirstObservationCount);
            writer.WriteNumber("secondObservationCount", snapshot.SecondObservationCount);
            writer.WriteNumber("stableCount", snapshot.Endpoints.Count);
            writer.WriteStartArray("endpoints");
            foreach (NetworkPortEndpoint endpoint in snapshot.Endpoints)
            {
                writer.WriteStartObject();
                writer.WriteString("protocol", endpoint.Protocol);
                writer.WriteString("address", endpoint.Address);
                writer.WriteNumber("port", endpoint.Port);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}
