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
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && IsString(node, "operation", "web.search")
            && node.TryGetProperty("verified", out JsonElement searchVerified) && searchVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement searchSucceeded) && searchSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement searchObserved) && searchObserved.ValueKind == JsonValueKind.Object
            && searchObserved.TryGetProperty("results", out JsonElement searchResults) && searchResults.ValueKind == JsonValueKind.Array)
        {
            // WEB1447 «qué clima hace hoy»: a result's title and host are observed data.
            foreach (JsonElement entry in searchResults.EnumerateArray())
            {
                if (entry.ValueKind != JsonValueKind.Object) continue;
                if (entry.TryGetProperty("title", out JsonElement resultTitle) && resultTitle.ValueKind == JsonValueKind.String
                    && resultTitle.GetString() is { Length: > 0 and <= 4096 } titleText && !string.IsNullOrWhiteSpace(titleText))
                {
                    names.Add(titleText.Trim());
                }
                if (entry.TryGetProperty("url", out JsonElement resultUrl) && resultUrl.ValueKind == JsonValueKind.String
                    && Uri.TryCreate(resultUrl.GetString(), UriKind.Absolute, out Uri? resultUri)
                    && resultUri.Host is { Length: > 0 } hostName)
                {
                    names.Add(hostName.StartsWith("www.", StringComparison.OrdinalIgnoreCase) ? hostName[4..] : hostName);
                }
            }
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && IsString(node, "operation", "notification.list")
            && node.TryGetProperty("verified", out JsonElement notifVerified) && notifVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement notifSucceeded) && notifSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement notifObserved) && notifObserved.ValueKind == JsonValueKind.Object
            && notifObserved.TryGetProperty("notifications", out JsonElement notifications) && notifications.ValueKind == JsonValueKind.Array)
        {
            // AGENDA1435 «listá los timers»: a scheduled title is observed data.
            foreach (JsonElement entry in notifications.EnumerateArray())
            {
                if (entry.ValueKind == JsonValueKind.Object
                    && entry.TryGetProperty("title", out JsonElement notifTitle) && notifTitle.ValueKind == JsonValueKind.String
                    && notifTitle.GetString() is { Length: > 0 and <= 4096 } titleText && !string.IsNullOrWhiteSpace(titleText))
                {
                    names.Add(titleText);
                }
            }
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && IsString(node, "operation", "filesystem.known.list")
            && node.TryGetProperty("verified", out JsonElement listVerified) && listVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement listSucceeded) && listSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement listing) && listing.ValueKind == JsonValueKind.Object
            && listing.TryGetProperty("entries", out JsonElement listed) && listed.ValueKind == JsonValueKind.Array)
        {
            // FILES1425 «lista los archivos del escritorio»: the person asked for
            // the folder's names; a listed name (dots, hyphens, underscores
            // included) is observed data, not vocabulary about BAXY.
            foreach (JsonElement entry in listed.EnumerateArray())
            {
                if (entry.ValueKind == JsonValueKind.Object
                    && entry.TryGetProperty("name", out JsonElement listedName) && listedName.ValueKind == JsonValueKind.String
                    && listedName.GetString() is { Length: > 0 and <= 4096 } entryName && !string.IsNullOrWhiteSpace(entryName))
                {
                    names.Add(entryName);
                }
            }
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && IsString(node, "operation", "ocr.read")
            && node.TryGetProperty("verified", out JsonElement readVerified) && readVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement readSucceeded) && readSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement recognized) && recognized.ValueKind == JsonValueKind.Object
            && recognized.TryGetProperty("text", out JsonElement recognizedText) && recognizedText.ValueKind == JsonValueKind.String
            && recognizedText.GetString() is { Length: > 0 } screenText)
        {
            // SCREEN1411 «leéme lo que dice la pantalla»: the person asked for the
            // screen's words; quoting a recognized line (identifiers, paths and
            // dotted names included) is observed data, not vocabulary about BAXY.
            foreach (string line in screenText.Split('\n'))
            {
                string trimmed = line.Trim();
                if (trimmed.Length is > 1 and <= 4096)
                {
                    names.Add(trimmed);
                }
            }
            foreach (Match token in Regex.Matches(screenText, @"[\w-]+(?:[._][\w-]+)+",
                         RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(100)))
            {
                names.Add(token.Value);
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
