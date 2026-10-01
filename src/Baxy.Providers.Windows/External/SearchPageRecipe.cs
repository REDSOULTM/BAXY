using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// M102 (DEV-D v3z D-s017 «a good southern style mac n cheese recipe», D-w10-t1 «¿me regalas una receta sencilla de
// arepas de queso?»): neither recipe book had the dish, and the reply was a sentence about it, with no quantity and no
// step (D52: a recipe is its quantities, and memory gives none). A recipe page says its recipe twice: once in prose for
// the reader and once as schema.org «Recipe» data in a JSON-LD script for search engines, with its ingredients
// (quantities included), its steps and how many it serves. That data is read here, from the page SearchPageReader
// fetched for a search result; nothing else of the page is kept.
internal static class SearchPageRecipe
{
    private const int MaximumIngredients = 30;
    private const int MaximumSteps = 20;
    private const int MaximumLineCharacters = 400;
    private const int MaximumDepth = 8;

    private static readonly TimeSpan RegexBudget = TimeSpan.FromSeconds(2);

    private static readonly Regex JsonLd = new(
        @"<script\b[^>]*\btype\s*=\s*[""']?application/ld\+json[""']?[^>]*>(?<data>.*?)</script\s*>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Tag = new("<[^>]*>", RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Number = new(@"\d+", RegexOptions.CultureInvariant, RegexBudget);

    private static readonly JsonDocumentOptions Lenient = new()
    {
        AllowTrailingCommas = true,
        CommentHandling = JsonCommentHandling.Skip,
        MaxDepth = 64,
    };

    internal readonly record struct PageRecipe(string Name, WikimediaReferenceSource.Recipe Recipe);

    // The page's recipe whose name (or the result's title) carries the dish asked for, with two ingredients and a step
    // at least; null otherwise.
    internal static PageRecipe? Read(string html, string title, string[] named)
    {
        try
        {
            foreach (Match script in JsonLd.Matches(html))
            {
                // The data as written («&amp;» inside its strings is decoded line by line); a script whose whole body
                // was entity-encoded is read decoded.
                string data = script.Groups["data"].Value.Trim();
                JsonDocument? document = Parse(data) ?? Parse(WebUtility.HtmlDecode(data));
                if (document is null) continue;
                using (document)
                {
                    foreach (JsonElement node in RecipeNodes(document.RootElement, 0))
                    {
                        PageRecipe? recipe = FromNode(node, title, named);
                        if (recipe is not null) return recipe;
                    }
                }
            }
        }
        catch (RegexMatchTimeoutException)
        {
            return null;
        }
        return null;
    }

    private static JsonDocument? Parse(string data)
    {
        try
        {
            return JsonDocument.Parse(data, Lenient);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static IEnumerable<JsonElement> RecipeNodes(JsonElement element, int depth)
    {
        if (depth > MaximumDepth) yield break;
        if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in element.EnumerateArray())
            {
                foreach (JsonElement found in RecipeNodes(item, depth + 1)) yield return found;
            }
            yield break;
        }
        if (element.ValueKind != JsonValueKind.Object) yield break;
        if (IsRecipe(element))
        {
            yield return element;
            yield break;
        }
        foreach (JsonProperty property in element.EnumerateObject())
        {
            if (property.Value.ValueKind is JsonValueKind.Object or JsonValueKind.Array)
            {
                foreach (JsonElement found in RecipeNodes(property.Value, depth + 1)) yield return found;
            }
        }
    }

    private static bool IsRecipe(JsonElement node) =>
        node.TryGetProperty("@type", out JsonElement type)
        && (type.ValueKind == JsonValueKind.String && IsRecipeType(type.GetString())
            || type.ValueKind == JsonValueKind.Array
            && type.EnumerateArray().Any(static item => item.ValueKind == JsonValueKind.String && IsRecipeType(item.GetString())));

    private static bool IsRecipeType(string? type) =>
        type is not null && (type == "Recipe" || type.EndsWith("/Recipe", StringComparison.Ordinal));

    private static PageRecipe? FromNode(JsonElement node, string title, string[] named)
    {
        string name = Clean(StringProperty(node, "name"));
        if (named.Length > 0)
        {
            var observed = new HashSet<string>(WebBrowserAdapter.SearchTokens(name + " " + title), StringComparer.Ordinal);
            int carried = named.Count(word => WebBrowserAdapter.MatchesSearchTerm(word, observed));
            if (carried < (named.Length + 1) / 2) return null;
        }
        string[] ingredients = Lines(node, "recipeIngredient").Concat(Lines(node, "ingredients"))
            .Distinct(StringComparer.Ordinal)
            .Take(MaximumIngredients)
            .ToArray();
        var steps = new List<string>();
        if (node.TryGetProperty("recipeInstructions", out JsonElement instructions))
            CollectSteps(instructions, steps, 0);
        if (ingredients.Length < 2 || steps.Count == 0) return null;
        string description = Clean(StringProperty(node, "description"));
        int cut = description.IndexOfAny(['.', '!', '?']);
        if (cut > 0) description = description[..(cut + 1)];
        if (description.Length > 200) description = string.Empty;
        return new PageRecipe(
            name.Length > 0 ? name : title,
            new WikimediaReferenceSource.Recipe(ingredients, steps.Take(MaximumSteps).ToArray(), Servings(node), description));
    }

    private static string StringProperty(JsonElement node, string name) =>
        node.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    private static IEnumerable<string> Lines(JsonElement node, string name)
    {
        if (!node.TryGetProperty(name, out JsonElement value)) yield break;
        if (value.ValueKind == JsonValueKind.String)
        {
            foreach (string line in (value.GetString() ?? string.Empty).Split('\n'))
            {
                string cleaned = Clean(line);
                if (cleaned.Length > 0) yield return cleaned;
            }
            yield break;
        }
        if (value.ValueKind != JsonValueKind.Array) yield break;
        foreach (JsonElement item in value.EnumerateArray())
        {
            string cleaned = item.ValueKind == JsonValueKind.String ? Clean(item.GetString()) : string.Empty;
            if (cleaned.Length > 0) yield return cleaned;
        }
    }

    // A step is a string, a HowToStep's text, or each step of a HowToSection, in the page's order.
    private static void CollectSteps(JsonElement value, List<string> steps, int depth)
    {
        if (depth > MaximumDepth || steps.Count >= MaximumSteps) return;
        switch (value.ValueKind)
        {
            case JsonValueKind.String:
                foreach (string line in (value.GetString() ?? string.Empty).Split('\n'))
                {
                    string cleaned = Clean(line);
                    if (cleaned.Length > 0) steps.Add(cleaned);
                }
                break;
            case JsonValueKind.Array:
                foreach (JsonElement item in value.EnumerateArray()) CollectSteps(item, steps, depth + 1);
                break;
            case JsonValueKind.Object:
                if (value.TryGetProperty("itemListElement", out JsonElement items))
                {
                    CollectSteps(items, steps, depth + 1);
                }
                else
                {
                    string text = Clean(StringProperty(value, "text"));
                    if (text.Length == 0) text = Clean(StringProperty(value, "name"));
                    if (text.Length > 0) steps.Add(text);
                }
                break;
        }
    }

    // «4», «4 servings», «Para 6 personas», ["8", "8 porciones"]: the first count from 1 to 100.
    private static int? Servings(JsonElement node)
    {
        if (!node.TryGetProperty("recipeYield", out JsonElement value)) return null;
        IEnumerable<JsonElement> values = value.ValueKind == JsonValueKind.Array ? value.EnumerateArray() : [value];
        foreach (JsonElement item in values)
        {
            if (item.ValueKind == JsonValueKind.Number && item.TryGetInt32(out int count) && count is >= 1 and <= 100)
                return count;
            if (item.ValueKind == JsonValueKind.String
                && Number.Match(item.GetString() ?? string.Empty) is { Success: true } found
                && int.TryParse(found.Value, out int said) && said is >= 1 and <= 100)
            {
                return said;
            }
        }
        return null;
    }

    private static string Clean(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return string.Empty;
        string text = WebUtility.HtmlDecode(Tag.Replace(WebUtility.HtmlDecode(value), " "));
        text = string.Join(' ', text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        return text.Length > MaximumLineCharacters ? text[..MaximumLineCharacters].TrimEnd() + "…" : text;
    }
}
