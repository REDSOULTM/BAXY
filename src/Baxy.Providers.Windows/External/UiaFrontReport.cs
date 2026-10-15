using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// What the UIA worker's front net saw while a command acted on a window behind (goal v3 point 0, r4a M1): the
/// target's family took the person's front (<c>frontChanged</c>), whether every time it was given back
/// (<c>frontRestored</c>), and how many returns failed (<c>frontReturnFailed</c>: the target kept the front and the
/// keyboard). The worker puts it on the command's answer and on its post-reads; the adapters copy it to the receipt,
/// where the mission's annoyance meter reads it. A front given back in milliseconds is still a change, never zero.
/// </summary>
internal readonly record struct UiaFrontReport(bool Restored, int ReturnFailed)
{
    /// <summary>The report on a worker answer; null when the front never moved under it.</summary>
    internal static UiaFrontReport? Read(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object
            || !root.TryGetProperty("frontChanged", out JsonElement changed) || changed.ValueKind != JsonValueKind.True)
            return null;
        bool restored = root.TryGetProperty("frontRestored", out JsonElement back) && back.ValueKind == JsonValueKind.True;
        int failed = root.TryGetProperty("frontReturnFailed", out JsonElement count) && count.ValueKind == JsonValueKind.Number
            && count.TryGetInt32(out int value)
                ? value
                : 0;
        return new UiaFrontReport(restored, failed);
    }

    /// <summary>The latest of two reports of the same watch: a later post-read has seen the tail too.</summary>
    internal static UiaFrontReport? Latest(UiaFrontReport? earlier, UiaFrontReport? later) => later ?? earlier;

    internal void Write(Utf8JsonWriter writer)
    {
        writer.WriteBoolean("frontChanged", true);
        writer.WriteBoolean("frontRestored", Restored);
        writer.WriteNumber("frontReturnFailed", ReturnFailed);
    }

    internal void Write(JsonObject node)
    {
        node["frontChanged"] = true;
        node["frontRestored"] = Restored;
        node["frontReturnFailed"] = ReturnFailed;
    }
}
