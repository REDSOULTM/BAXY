using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// When a turn of the native tool loop takes no more calls and the model answers in words from the results it has (the
/// mind's final continue: tool_choice none). The model still decides every move; this only bounds how long and how
/// often it may move, from what ran, never from what the person said.
/// <list type="bullet">
/// <item>Its moves: <see cref="MaximumModelCalls"/>.</item>
/// <item>Its time (FT/proveedores goal, E5): <see cref="Budget"/> from the turn's start. An app.open of a console app
/// waited 30 s per verification and the model retried it up to the move cap: 7.5 min with no answer.</item>
/// <item>A call that came back the same three times in the turn, in a row or not: the same operation with the same
/// arguments and the same result, its content, or for an effect that did not complete how it ended (e2e E022: the same
/// page fetched eight times, until the results overflowed the context and the turn ended with no answer; uso real
/// 2026-11-02: an unconfirmed navigation six times; feria 2026-10-27: a navigation and a new tab alternated 16 times in
/// 55 s, each breaking the other's run, until the move cap), unless a call not made before in the turn (another operation
/// or other arguments), or a read that saw a word no read saw before in it, came since its last time: a form
/// filled field by field, the same key between each typing, goes on, and so does a long page read by scrolling and
/// looking in turn.
/// Not twice: after two identical failures the model still changes course (e2e E011, base 0be0f9de9, all three seeds: two
/// calculator_window_not_found, then app.open and the sum); the branch that closed the turn at the second one lost that
/// case.</item>
/// </list>
/// </summary>
internal sealed class TurnClosing
{
    /// <summary>Model moves per turn.</summary>
    internal const int MaximumModelCalls = 15;

    /// <summary>The turn's time: longer than any turn of the practice e2e that passes (57 s at most, lote 3).</summary>
    internal static readonly TimeSpan Budget = TimeSpan.FromSeconds(90);

    /// <summary>
    /// The same call with the same result this many times in the turn, with no new call since its last time, closes it.
    /// </summary>
    internal const int RepeatsThatClose = 3;

    // Each call with its result: how many times it came, and how many new calls the turn had made at its last time.
    private readonly Dictionary<string, (int Times, int NewCalls)> _appearances = new(StringComparer.Ordinal);
    // The calls made in the turn (operation and arguments), and the words its reads saw: either growing is a new call.
    private readonly HashSet<string> _made = new(StringComparer.Ordinal);
    private readonly HashSet<string> _seen = new(StringComparer.Ordinal);

