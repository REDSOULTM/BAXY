using System.Globalization;
using System.IO;
using System.Text.Json;

namespace Baxy.App;

/// <summary>
/// Feria 2026-10-27: the mind was relaunched twice in a morning and nothing said why (the shell's trace exists only in
/// development). Each relaunch the App decides leaves one line in the profile
/// (<c>&lt;datos&gt;/diagnostics/mind_relaunch.v1.jsonl</c>, bounded as <c>unhandled.v1.jsonl</c>): when, the classified
/// cause, the type of the request that failed, the mind's exit code and how long it had been running since its start.
/// Never what the person said nor a request's arguments.
/// </summary>
internal static class MindRelaunches
{
    internal const string FileName = "mind_relaunch.v1.jsonl";
    private const long MaximumBytes = 256 * 1024;
    private static readonly object Gate = new();

    /// <summary>Records one relaunch; <paramref name="directory"/>: where (tests), else the profile's.</summary>
    internal static void Record(MindLoss loss, TimeSpan sinceStart, string? directory = null)
    {
        ArgumentNullException.ThrowIfNull(loss);
        try
        {
            string folder = directory ?? Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "diagnostics");
            var line = new Dictionary<string, object?>
            {
                ["utc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                ["cause"] = loss.Cause,
                ["request"] = loss.Request,
                ["exitCode"] = loss.ExitCode,
                ["sinceStartSeconds"] = Math.Round(sinceStart.TotalSeconds, 1),
            };
            lock (Gate)
            {
                Directory.CreateDirectory(folder);
                new BoundedJsonlFile(Path.Combine(folder, FileName), MaximumBytes).AppendLine(JsonSerializer.Serialize(line));
            }
        }
        catch (Exception recordFailure) when (recordFailure is IOException or UnauthorizedAccessException
            or InvalidOperationException or ArgumentException)
        {
            // Recording it never adds a failure of its own.
        }
    }
}
