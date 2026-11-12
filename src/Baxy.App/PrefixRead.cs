using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// MOD1 D5 (ABIERTOS_VIVO D5, 2026-11-09): another context is another prompt cache for BAXY's own model (the kept prefix is
/// keyed by the server's arguments, llm_server.prefix_key), so after the change the model reads its instructions and tools
/// whole again: 746-754 s on an RX 7600 on Vulkan (AMD2 §5), 167.5 s on a cold start there (uso 84), and nothing said so
/// before the person changed it. What this PC took the last time it read them whole is kept here
/// (&lt;data&gt;\prefix-read.v1.json), measured from the mind's own progress lines of a start (MindModelReading), so
/// Settings → Model → Context says it before the change. A start that restored its kept prefix reads nothing and leaves
/// the last measure as it was.
/// </summary>
internal sealed class PrefixRead
{
    internal const string FileName = "prefix-read.v1.json";

    private readonly string _path;
    private readonly object _sync = new();
    // The first and the last progress line of the start under way: the tokens read so far, the prefix's, and when.
    private (long Done, long Total, TimeSpan At)? _first;
    private (long Done, long Total, TimeSpan At)? _last;

    internal PrefixRead(string dataRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        _path = Path.Combine(dataRoot, FileName);
    }

    /// <summary>A start of the mind begins: nothing of it was read yet.</summary>
    internal void Begin()
    {
        lock (_sync)
        {
            _first = _last = null;
        }
    }

    /// <summary>The model advanced through its prefix: <paramref name="done"/> of <paramref name="total"/> tokens,
    /// <paramref name="at"/> on a clock that only moves forward.</summary>
    internal void Saw(long done, long total, TimeSpan at)
    {
        lock (_sync)
        {
            _first ??= (done, total, at);
            _last = (done, total, at);
        }
    }

    /// <summary>
    /// The start ended. With <paramref name="ownModel"/> (it came up on BAXY's own model), what its lines measured is
    /// kept as this PC's read of the whole prefix: the time between the first and the last, scaled from the tokens read
    /// between them to the prefix's. Only a start that read half the prefix or more counts: a restored prefix, or one
    /// read from where it differed, measures no whole read. A start that failed, or another model's, is not this PC's
    /// read of BAXY's own model.
    /// </summary>
    internal void Ended(bool ownModel)
    {
        lock (_sync)
        {
            (long Done, long Total, TimeSpan At)? first = _first;
            (long Done, long Total, TimeSpan At)? last = _last;
            _first = _last = null;
            if (!ownModel || first is not { } began || last is not { } ended || ended.Total <= 0 || ended.Total > int.MaxValue)
            {
                return;
            }

            long read = ended.Done - began.Done;
            TimeSpan took = ended.At - began.At;
            if (read * 2 < ended.Total || took <= TimeSpan.Zero)
            {
                return;
            }

            double seconds = Math.Ceiling(took.TotalSeconds * ended.Total / read);
            if (seconds > int.MaxValue)
            {
                return;
            }

            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
                string temporary = _path + ".tmp";
                File.WriteAllText(temporary, new JsonObject { ["tokens"] = (int)ended.Total, ["seconds"] = (int)seconds }.ToJsonString());
                File.Move(temporary, _path, overwrite: true);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // Not kept: Settings says the wait without this PC's figure, as before any read.
            }
        }
    }

    /// <summary>The last whole read kept: the prefix's tokens and the seconds it took; null before any, or unreadable.</summary>
    internal (int Tokens, int Seconds)? Last()
    {
        lock (_sync)
        {
            try
            {
                return File.Exists(_path)
                    && JsonNode.Parse(File.ReadAllText(_path)) is JsonObject kept
                    && kept["tokens"] is JsonValue tokens && tokens.TryGetValue(out int prefix) && prefix > 0
                    && kept["seconds"] is JsonValue seconds && seconds.TryGetValue(out int took) && took > 0
                        ? (prefix, took)
                        : null;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
            {
                return null;
            }
        }
    }

    /// <summary>The view's state of it (GET /settings/local-context, <c>lastRead</c>), or null with none.</summary>
    internal JsonObject? Json() => Last() is { } last
        ? new JsonObject { ["tokens"] = last.Tokens, ["seconds"] = last.Seconds }
        : null;
}