    /// <summary>
    /// The call number <paramref name="calls"/> of the turn came back, <paramref name="elapsed"/> after the turn started,
    /// with <paramref name="observation"/> (the result the model reads): whether the model answers now.
    /// </summary>
    internal bool AfterCall(int calls, TimeSpan elapsed, string operation, string arguments, string observation)
    {
        // Uso-108 (B4): vision or OCR of another capture of one image is the same call; the mind compares the same way.
        string made = string.Join('\n', operation, CaptureId.Replace(arguments, "capture_"));
        _made.Add(made);
        bool reads = Reads(operation);
        string content = Content(observation, effect: !reads);
        string call = string.Join('\n', made, Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(content))));
        if (reads)
        {
            // A read that saw a word no read of the turn saw before is new too (a look after each scroll of a long page);
            // other numbers or the same words in another order (a clock, a load, a list sorted by it) are not.
            _seen.UnionWith(Word.Matches(content).Select(static word => word.Value));
        }

        int news = _made.Count + _seen.Count;
        (int times, int newCallsBefore) = _appearances.GetValueOrDefault(call);
        bool stuck = times + 1 >= RepeatsThatClose && newCallsBefore == news;
        _appearances[call] = (times + 1, news);
        return calls >= MaximumModelCalls || elapsed >= Budget || stuck;
    }

    // Only a read's result is progress, by the catalog's risk: an effect's result may change at each repeat with nothing
    // gained (a new tab's tabCount in the feria loop).
    private static bool Reads(string operation) =>
        ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor)
        && descriptor.Risk == OperationRisks.ReadOnly;

    // Al máximo 7.7: the same result is the same content, status and error with it (three looks at a window still
    // loading, each with another view, are three results, not a repeat). How long the call took («…Ms»: durationMs,
    // elapsedMs, burstMs) is not part of it: the same console output each time in its own time is a repeat. The mind's
    // «same call» aid compares the same way (mind.py, _result_key).
    // Uso real 2026-11-02: an effect that did not complete is how it ended (its status, code and uncertainty): what its
    // result says it checked is the diagnosis of that same failure, another each time (an unconfirmed navigation opened
    // six times, each with another window change and address kind seen, until the turn's time ran out). The mind's aid
    // still compares the whole content.
    private static readonly string[] Ending = ["status", "error", "cause", "effectUncertain"];

    private static string Content(string observation, bool effect)
    {
        string content = observation;
        try
        {
            if (JsonNode.Parse(observation) is { } facts)
            {
                if (effect && facts is JsonObject ended && ended["status"] is JsonValue value
                    && value.TryGetValue(out string? status) && status != OperationStatuses.Completed)
                {
                    facts = new JsonObject(Ending.Where(ended.ContainsKey)
                        .Select(key => KeyValuePair.Create(key, ended[key]?.DeepClone())));
                }

                WithoutTimes(facts);
                content = facts.ToJsonString(Unescaped);
            }
        }
        catch (JsonException)
        {
        }

        return content;
    }

    // Letters as they are, not \u escapes, so that a read's words are whole (only compared, never shown).
    private static readonly JsonSerializerOptions Unescaped = new() { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

    private static readonly Regex Word = new(@"\p{L}+", RegexOptions.CultureInvariant);

    // Holdout v4 (the Steam library, «Biblioteca» 7 times): nor is a click's own count of its repeats
    // (unchangedInARow, WindowsVisibleControlAdapter) and the «next» that count brings, which differ on each repeat of
    // the same unchanged click; the mind compares the same way.
    private const string RepeatKey = "unchangedInARow";

    // Holdout v5 (en vivo, «maximiza Paint»: 13 window.resolve): nor a window's single-use handle
    // (WindowsWindowControlProvider.Issue), new at every read of the same window; the mind compares the same way.
    private static readonly Regex WindowHandle = new(@"\bwin_[0-9a-f]{32}\b", RegexOptions.CultureInvariant);

    // Uso-108 (B4): nor a capture's new id, its moment or how vision worded the same bytes (sha256, captureSha256 stay, and
    // tell a screen that changed): only the move cap or the time ended a loop of captures; the mind compares the same way.
    private static readonly Regex CaptureId = new(@"\bcapture_[0-9a-f]{32}\b", RegexOptions.CultureInvariant);
    private static readonly HashSet<string> CaptureMoment = new(StringComparer.Ordinal)
    {
        "createdAtUtc", "description",
    };

    private static void WithoutTimes(JsonNode node)
    {
        if (node is JsonObject facts)
        {
            bool repeat = facts.ContainsKey(RepeatKey);
            bool captured = facts.ContainsKey("captureId");
            foreach (string key in facts.Select(static pair => pair.Key).ToArray())
            {
                // A result that holds nothing but the count is the same as the first one, which had none.
                if (key.EndsWith("Ms", StringComparison.Ordinal) || key == RepeatKey || (repeat && key == "next")
                    || (captured && CaptureMoment.Contains(key)) || key is "captureStartedAtUtc" or "captureCompletedAtUtc"
                    || (facts[key] is JsonObject inner && inner.ContainsKey(RepeatKey)
                        && inner.All(static pair => pair.Key is RepeatKey or "next")))
                {
                    facts.Remove(key);
                }
                else if (facts[key] is JsonValue value && value.TryGetValue(out string? text))
                {
                    facts[key] = CaptureId.Replace(WindowHandle.Replace(text, "win_"), "capture_");
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
