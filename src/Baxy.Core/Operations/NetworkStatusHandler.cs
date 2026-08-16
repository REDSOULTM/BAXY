using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Network;

namespace Baxy.Core.Operations;

internal sealed class NetworkStatusHandler(INetworkStatusProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("network.status");

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        NetworkStatusSnapshot? snapshot = await provider.ReadVerifiedAsync(cancellationToken).ConfigureAwait(false);
        if (snapshot is null) return OperationOutcome.Failure("verification_failed");
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("online", snapshot.Online);
            writer.WriteNumber("connectedInterfaceCount", snapshot.ConnectedInterfaceCount);
            writer.WritePropertyName("interfaceTypes");
            writer.WriteStartArray();
            foreach (string type in snapshot.InterfaceTypes) writer.WriteStringValue(type);
            writer.WriteEndArray();
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}
