using System.Buffers;
using System.Globalization;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Core.Operations;

internal sealed class TimeStatusHandler(ITimeStatusProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("system.time");

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        TimeStatusSnapshot? snapshot = await provider.ReadVerifiedAsync(cancellationToken).ConfigureAwait(false);
        if (snapshot is null) return OperationOutcome.Failure("verification_failed");
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("utc", snapshot.UtcNow.ToString("O", CultureInfo.InvariantCulture));
            writer.WriteNumber("localUtcOffsetMinutes", snapshot.LocalUtcOffsetMinutes);
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}
