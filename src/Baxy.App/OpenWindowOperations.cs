using System.IO;
using System.Text.Json;

namespace Baxy.App;

/// <summary>
/// Ronda 19 «app-cerrada-se-abre»: the operations that place an application's open window, read from data
/// (src/baxy_mind/data/open_window_operations.v1.json, embedded). Only these make an absent window of an installed
/// application worth opening first (<see cref="MindPlanBoundary.OpenBeforeResolvingAgain"/>); any other act on a
/// window (minimize, close, focus) never opens what is not there.
/// </summary>
internal static class OpenWindowOperations
{
    private const string ResourceName = "Baxy.App.OpenWindowOperations.json";

    private static readonly Lazy<IReadOnlySet<string>> Placing = new(Load);

    private static readonly Lazy<PersonsFrameThresholds> Frame = new(LoadFrame);

    internal static bool PlacesAnOpenWindow(string operation) =>
        !string.IsNullOrEmpty(operation) && Placing.Value.Contains(operation);

    /// <summary>
    /// Ronda 22 (r18 t4-c19, revisión 1): how an application's titled frames narrow to the one an act is for, from
    /// data («persons_frame»): the tool-sized fraction of a topmost frame's work area, the comparable fraction, and
    /// the state each act leaves a window in.
    /// </summary>
    internal static PersonsFrameThresholds PersonsFrame => Frame.Value;

    private static PersonsFrameThresholds LoadFrame()
    {
        using Stream stream = typeof(OpenWindowOperations).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException("open_window_operations_missing");
        using JsonDocument document = JsonDocument.Parse(stream);
        JsonElement frame = document.RootElement.GetProperty("persons_frame");
        var endStates = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (JsonProperty act in frame.GetProperty("act_end_state").EnumerateObject())
        {
            endStates[act.Name] = act.Value.GetString()
                ?? throw new InvalidOperationException("open_window_operations_invalid");
        }

        return new PersonsFrameThresholds(
            frame.GetProperty("tool_sized_work_area_fraction").GetDouble(),
            frame.GetProperty("comparable_area_fraction").GetDouble(),
            endStates);
    }

    private static HashSet<string> Load()
    {
        using Stream stream = typeof(OpenWindowOperations).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException("open_window_operations_missing");
        using JsonDocument document = JsonDocument.Parse(stream);
        var operations = new HashSet<string>(StringComparer.Ordinal);
        if (document.RootElement.TryGetProperty("place_an_open_window", out JsonElement array)
            && array.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in array.EnumerateArray())
            {
                if (item.ValueKind == JsonValueKind.String && item.GetString() is { Length: > 0 } name)
                {
                    operations.Add(name);
                }
            }
        }

        return operations;
    }
}

internal sealed record PersonsFrameThresholds(
    double ToolSizedWorkAreaFraction,
    double ComparableAreaFraction,
    IReadOnlyDictionary<string, string> ActEndState);
