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
            && IsString(node, "operation", "web.news.headlines")
            && node.TryGetProperty("verified", out JsonElement newsVerified) && newsVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement newsSucceeded) && newsSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement newsObserved) && newsObserved.ValueKind == JsonValueKind.Object
            && newsObserved.TryGetProperty("headlines", out JsonElement headlines) && headlines.ValueKind == JsonValueKind.Array)
        {
            // NEWS2027 «buscá noticias de hoy»: a headline's title and its source
            // («cooperativa.cl», «dw.com») are observed data, not dotted codes.
            foreach (JsonElement entry in headlines.EnumerateArray())
            {
                if (entry.ValueKind != JsonValueKind.Object) continue;
                foreach (string field in new[] { "title", "source" })
                {
                    if (entry.TryGetProperty(field, out JsonElement value) && value.ValueKind == JsonValueKind.String
                        && value.GetString() is { Length: > 0 and <= 4096 } text && !string.IsNullOrWhiteSpace(text))
                    {
                        names.Add(text.Trim());
                    }
                }
            }
        }
        if (IsString(node, "kind", "confirmation")
            && node.TryGetProperty("pendingAction", out JsonElement pendingAction) && pendingAction.ValueKind == JsonValueKind.Object
            && pendingAction.TryGetProperty("arguments", out JsonElement pendingArguments) && pendingArguments.ValueKind == JsonValueKind.Object
            && pendingArguments.TryGetProperty("url", out JsonElement pendingUrl) && pendingUrl.ValueKind == JsonValueKind.String
            && Uri.TryCreate(pendingUrl.GetString(), UriKind.Absolute, out Uri? pendingUri)
            && pendingUri.Host is { Length: > 0 } pendingHost)
        {
            // H0081 «quiero que abras opera gx y entras a pivigames» → «¿Quieres
            // confirmar o cancelar que abra Opera GX y entre a pivigames.es?»: the
            // host of the navigation proposed for confirmation is observed data
            // (it came from the verified search), not a dotted operation name.
            names.Add(pendingHost.StartsWith("www.", StringComparison.OrdinalIgnoreCase) ? pendingHost[4..] : pendingHost);
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && (IsString(node, "operation", "browser.navigate") || IsString(node, "operation", "browser.navigate.named"))
            && node.TryGetProperty("verified", out JsonElement navVerified) && navVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement navSucceeded) && navSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement navObserved) && navObserved.ValueKind == JsonValueKind.Object
            && navObserved.TryGetProperty("finalUrl", out JsonElement finalUrl) && finalUrl.ValueKind == JsonValueKind.String
            && Uri.TryCreate(finalUrl.GetString(), UriKind.Absolute, out Uri? finalUri)
            && finalUri.Host is { Length: > 0 } finalHost)
        {
            // The host the browser actually reached («entré a pivigames.es») is
            // observed data as much as a search result's host.
            names.Add(finalHost.StartsWith("www.", StringComparison.OrdinalIgnoreCase) ? finalHost[4..] : finalHost);
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
            && IsString(node, "operation", "filesystem.write.text")
            && node.TryGetProperty("verified", out JsonElement writeVerified) && writeVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement writeSucceeded) && writeSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement written) && written.ValueKind == JsonValueKind.Object
            && written.TryGetProperty("name", out JsonElement writtenName) && writtenName.ValueKind == JsonValueKind.String
            && writtenName.GetString() is { Length: > 0 and <= 4096 } writtenText && !string.IsNullOrWhiteSpace(writtenText))
        {
            // FILES1711 «crea un archivo de texto con los 5 procesos que más
            // memoria usan»: the name of the file just written
            // («procesos-memoria.txt») is observed data the report must say.
            names.Add(writtenText);
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && (IsString(node, "operation", "filesystem.explorer.count") || IsString(node, "operation", "filesystem.known.list")
                || IsString(node, "operation", "filesystem.known.search"))
            && node.TryGetProperty("verified", out JsonElement folderVerified) && folderVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement folderSucceeded) && folderSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement folderObserved) && folderObserved.ValueKind == JsonValueKind.Object)
        {
            // EXPLORER2071 H0701: the folder the Explorer had in front is what the
            // person sees; the reply has to name it.
            foreach (string key in new[] { "folderName", "folder", "extension" })
            {
                if (folderObserved.TryGetProperty(key, out JsonElement folderValue) && folderValue.ValueKind == JsonValueKind.String
                    && folderValue.GetString() is { Length: > 0 and <= 4096 } folderText && !string.IsNullOrWhiteSpace(folderText))
                {
                    names.Add(folderText.Trim());
                }
            }
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && (IsString(node, "operation", "document.text.read") || IsString(node, "operation", "document.pdf.read"))
            && node.TryGetProperty("verified", out JsonElement documentVerified) && documentVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement documentSucceeded) && documentSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement documentObserved) && documentObserved.ValueKind == JsonValueKind.Object)
        {
            // TEXTREAD2063 H0299: what the file says is the file's own words,
            // not the assistant's vocabulary.
            foreach (string key in new[] { "text", "lead" })
            {
                if (documentObserved.TryGetProperty(key, out JsonElement documentText) && documentText.ValueKind == JsonValueKind.String
                    && documentText.GetString() is { Length: > 0 } body && !string.IsNullOrWhiteSpace(body))
                {
                    names.Add(body.Trim());
                    foreach (string line in body.Split('\n'))
                    {
                        string trimmed = line.Trim();
                        if (trimmed.Length >= 3)
                        {
                            names.Add(trimmed);
                        }
                    }
                }
            }

            if (documentObserved.TryGetProperty("headings", out JsonElement headings) && headings.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement heading in headings.EnumerateArray())
                {
                    if (heading.ValueKind == JsonValueKind.String
                        && heading.GetString() is { Length: > 0 } text && !string.IsNullOrWhiteSpace(text))
                    {
                        names.Add(text.Trim());
                    }
                }
            }

            if (documentObserved.TryGetProperty("reviewLabel", out JsonElement documentLabel) && documentLabel.ValueKind == JsonValueKind.String
                && documentLabel.GetString() is { Length: > 0 and <= 4096 } label && !string.IsNullOrWhiteSpace(label))
            {
                names.Add(label.Trim());
            }
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && (IsString(node, "operation", "web.download") || IsString(node, "operation", "file.compress")
                || IsString(node, "operation", "file.open") || IsString(node, "operation", "filesystem.create.directory"))
            && node.TryGetProperty("verified", out JsonElement fileVerified) && fileVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement fileSucceeded) && fileSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement fileObserved) && fileObserved.ValueKind == JsonValueKind.Object)
        {
            // DOWNLOAD2047: the file just written («250px-Wikipedia-logo-v2.svg.png»),
            // the zip and the source's host are observed data the report must say.
            foreach (string key in new[] { "name", "zipName" })
            {
                if (fileObserved.TryGetProperty(key, out JsonElement fileName) && fileName.ValueKind == JsonValueKind.String
                    && fileName.GetString() is { Length: > 0 and <= 4096 } fileText && !string.IsNullOrWhiteSpace(fileText))
                {
                    names.Add(fileText.Trim());
                }
            }

            if (fileObserved.TryGetProperty("sourceUrl", out JsonElement sourceUrl) && sourceUrl.ValueKind == JsonValueKind.String
                && Uri.TryCreate(sourceUrl.GetString(), UriKind.Absolute, out Uri? source) && source.Host.Length is > 0 and <= 253)
            {
                names.Add(source.Host.StartsWith("www.", StringComparison.OrdinalIgnoreCase) ? source.Host[4..] : source.Host);
            }
        }
        if (IsString(node, "kind", "operation") && IsString(node, "polarity", "success")
            && IsString(node, "operation", "wifi.scan")
            && node.TryGetProperty("verified", out JsonElement scanVerified) && scanVerified.ValueKind == JsonValueKind.True
            && node.TryGetProperty("succeeded", out JsonElement scanSucceeded) && scanSucceeded.ValueKind == JsonValueKind.True
            && node.TryGetProperty("observed", out JsonElement scanned) && scanned.ValueKind == JsonValueKind.Object
            && scanned.TryGetProperty("networks", out JsonElement networks) && networks.ValueKind == JsonValueKind.Array)
        {
            // NETWORK1729 «qué redes wifi hay»: a visible network name («Fibertel-2.4GHz»)
            // is observed data, dots included, not vocabulary about BAXY.
            foreach (JsonElement network in networks.EnumerateArray())
            {
                if (network.ValueKind == JsonValueKind.Object
                    && network.TryGetProperty("ssid", out JsonElement ssid) && ssid.ValueKind == JsonValueKind.String
                    && ssid.GetString() is { Length: > 0 and <= 4096 } ssidText && !string.IsNullOrWhiteSpace(ssidText))
                {
                    names.Add(ssidText);
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
