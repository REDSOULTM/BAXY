using System.Buffers;
using System.Globalization;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Core.Operations;

internal sealed class TimeStatusHandler(ITimeStatusProvider provider, IPlaceTimeZoneResolver places) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("system.time");

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        // With a named place or zone, the reading also carries that zone's offset
        // at the same observed instant; the mind does the clock arithmetic.
        PlaceTimeZone? place = null;
        if (ReadPlace(invocation.Arguments) is { } named)
        {
            PlaceTimeZoneReading reading = await places.ResolveAsync(named, cancellationToken).ConfigureAwait(false);
            if (reading.Place is null)
                return OperationOutcome.Failure(reading.ErrorCode ?? "time_place_not_found");
            place = reading.Place;
        }

        TimeStatusSnapshot? snapshot = await provider.ReadVerifiedAsync(cancellationToken).ConfigureAwait(false);
        if (snapshot is null) return OperationOutcome.Failure("verification_failed");
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("utc", snapshot.UtcNow.ToString("O", CultureInfo.InvariantCulture));
            writer.WriteNumber("localUtcOffsetMinutes", snapshot.LocalUtcOffsetMinutes);
            if (place is not null)
            {
                writer.WriteStartObject("place");
                writer.WriteString("name", place.Name);
                writer.WriteString("country", place.Country);
                writer.WriteString("timeZone", place.Zone.Id);
                writer.WriteNumber(
                    "utcOffsetMinutes",
                    checked((int)place.Zone.GetUtcOffset(snapshot.UtcNow).TotalMinutes));
                writer.WriteString("authority", place.Authority);
                writer.WriteEndObject();
            }
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }

    private static string? ReadPlace(JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("place", out JsonElement value)
        && value.ValueKind == JsonValueKind.String
        && value.GetString() is { } text
        && !string.IsNullOrWhiteSpace(text)
            ? text.Trim()
            : null;
}
