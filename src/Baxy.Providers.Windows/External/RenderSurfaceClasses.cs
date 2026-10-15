using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// fable/cu-v3-worker-sin-nombres: the Win32 window classes of a Chromium host's render surface, read from data
/// (src/baxy_mind/data/render_surface_classes.v1.json, embedded). The UIA worker tells a render surface only by them;
/// <see cref="UiaWorkerHost"/> hands them over in its first «ping», so the worker's source names no surface class.
/// </summary>
internal static class RenderSurfaceClasses
{
    private static readonly Lazy<IReadOnlyList<string>> Data = new(Load);

    /// <summary>The classes in the data's order, trimmed, without empty or repeated entries.</summary>
    internal static IReadOnlyList<string> All => Data.Value;

    internal static IReadOnlyList<string> Parse(Stream stream)
    {
        using JsonDocument document = JsonDocument.Parse(stream);
        var classes = new List<string>();
        if (document.RootElement.TryGetProperty("classes", out JsonElement array)
            && array.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in array.EnumerateArray())
            {
                string? value = item.ValueKind == JsonValueKind.String ? item.GetString()?.Trim() : null;
                if (!string.IsNullOrEmpty(value) && !classes.Contains(value, StringComparer.Ordinal))
                {
                    classes.Add(value);
                }
            }
        }

        return classes;
    }

    private static IReadOnlyList<string> Load()
    {
        using Stream stream = typeof(RenderSurfaceClasses).Assembly.GetManifestResourceStream(
                "Baxy.Providers.Windows.RenderSurfaceClasses.json")
            ?? throw new InvalidOperationException("render_surface_classes_missing");
        return Parse(stream);
    }
}
