using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

/// <summary>
/// When a turn of the native tool loop takes no more calls and the model answers in words from the results it has (the
/// mind's final continue: tool_choice none). The model still decides every move; this only bounds how long and how
/// often it may move, from what ran, never from what the person said.
/// <list type="bullet">
/// <item>Its moves: <see cref="MaximumModelCalls"/>.</item>
/// <item>Its time (FT/proveedores goal, E5): <see cref="Budget"/> from the turn's start. An app.open of a console app
/// waited 30 s per verification and the model retried it up to the move cap: 7.5 min with no answer.</item>
/// <item>A call that came back the same three times in a row: the same operation with the same arguments and the same
/// result, its content (e2e E022: the same page fetched eight times, until the results overflowed the context and the
/// turn ended with no answer). Not twice: after two identical failures the model still changes course (e2e E011, base 0be0f9de9,
/// all three seeds: two calculator_window_not_found, then app.open and the sum); the branch that closed the turn at the
/// second one lost that case.</item>
/// </list>
/// </summary>
internal sealed class TurnClosing
{
    /// <summary>Model moves per turn.</summary>
    internal const int MaximumModelCalls = 15;

    /// <summary>The turn's time: longer than any turn of the practice e2e that passes (57 s at most, lote 3).</summary>
    internal static readonly TimeSpan Budget = TimeSpan.FromSeconds(90);

    /// <summary>The same call with the same result this many times in a row closes the turn.</summary>
    internal const int RepeatsThatClose = 3;

    private string? _last;
    private int _same;

    /// <summary>
    /// The call number <paramref name="calls"/> of the turn came back, <paramref name="elapsed"/> after the turn started,
    /// with <paramref name="observation"/> (the result the model reads): whether the model answers now.
    /// </summary>
    internal bool AfterCall(int calls, TimeSpan elapsed, string operation, string arguments, string observation)
    {
        string call = string.Join('\n', operation, arguments, ResultHash(observation));
        _same = call == _last ? _same + 1 : 1;
        _last = call;
        return calls >= MaximumModelCalls || elapsed >= Budget || _same >= RepeatsThatClose;
    }

    // Al máximo 7.7: the same result is the same content, status and error with it (three looks at a window still
    // loading, each with another view, are three results, not a repeat). How long the call took («…Ms»: durationMs,
    // elapsedMs, burstMs) is not part of it: the same console output each time in its own time is a repeat. The mind's
    // «same call» aid compares the same way (mind.py, _result_key).
    private static string ResultHash(string observation)
    {
        string content = observation;
        try
        {
            if (JsonNode.Parse(observation) is { } facts)
            {
                WithoutTimes(facts);
                content = facts.ToJsonString();
            }
        }
        catch (JsonException)
        {
        }

        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(content)));
    }

    // Holdout v4 (the Steam library, «Biblioteca» 7 times): nor is a click's own count of its repeats
    // (unchangedInARow, WindowsVisibleControlAdapter) and the «next» that count brings, which differ on each repeat of
    // the same unchanged click; the mind compares the same way.
    private const string RepeatKey = "unchangedInARow";

    // Holdout v5 (en vivo, «maximiza Paint»: 13 window.resolve): nor a window's single-use handle
    // (WindowsWindowControlProvider.Issue), new at every read of the same window; the mind compares the same way.
    private static readonly Regex WindowHandle = new(@"\bwin_[0-9a-f]{32}\b", RegexOptions.CultureInvariant);

    private static void WithoutTimes(JsonNode node)
    {
        if (node is JsonObject facts)
        {
            bool repeat = facts.ContainsKey(RepeatKey);
            foreach (string key in facts.Select(static pair => pair.Key).ToArray())
            {
                // A result that holds nothing but the count is the same as the first one, which had none.
                if (key.EndsWith("Ms", StringComparison.Ordinal) || key == RepeatKey || (repeat && key == "next")
                    || (facts[key] is JsonObject inner && inner.ContainsKey(RepeatKey)
                        && inner.All(static pair => pair.Key is RepeatKey or "next")))
                {
                    facts.Remove(key);
                }
                else if (facts[key] is JsonValue value && value.TryGetValue(out string? text))
                {
                    facts[key] = WindowHandle.Replace(text, "win_");
                }
                else if (facts[key] is { } child)
                {
                    WithoutTimes(child);
                }
            }
        }
        else if (node is JsonArray items)
        {
            foreach (JsonNode? item in items)
            {
                if (item is not null)
                {
                    WithoutTimes(item);
                }
            }
        }
    }
}
