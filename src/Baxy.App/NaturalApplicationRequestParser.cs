using System.Globalization;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

internal static partial class NaturalApplicationRequestParser
{
    internal static bool TryParse(string text, out RoutedOperation? operation)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(text);
        Match match = ImperativePattern().Match(text.Trim());
        if (!match.Success)
        {
            match = PolitePattern().Match(text.Trim());
        }

        if (!match.Success)
        {
            operation = null;
            return false;
        }

        string target = AllowedHistoricalSuffixPattern()
            .Replace(match.Groups["target"].Value.Trim(), string.Empty)
            .Trim();
        target = CollapseRepeatedSingleWordTarget(target);
        if (!IsSafeTarget(target) || !IsKnownDirectApplication(target))
        {
            operation = null;
            return false;
        }

        string appId = Fold(target) switch
        {
            "bloc de notas" or "notepad" or "editor de texto" or
                "coso de notas" or "app de notas" => "windows.notepad",
            "calculadora" or "calculator" or "calc" => "windows.calculator",
            "configuracoes do windows" or "windows settings" => "ConfiguraciÃ³n",
            _ => target.Normalize(NormalizationForm.FormC),
        };
        operation = new RoutedOperation(
            "app.open",
            new JsonObject { ["appId"] = appId });
        return true;
    }

    internal static bool TryNormalizeKnownAlias(
        string value,
        out string canonical)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        canonical = Fold(value) switch
        {
            "bloc de notas" or "notepad" or "editor de texto" or
                "coso de notas" or "app de notas" => "windows.notepad",
            "calculadora" or "calculator" or "calc" => "windows.calculator",
            "configuracoes do windows" or "windows settings" => "Configuración",
            _ => string.Empty,
        };
        return canonical.Length > 0;
    }

    private static string CollapseRepeatedSingleWordTarget(string target)
    {
        string[] words = target.Split(
            (char[]?)null,
            StringSplitOptions.RemoveEmptyEntries);
        if (words.Length is > 1 and <= 3
            && words.All(word => string.Equals(
                Fold(word),
                Fold(words[0]),
                StringComparison.Ordinal)))
        {
            return words[0];
        }

        return target;
    }

    private static bool IsSafeTarget(string target)
    {
        if (string.IsNullOrWhiteSpace(target) || target.Length > 256)
        {
            return false;
        }

        if (target.Any(char.IsControl)
            || target.Contains("--", StringComparison.Ordinal)
            || target.Contains("://", StringComparison.Ordinal)
            || target.StartsWith("file:", StringComparison.OrdinalIgnoreCase)
            || target.IndexOfAny(['\\', '/', ';', '|', '&', '>', '<', '$']) >= 0
            || target.EndsWith('?')
            || target.EndsWith('!')
            || target.StartsWith("dos ventanas", StringComparison.OrdinalIgnoreCase)
            || FileExtensionPattern().IsMatch(target)
            || CompoundOpenPattern().IsMatch(target)
            || AlternativeTargetPattern().IsMatch(target)
            || CompoundActionPattern().IsMatch(target)
            || CommaActionPattern().IsMatch(target)
            || ConditionalTargetPattern().IsMatch(target))
        {
            return false;
        }

        return true;
    }

    private static bool IsKnownDirectApplication(string target) => Fold(target) is
        "bloc de notas" or "notepad" or "editor de texto" or "coso de notas" or
        "app de notas" or "calculadora" or "calculator" or "calc" or "spotify" or
        "steam" or "discord" or "chrome" or "google chrome" or "word" or
        "microsoft word" or "edge" or "microsoft edge" or "firefox" or "opera" or
        "whatsapp" or "excel" or "powerpoint" or "vlc" or
        "configuracoes do windows" or "windows settings";

    private static string Fold(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (char character in value.Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }

        return string.Join(' ', builder.ToString().Split(
            (char[]?)null,
            StringSplitOptions.RemoveEmptyEntries));
    }

    [GeneratedRegex(
        "^(?:(?:abre|abrí|abri|inicia|lanza|ejecuta|open(?: up)?|launch|start|ouvre|lance|öffne|offne|starte|apri|avvia|abra)(?: el| la| lo| the| le| den| der| das| il| o| a| as)? )(?<target>.+?)(?: por favor| please)?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ImperativePattern();

    [GeneratedRegex(
        "^¿?(?:(?:puedes|podrías|podrias)(?: por favor)? abrir|(?:can|could) you(?: please)? (?:open|launch|start))(?: el| la| the)? (?<target>.+?)(?: por favor| please)?\\?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PolitePattern();

    [GeneratedRegex(
        "\\.(?:bat|cmd|com|exe|lnk|ps1|txt|docx?|xlsx?|pdf)(?:\\s|$)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex FileExtensionPattern();

    [GeneratedRegex(
        "(?:\\b(?:y|and|then|luego|después|despues|o|or)\\s+|[.]\\s*)(?:abre|open|launch|start)\\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CompoundOpenPattern();

    [GeneratedRegex(
        "\\s+(?:o|or)\\s+",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AlternativeTargetPattern();

    [GeneratedRegex(
        "\\b(?:y|and|then|luego|después|despues)\\s+(?:borra|elimina|delete|close|cierra|ejecuta|run|escribe|write|envía|envia|send)\\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CompoundActionPattern();

    [GeneratedRegex(
        ",\\s*(?:pon|play|reproduce|baja|sube|set|ajusta|abre|open|cierra|close|borra|delete)\\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CommaActionPattern();

    [GeneratedRegex(
        "\\s+(?:si (?:está|esta) instalado|pero no maximices ni lances juegos|but don'?t say it'?s done if you can'?t verify it)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AllowedHistoricalSuffixPattern();

    [GeneratedRegex(
        "\\b(?:si puedes|si es posible|if possible|if you can)\\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ConditionalTargetPattern();
}
