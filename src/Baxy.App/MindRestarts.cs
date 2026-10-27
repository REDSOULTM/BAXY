using System.Globalization;
using System.IO;
using System.Text.Json;

namespace Baxy.App;

/// <summary>
/// Feria 2026-10-27: the mind started anew three times in a morning and nothing outside development said why (the
/// shell's trace exists only there); it took the Windows event log to learn the App itself had been opened again. Each
/// mind that ends or starts anew leaves one line in the profile (<c>&lt;datos&gt;/diagnostics/mind_restarts.v1.jsonl</c>,
/// 256 KB and one archive): when, the classified cause (<see cref="MindLoss.Cause"/>, the App's start or exit included),
/// the type of the request that failed, the exit code (the mind's; the App's on its exit line) and how long the mind (or
/// the App) had run. Never what the person said nor a request's arguments. An App that ended without its exit line ended without exiting.
/// </summary>
internal static class MindRestarts
{
    internal const string FileName = "mind_restarts.v1.jsonl";
    internal const string UnrecordedStage = "process.restart.unrecorded";
    private const long MaximumBytes = 256 * 1024;
    private static readonly object Gate = new();

    /// <summary>Records one; <paramref name="directory"/>: where (tests), else the profile's.</summary>
    internal static void Record(MindLoss loss, TimeSpan running, string? directory = null)
    {
        try
        {
            string folder = directory ?? Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "diagnostics");
            var line = new Dictionary<string, object?>
            {
                ["utc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                ["cause"] = loss.Cause,
                ["request"] = loss.Request,
                ["exitCode"] = loss.ExitCode,
                ["runningSeconds"] = Math.Round(running.TotalSeconds, 1),
            };
            lock (Gate)
            {
                Directory.CreateDirectory(folder);
                new BoundedJsonlFile(Path.Combine(folder, FileName), MaximumBytes).AppendLine(JsonSerializer.Serialize(line));
            }
        }
        catch (Exception recordFailure) when (recordFailure is IOException or UnauthorizedAccessException
            or InvalidOperationException or ArgumentException or NotSupportedException)
        {
            // Recording it never adds a failure of its own; development's trace still tells the line was lost.
            ShellTraceSink.Record(ShellTraceScopes.Startup, "process", UnrecordedStage,
                $"{loss.Cause}.{recordFailure.GetType().Name}".ToLowerInvariant());
        }
    }
}
