using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Network;

namespace Baxy.Core.Operations;

internal sealed class NetworkIpHandler(INetworkIpProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("network.ip.list");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        NetworkIpSnapshot? snapshot = await provider.ReadVerifiedAsync(cancellationToken)
            .ConfigureAwait(false);
        if (snapshot is null) return OperationOutcome.Failure("verification_failed");

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("count", snapshot.Addresses.Count);
            writer.WriteStartArray("addresses");
            foreach (string address in snapshot.Addresses) writer.WriteStringValue(address);
            writer.WriteEndArray();
            writer.WriteString("authority", "windows_active_unicast_addresses_secondread");
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}
