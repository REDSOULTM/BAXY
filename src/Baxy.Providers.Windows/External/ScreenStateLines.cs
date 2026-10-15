using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Encargo H2 (tandas redpc t3-c09: «Conectado», read alone under «Ethernet» in Configuración, was told as «los
/// auriculares están conectados»): an OCR line that only says a connection state (data screen_state_lines.v1.json) is
/// read with the line it sits under, the device it is the state of: «Ethernet: Conectado». A state with no line right
/// above it, aligned on the left, stays as it was read.
/// </summary>
internal static class ScreenStateLines
{
    private static readonly Lazy<HashSet<string>> States = new(Load);

    internal static IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> Grouped(
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> lines)
    {
        var grouped = new List<WindowsVisibleOcrLocator.LayoutLine>(lines.Count);
        foreach (WindowsVisibleOcrLocator.LayoutLine line in lines)
        {
            WindowsVisibleOcrLocator.LayoutLine? owner = IsState(line.Text)
                ? lines
                    .Where(above => !IsState(above.Text)
                        && above.Y < line.Y
                        && line.Y - (above.Y + above.Height) is var gap
                        && gap >= -0.3 * line.Height && gap <= line.Height
                        && Math.Abs(above.X - line.X) <= line.Height)
                    .OrderByDescending(above => above.Y)
                    .FirstOrDefault()
                : null;
            grouped.Add(owner is null ? line : line with { Text = $"{owner.Text}: {line.Text}" });
        }

        return grouped;
    }

    internal static bool IsState(string text) =>
        States.Value.Contains(WindowsVisibleOcrLocator.Fold(text).Trim(' ', '.', ',', ':', ';', '·', '-'));

    private static HashSet<string> Load()
    {
        using Stream stream = typeof(ScreenStateLines).Assembly.GetManifestResourceStream(
                "Baxy.Providers.Windows.ScreenStateLines.json")
            ?? throw new InvalidOperationException("screen_state_lines_missing");
        using JsonDocument document = JsonDocument.Parse(stream);
        return document.RootElement.GetProperty("states").EnumerateArray()
            .Select(item => item.GetString() ?? string.Empty)
            .Where(item => item.Length > 0)
            .ToHashSet(StringComparer.Ordinal);
    }
}
