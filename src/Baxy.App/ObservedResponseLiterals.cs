using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.App;

/// <summary>Verified observed names are data, not vocabulary about BAXY internals.</summary>
internal static class ObservedResponseLiterals
{
    internal static string WithoutObservedNames(string text, string source)
    {
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        CollectSource(source, names, 0);
        if (names.Count == 0)
        {
            return text;
        }

        // This scratch copy is used only by lexical checks. Factual checks and
        // publication still receive every original word and its punctuation.
        // Compound identifiers extend through dots/hyphens, but a sentence's
        // final dot remains punctuation around the complete observed name.
        string pattern = @"(?<![\w.-])(?:" + string.Join('|', names
            .OrderByDescending(static name => name.Length).Select(Regex.Escape)) + @")(?!\w|[.-]\w)";
        return Regex.Replace(text, pattern, "\uFFFC",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(100));
    }

    private static void CollectSource(string source, HashSet<string> names, int depth)
    {
        if (depth > 8)
        {
            return;
        }
        try
        {
            using JsonDocument document = JsonDocument.Parse(source);
            Collect(document.RootElement, names, depth);
        }
        catch (JsonException)
        {
            // Legacy prose, malformed facts and dialogue grant no exemption.
        }
    }

    private static void Collect(JsonElement node, HashSet<string> names, int depth)
    {
        if (node.ValueKind != JsonValueKind.Object)
        {
            return;
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && node.TryGetProperty("operation", out JsonElement operation)
            && operation.ValueKind == JsonValueKind.String
            && (operation.GetString()!.StartsWith("window.", StringComparison.Ordinal)
                || operation.GetString() is "system.process.list" or "app.installed")
            && node.TryGetProperty("verified", out JsonElement verified) && verified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement succeeded) && succeeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement observed) && observed.ValueKind == JsonValueKind.Object)
        {
            if (operation.GetString() == "app.installed"
                && IsString(observed, "authority", "windows_start_catalog_snapshot"))
            {
                // The provider's human-readable authority is observed data too.
                names.Add("catálogo de inicio de Windows");
                names.Add("Windows Start application catalog");
            }
            bool processInventory = operation.GetString() == "system.process.list";
            string[] fields = processInventory ? ["name"] : ["title", "processName"];
            if (observed.TryGetProperty(processInventory ? "processes" : "windows", out JsonElement entries)
                && entries.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement entry in entries.EnumerateArray())
                {
                    if (entry.ValueKind != JsonValueKind.Object)
                    {
                        continue;
                    }
                    foreach (string field in fields)
                    {
                        if (entry.TryGetProperty(field, out JsonElement value) && value.ValueKind == JsonValueKind.String
                            && value.GetString() is { Length: > 0 and <= 4096 } name && !string.IsNullOrWhiteSpace(name))
                        {
                            names.Add(name);
                        }
                    }
                }
            }
        }
        if (node.TryGetProperty("steps", out JsonElement steps) && steps.ValueKind == JsonValueKind.Array && depth < 8)
        {
            foreach (JsonElement step in steps.EnumerateArray())
            {
                if (step.ValueKind == JsonValueKind.String)
                {
                    CollectSource(step.GetString()!, names, depth + 1);
                }
                else
                {
                    Collect(step, names, depth + 1);
                }
            }
        }
    }

    private static bool IsString(JsonElement node, string key, string value) =>
        node.TryGetProperty(key, out JsonElement property) && property.ValueKind == JsonValueKind.String
        && property.GetString() == value;
}
