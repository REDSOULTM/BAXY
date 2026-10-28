using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;

namespace Baxy.GuardOracle;

/// <summary>
/// The App's shape guards, as the Python decision benches can ask them (scripts/renew/bench_decision.py and
/// bench_sesion_larga.py judge the model's first call and never saw a guard send it back). It runs the App's own
/// NetworkEgress, SaidFolders, SaidApplication and SaidVerbs, in NativeTurnLoop's order, and re-implements none of their
/// rules: one JSON object per request, one per answer.
/// <list type="bullet">
/// <item><c>{"heard": words, "answering": false}</c>: the person's words open a turn (NativeTurnLoop.RunAsync).</item>
/// <item><c>{"asked": true}</c>: the model ended the turn with a question (NativeTurnLoop.DriveAsync, «question»).</item>
/// <item><c>{"call": op, "arguments": {…}}</c>: <c>{"refused": observation}</c>, the result the model reads, or
/// <c>{"operation", "arguments", "note", "held"}</c>, the call as it would run (NativeTurnLoop.ExecuteAsync);
/// <c>held</c>, NetworkEgress.Holds' cause when the App holds it for the person's «sí» (null: it runs).</item>
/// <item><c>{"ran": op, "arguments": {…}, "observation": json}</c>: a call's result (SaidFolders.Ran,
/// NetworkEgress.Observed); <c>{"observation": json}</c>, that result with the said note of the call as the model reads
/// it (NativeTurnLoop.WithSaid).</item>
/// <item><c>{"reset": true}</c>: a new session (NativeTurnLoop.Reset).</item>
/// </list>
/// Not here: the owner's switches in Settings (Host.Refuse), the kernel's confirmation and argument checks, and
/// heartbeats (a heartbeat's call skips NetworkEgress.Unsaid).
/// </summary>
internal sealed class GuardOracle
{
    private readonly NetworkEgress _egress = new();
    private readonly SaidFolders _said;
    private readonly SaidApplication _saidApp = new();
    private readonly SaidVerbs _saidVerbs = new();
    // The said note of the last call that goes, by its key, for its result (ran).
    private (string Key, string Note)? _told;

    /// <param name="known">The person's known folders by label (SaidFolders); null: this PC's own.</param>
    internal GuardOracle(Func<string, string?>? known = null) => _said = new SaidFolders(known);

    /// <summary>One request line; its answer line.</summary>
    internal string Answer(string line)
    {
        JsonObject request;
        try
        {
            request = JsonNode.Parse(line) as JsonObject ?? throw new JsonException("not an object");
        }
        catch (JsonException invalid)
        {
            return new JsonObject { ["error"] = "invalid_request: " + invalid.Message }.ToJsonString(SaidFolders.AsWritten);
        }

        if (request["call"] is JsonValue call)
        {
            return Call((string?)call ?? string.Empty, Arguments(request)).ToJsonString(SaidFolders.AsWritten);
        }

        if (request["heard"] is JsonValue heard)
        {
            Heard((string?)heard ?? string.Empty, request["answering"]?.GetValueKind() == JsonValueKind.True);
        }
        else if (request["asked"] is not null)
        {
            _egress.Asked();
        }
        else if (request["ran"] is JsonValue ran)
        {
            // NativeTurnLoop.SendAsync and DriveAsync: SaidFolders.Ran, the said note into the body, then Observed.
            string observation = (string?)request["observation"] ?? "{}";
            _said.Ran((string?)ran ?? string.Empty, Arguments(request), NativeTurnLoop.StatusOf(observation));
            if (_told is { } fact)
            {
                observation = NativeTurnLoop.WithSaid(observation, fact.Key, fact.Note);
            }

            _told = null;
            _egress.Observed((string?)ran ?? string.Empty, observation);
            return new JsonObject { ["observation"] = observation }.ToJsonString(SaidFolders.AsWritten);
        }
        else if (request["reset"] is not null)
        {
            // NativeTurnLoop.Reset.
            _egress.Reset();
            _said.Clear();
            _saidApp.Clear();
            _saidVerbs.Clear();
        }
        else
        {
            return new JsonObject { ["error"] = "unknown_request" }.ToJsonString(SaidFolders.AsWritten);
        }

        return "{}";
    }

    // NativeTurnLoop.RunAsync: the person's words, or their words answering the call that waits for their «sí».
    private void Heard(string text, bool answering)
    {
        _egress.Heard(text, answering);
        if (answering)
        {
            _said.Answered(text);
            _saidApp.Answered(text);
            _saidVerbs.Answered(text);
        }
        else
        {
            _said.Heard(text);
            _saidApp.Heard(text);
            _saidVerbs.Heard(text);
        }
    }

    // NativeTurnLoop.ExecuteAsync, from the catalog's lookup to SaidVerbs, in its order: what it refuses is the
    // observation it would record, what it rewrites is the call it would prepare. Keep the two in step.
    private JsonObject Call(string operation, JsonObject arguments)
    {
        if (operation == MindStep.ConfirmationAnswer || NativeTurnLoop.IsConversation(operation))
        {
            return Goes(operation, arguments, note: null);
        }

        if (!ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor) || descriptor is null)
        {
            return Refused(NativeTurnLoop.Observation("rejected", "unknown_operation"));
        }

        if (_egress.Unsaid(operation, arguments) is { } unsaid)
        {
            return Refused(NativeTurnLoop.Observation("rejected", unsaid.Code, new JsonObject { ["next"] = unsaid.Next }));
        }

        _told = null;
        (string Key, string Note)? said = null;
        if (_said.Rule(operation, descriptor, arguments) is { } ruling)
        {
            if (ruling.Refusal is { } leftOut)
            {
                return Refused(leftOut.ToJsonString(SaidFolders.AsWritten));
            }

            if (ruling.Operation is { } instead && ProductCatalog.TryGet(instead, out ProductOperationDescriptor? other)
                && other is not null)
            {
                operation = instead;
            }

            arguments = ruling.Arguments;
            said = ruling.Note is { } folder ? ("saidFolder", folder) : null;
        }
        else if (_saidApp.Rule(operation, arguments) is { } owner)
        {
            arguments = owner.Arguments;
            said = (SaidApplication.NoteKey, owner.Note);
        }

        if (_saidVerbs.Rule(operation, arguments, (named, given) =>
                ProductCatalog.TryGet(named, out ProductOperationDescriptor? called) && called is not null
                    ? _said.FileThere(named, called, given) : null) is { } verb)
        {
            arguments = verb.Arguments;
            said = said is { } before ? (before.Key, before.Note + "; " + verb.Note) : (SaidVerbs.NoteKey, verb.Note);
        }

        _told = said;
        return Goes(operation, arguments, said?.Note, _egress.Holds(operation, arguments));
    }

    private static JsonObject Refused(string observation) => new() { ["refused"] = observation };

    private static JsonObject Goes(string operation, JsonObject arguments, string? note, string? held = null) => new()
    {
        ["operation"] = operation,
        ["arguments"] = arguments.DeepClone(),
        ["note"] = note,
        ["held"] = held,
    };

    private static JsonObject Arguments(JsonObject request) =>
        request["arguments"] is JsonObject given ? (JsonObject)given.DeepClone() : [];
}
