using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Baxy.App;

internal sealed class PresenceStatusStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        WriteIndented = false,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };

    private readonly string _statusPath;
    private readonly BoundedJsonlFile _samples;

    internal PresenceStatusStore(
        string directory,
        long maximumSampleBytes = BoundedJsonlFile.DefaultMaximumBytes)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(directory);
        Directory.CreateDirectory(directory);
        _statusPath = Path.Combine(directory, "status.v1.json");
        _samples = new BoundedJsonlFile(
            Path.Combine(directory, "idle-samples.v1.jsonl"),
            maximumSampleBytes);
    }

    internal static PresenceStatusStore CreateDefault() =>
        new(Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "presence"));

    internal void WriteStatus(PresenceStatusDocument document)
    {
        ArgumentNullException.ThrowIfNull(document);
        string payload = JsonSerializer.Serialize(document, JsonOptions);
        string temporary = _statusPath + ".tmp";
        File.WriteAllText(temporary, payload + Environment.NewLine);
        if (File.Exists(_statusPath))
        {
            AtomicFileReplacement.Replace(temporary, _statusPath);
        }
        else
        {
            File.Move(temporary, _statusPath);
        }
    }

    internal void AppendSample(PresenceIdleSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        var payload = new Dictionary<string, object?>
        {
            ["schema"] = PresenceLimits.SampleSchema,
            ["utc"] = snapshot.Utc.ToString("O", CultureInfo.InvariantCulture),
            ["ready"] = snapshot.Ready,
            ["input_enabled"] = snapshot.InputEnabled,
            ["listening"] = snapshot.Listening,
            ["first_wake_utc"] = snapshot.FirstWakeUtc?.ToString("O", CultureInfo.InvariantCulture),
            ["terminal"] = snapshot.Terminal,
            ["working_set_bytes"] = PresenceIdleSampler.TotalWorkingSet(snapshot),
            ["handles"] = PresenceIdleSampler.TotalHandles(snapshot),
            ["vram_bytes"] = PresenceIdleSampler.TotalVram(snapshot),
            ["cpu_seconds"] = PresenceIdleSampler.TotalCpuSeconds(snapshot),
            ["processes"] = snapshot.Processes,
        };
        string line = JsonSerializer.Serialize(payload, JsonOptions);
        _samples.AppendLine(line);
    }
}
