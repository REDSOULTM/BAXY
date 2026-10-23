using System.Globalization;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// The conversation as the view shows it (design v4): the person's words, BAXY's replies with a step per call under
/// them, the Sí/No cards and the shell's own lines. The host keeps it, so a view that reconnects or a session that is
/// opened again shows exactly what happened; every change returns the item the view must add or replace.
/// The calls of a turn gather under the reply that follows them (a turn's steps arrive before its words).
/// </summary>
internal sealed class FieldTranscript
{
    internal const int MaximumItems = 400;

    private readonly List<JsonObject> _items = [];
    private JsonObject? _open;
    private long _sequence;

    internal IReadOnlyList<JsonObject> Items => _items;

    /// <summary>The turn the open reply belongs to (the face's walk), or null between turns.</summary>
    internal string? Turn { get; private set; }

    internal int Requests => _items.Count(static i => (string?)i["who"] == "you");

    internal JsonArray Snapshot() => new([.. _items.Select(static i => (JsonNode)i.DeepClone())]);

    internal void Replace(JsonArray? items)
    {
        _items.Clear();
        _open = null;
        Turn = null;
        foreach (JsonNode? item in items ?? [])
        {
            if (item is JsonObject value)
            {
                var kept = (JsonObject)value.DeepClone();
                // A card kept pending (the session was saved while it waited) waits for nobody now: a new or opened
                // session drops what was pending (NativeTurnLoop.Reset), so it is never shown with a live Sí / No.
                if ((string?)kept["who"] == "card" && (string?)kept["status"] == "pending")
                {
                    kept["status"] = "dropped";
                }

                _items.Add(kept);
            }
        }

        _sequence = _items.Count;
    }

    internal JsonObject You(string text)
    {
        _open = null;
        Turn = NextId("t");
        return Clone(Store(new JsonObject { ["who"] = "you", ["id"] = NextId("y"), ["text"] = text, ["ts"] = Now() }));
    }

    internal JsonObject System(string text) =>
        Clone(Store(new JsonObject { ["who"] = "sys", ["id"] = NextId("s"), ["text"] = text, ["ts"] = Now() }));

    /// <summary>A call started or finished: the open reply gets (or replaces) that step.</summary>
    internal JsonObject Step(JsonObject step)
    {
        if (_open is null)
        {
            Turn ??= NextId("t");
            _open = Store(Reply(string.Empty));
        }

        var steps = (JsonArray)_open["steps"]!;
        string id = (string)step["id"]!;
        int index = steps.ToList().FindIndex(s => (string?)s?["id"] == id);
        if (index >= 0)
        {
            steps[index] = step.DeepClone();
        }
        else
        {
            steps.Add(step.DeepClone());
        }

        string[] nets = [.. steps.Select(static s => (string?)s?["net"]).Where(static n => n is not null).Distinct()!];
        _open["net"] = nets.Length == 0 ? null : string.Join(" · ", nets);
        return Clone(_open);
    }

    /// <summary>A started call that is no step of its own (held for the person's «sí»: the card shows it) leaves the
    /// open reply; null when there was nothing to remove.</summary>
    internal JsonObject? Drop(string stepId)
    {
        if (_open?["steps"] is not JsonArray steps
            || steps.FirstOrDefault(s => (string?)s?["id"] == stepId) is not { } step)
        {
            return null;
        }

        steps.Remove(step);
        return Clone(_open);
    }

    /// <summary>BAXY's words: they complete the open reply (its steps came first) and close the turn's reply.</summary>
    internal JsonObject Words(string text, string? silent)
    {
        JsonObject item = _open is { } open && string.IsNullOrEmpty((string?)open["text"]) ? open : Store(Reply(string.Empty));
        item["text"] = text;
        item["ts"] = Now();
        if (silent is not null)
        {
            item["silent"] = silent;
        }

        _open = null;
        return Clone(item);
    }

    internal JsonObject Card(JsonObject card)
    {
        _open = null;
        return Clone(Store(Clone(card)));
    }

    /// <summary>A card's end: answered (yes or no), expired, or dropped because the person asked something else.</summary>
    internal JsonObject? Resolve(string status, string? via)
    {
        JsonObject? card = _items.LastOrDefault(static i => (string?)i["who"] == "card" && (string?)i["status"] == "pending");
        if (card is null)
        {
            return null;
        }

        card["status"] = status;
        card["via"] = via;
        return Clone(card);
    }

    /// <summary>The card <paramref name="id"/>, still pending, was also sent as a Windows notification.</summary>
    internal JsonObject? Notified(string id)
    {
        JsonObject? card = _items.LastOrDefault(i => (string?)i["who"] == "card" && (string?)i["id"] == id
            && (string?)i["status"] == "pending");
        if (card is null)
        {
            return null;
        }

        card["notified"] = true;
        return Clone(card);
    }

    internal string NextId(string prefix) =>
        prefix + Interlocked.Increment(ref _sequence).ToString(CultureInfo.InvariantCulture) + "-"
        + Guid.NewGuid().ToString("N")[..6];

    private JsonObject Reply(string text) => new()
    {
        ["who"] = "baxy",
        ["id"] = NextId("b"),
        ["text"] = text,
        ["ts"] = Now(),
        ["steps"] = new JsonArray(),
        ["net"] = null,
        ["silent"] = null,
    };

    private JsonObject Store(JsonObject item)
    {
        _items.Add(item);
        if (_items.Count > MaximumItems)
        {
            _items.RemoveRange(0, _items.Count - MaximumItems);
        }

        return item;
    }

    private static JsonObject Clone(JsonObject item) => (JsonObject)item.DeepClone();

    private static string Now() => DateTimeOffset.Now.ToString("HH:mm", CultureInfo.InvariantCulture);
}
