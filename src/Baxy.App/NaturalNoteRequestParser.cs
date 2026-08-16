using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

internal sealed record RoutedOperation(string Name, JsonObject Arguments);

internal static partial class NaturalNoteRequestParser
{
    private const int MaximumQuickTitleUtf8Bytes = 120;
    private const int MaximumNoteTitleUtf8Bytes = 512;

    public const string Guidance =
        "Puedo crear, listar, leer, enviar a la papelera y restaurar notas en español, English o spanglish. " +
        "Por ejemplo: «anota comprar leche», «read the note called comprar leche» o " +
        "«restaura la nota comprar leche de la papelera». También puedo abrir Notepad y consultar " +
        "CPU, GPU, VRAM, RAM, disco, batería o la versión de Windows, y ajustar el volumen o " +
        "silencio global.";

    public static bool TryParse(string text, out RoutedOperation? operation)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(text);
        string trimmed = text.Trim();
        if (!IsWellFormedUtf16(trimmed))
        {
            operation = null;
            return false;
        }

        string normalized = trimmed.Normalize(NormalizationForm.FormC);

        bool auditedAudioCorrection = NaturalAudioRequestParser.IsAuditedCorrection(normalized);
        bool auditedApplicationOpen = NaturalApplicationRequestParser.TryParse(
            normalized,
            out RoutedOperation? applicationOperation);
        if (ContainsControlCharacter(normalized)
            || (NegatedOrConditionalPrefixPattern().IsMatch(normalized)
                && !auditedAudioCorrection)
            || (ConditionalSuffixPattern().IsMatch(normalized)
                && !auditedApplicationOpen)
            || ReminderCompositionPattern().IsMatch(normalized))
        {
            operation = null;
            return false;
        }

        if (OpenNotepadPattern().IsMatch(normalized)
            || PoliteSpanishOpenNotepadPattern().IsMatch(normalized)
            || PoliteEnglishOpenNotepadPattern().IsMatch(normalized))
        {
            operation = new RoutedOperation(
                "app.open",
                new JsonObject { ["appId"] = "windows.notepad" });
            return true;
        }

        if (auditedApplicationOpen)
        {
            operation = applicationOperation;
            return true;
        }

        if (NaturalSystemStatusRequestParser.TryParse(normalized, out operation))
        {
            return true;
        }

        if (NaturalAudioRequestParser.TryParse(normalized, out operation))
        {
            return true;
        }

        Match namedCreate = SpanishNamedCreatePattern().Match(normalized);
        if (!namedCreate.Success)
        {
            namedCreate = EnglishNamedCreatePattern().Match(normalized);
        }

        if (namedCreate.Success)
        {
            return TryBuildNamedCreate(namedCreate, out operation);
        }

        Match quickCreate = SpanishShortQuickCreatePattern().Match(normalized);
        if (!quickCreate.Success)
        {
            quickCreate = SpanishTakeNotePattern().Match(normalized);
        }

        if (!quickCreate.Success)
        {
            quickCreate = SpanishExplicitQuickCreatePattern().Match(normalized);
        }

        if (!quickCreate.Success)
        {
            quickCreate = EnglishQuickCreatePattern().Match(normalized);
        }

        if (quickCreate.Success)
        {
            return TryBuildQuickCreate(quickCreate, out operation);
        }

        if (TrashedListPattern().IsMatch(normalized)
            || PrefixedTrashedListPattern().IsMatch(normalized))
        {
            operation = new RoutedOperation(
                "note.list",
                new JsonObject { ["scope"] = "trashed" });
            return true;
        }

        if (ActiveListPattern().IsMatch(normalized)
            || PrefixedActiveListPattern().IsMatch(normalized))
        {
            operation = new RoutedOperation("note.list", new JsonObject());
            return true;
        }

        Match restore = SpanishScopedRestorePattern().Match(normalized);
        if (!restore.Success)
        {
            restore = EnglishScopedRestorePattern().Match(normalized);
        }

        if (!restore.Success)
        {
            restore = DirectRestorePattern().Match(normalized);
        }

        if (restore.Success)
        {
            return TryBuildTitleOperation("note.restore", restore, out operation);
        }

        Match trash = SpanishMoveToTrashPattern().Match(normalized);
        if (!trash.Success)
        {
            trash = SpanishMoveToTrashPrefixPattern().Match(normalized);
        }

        if (!trash.Success)
        {
            trash = EnglishMoveToTrashPattern().Match(normalized);
        }

        if (!trash.Success)
        {
            trash = EnglishMoveToTrashPrefixPattern().Match(normalized);
        }

        if (!trash.Success)
        {
            trash = DirectTrashPattern().Match(normalized);
        }

        if (trash.Success)
        {
            return TryBuildTitleOperation("note.trash", trash, out operation);
        }

        Match read = ReadPattern().Match(normalized);
        if (read.Success)
        {
            return TryBuildTitleOperation("note.read", read, out operation);
        }

        operation = null;
        return false;
    }

    private static bool TryBuildNamedCreate(Match match, out RoutedOperation? operation)
    {
        if (!TryNormalizeCapture(match.Groups["title"].Value, stripTerminalPunctuation: false, out string title)
            || !TryNormalizeCapture(match.Groups["content"].Value, stripTerminalPunctuation: false, out string content)
            || !IsSafeTitle(title))
        {
            operation = null;
            return false;
        }

        operation = new RoutedOperation(
            "note.create",
            new JsonObject
            {
                ["title"] = title,
                ["content"] = content,
            });
        return true;
    }

    private static bool TryBuildQuickCreate(Match match, out RoutedOperation? operation)
    {
        if (!TryNormalizeCapture(match.Groups["content"].Value, stripTerminalPunctuation: false, out string content))
        {
            operation = null;
            return false;
        }

        string title = BuildQuickTitle(content);
        if (!IsSafeTitle(title))
        {
            operation = null;
            return false;
        }

        operation = new RoutedOperation(
            "note.create",
            new JsonObject
            {
                ["title"] = title,
                ["content"] = content,
            });
        return true;
    }

    private static bool TryBuildTitleOperation(
        string operationName,
        Match match,
        out RoutedOperation? operation)
    {
        if (!TryNormalizeCapture(match.Groups["title"].Value, stripTerminalPunctuation: true, out string title)
            || !IsSafeTitle(title))
        {
            operation = null;
            return false;
        }

        operation = new RoutedOperation(
            operationName,
            new JsonObject { ["title"] = title });
        return true;
    }

    private static bool TryNormalizeCapture(
        string value,
        bool stripTerminalPunctuation,
        out string normalized)
    {
        normalized = value.Trim();
        if (stripTerminalPunctuation
            && normalized.Length > 0
            && normalized[^1] is '.' or '!' or '?')
        {
            normalized = normalized[..^1].TrimEnd();
        }

        normalized = StripMatchingOuterQuotes(normalized).Trim().Normalize(NormalizationForm.FormC);
        return normalized.Length > 0 && !ContainsControlCharacter(normalized);
    }

    private static string StripMatchingOuterQuotes(string value)
    {
        while (value.Length >= 2 && IsMatchingQuotePair(value[0], value[^1]))
        {
            value = value[1..^1].Trim();
        }

        return value;
    }

    private static bool IsMatchingQuotePair(char first, char last) =>
        (first, last) is ('"', '"') or ('\'', '\'') or ('«', '»') or ('“', '”') or ('‘', '’');

    private static string BuildQuickTitle(string content)
    {
        string collapsed = HorizontalWhitespacePattern().Replace(content, " ");
        var title = new StringBuilder(capacity: Math.Min(collapsed.Length, MaximumQuickTitleUtf8Bytes));
        int byteCount = 0;

        foreach (Rune rune in collapsed.EnumerateRunes())
        {
            if (byteCount + rune.Utf8SequenceLength > MaximumQuickTitleUtf8Bytes)
            {
                break;
            }

            title.Append(rune);
            byteCount += rune.Utf8SequenceLength;
        }

        return title.ToString().TrimEnd().Normalize(NormalizationForm.FormC);
    }

    private static bool IsSafeTitle(string title) =>
        Encoding.UTF8.GetByteCount(title) <= MaximumNoteTitleUtf8Bytes
        && !BulkTitlePattern().IsMatch(title)
        && !MultipleNoteSelectorPattern().IsMatch(title)
        && !FilesystemNoisePattern().IsMatch(title);

    private static bool ContainsControlCharacter(string value)
    {
        foreach (char character in value)
        {
            if (char.IsControl(character))
            {
                return true;
            }
        }

        return false;
    }

    private static bool IsWellFormedUtf16(string value)
    {
        for (int index = 0; index < value.Length; index++)
        {
            char character = value[index];
            if (char.IsHighSurrogate(character))
            {
                if (index + 1 >= value.Length || !char.IsLowSurrogate(value[index + 1]))
                {
                    return false;
                }

                index++;
            }
            else if (char.IsLowSurrogate(character))
            {
                return false;
            }
        }

        return true;
    }

    [GeneratedRegex(
        "^(?:abre|open(?:[ \\t]+up)?)[ \\t]+(?:(?:el|the)[ \\t]+)?(?:notepad|bloc[ \\t]+de[ \\t]+notas)(?:[ \\t]+(?:por[ \\t]+favor|please))?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex OpenNotepadPattern();

    [GeneratedRegex(
        "^\\u00bf?[ \\t]*(?:puedes|podr[i\\u00ed]as)[ \\t]+abrir[ \\t]+(?:el[ \\t]+)?(?:notepad|bloc[ \\t]+de[ \\t]+notas)(?:[ \\t]+por[ \\t]+favor)?[ \\t]*\\?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PoliteSpanishOpenNotepadPattern();

    [GeneratedRegex(
        "^(?:can|could|would)[ \\t]+you[ \\t]+(?:please[ \\t]+)?(?:open|launch)(?:[ \\t]+up)?[ \\t]+(?:the[ \\t]+)?notepad(?:[ \\t]+please)?[ \\t]*\\?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PoliteEnglishOpenNotepadPattern();

    [GeneratedRegex(
        "^(?:crea|cre\\u00e1)[ \\t]+una[ \\t]+nota[ \\t]+llamada[ \\t]+(?<title>.+?)[ \\t]+con[ \\t]+(?<content>.+?)(?:[ \\t]+y[ \\t]+gu[a\\u00e1]rdala)?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishNamedCreatePattern();

    [GeneratedRegex(
        "^create[ \\t]+a[ \\t]+note[ \\t]+called[ \\t]+(?<title>.+?)[ \\t]+with[ \\t]+(?<content>.+?)(?:[ \\t]+and[ \\t]+save[ \\t]+it)?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishNamedCreatePattern();

    [GeneratedRegex(
        "^(?:anota|apunta)[ \\t]+(?:que[ \\t]+)?(?<content>.+?)(?:[ \\t]+y[ \\t]+gu[a\\u00e1]rdala)?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishShortQuickCreatePattern();

    [GeneratedRegex(
        "^(?:toma|tom\\u00e1)[ \\t]+nota(?:[ \\t]+de)?(?:[ \\t]+que)?[ \\t]*(?::[ \\t]*)?(?<content>.+?)(?:[ \\t]+y[ \\t]+gu[a\\u00e1]rdala)?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishTakeNotePattern();

    [GeneratedRegex(
        "^(?:crea|cre\\u00e1)[ \\t]+una[ \\t]+nota[ \\t]*(?::[ \\t]*|que[ \\t]+diga[ \\t]+)(?<content>.+?)(?:[ \\t]+y[ \\t]+gu[a\\u00e1]rdala)?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishExplicitQuickCreatePattern();

    [GeneratedRegex(
        "^create[ \\t]+a[ \\t]+note[ \\t]*(?::[ \\t]*|saying[ \\t]+)(?<content>.+?)(?:[ \\t]+and[ \\t]+save[ \\t]+it)?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishQuickCreatePattern();

    [GeneratedRegex(
        "^(?:(?:mu[e\\u00e9]strame|muestra|lista|ens[e\\u00e9][n\\u00f1]ame|show(?:[ \\t]+me)?|list)[ \\t]+)?(?:(?:mis|my|las|the)[ \\t]+)?(?:notas|notes)(?:[ \\t]+(?:borradas|eliminadas|en[ \\t]+la[ \\t]+papelera|trashed|deleted|in[ \\t]+(?:the[ \\t]+)?trash))[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex TrashedListPattern();

    [GeneratedRegex(
        "^(?:(?:mu[e\\u00e9]strame|muestra|lista|ens[e\\u00e9][n\\u00f1]ame|show(?:[ \\t]+me)?|list)[ \\t]+)?(?:(?:mis|my|las|the)[ \\t]+)?(?:borradas|eliminadas|trashed|deleted)[ \\t]+(?:notas|notes)[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PrefixedTrashedListPattern();

    [GeneratedRegex(
        "^(?:(?:mu[e\\u00e9]strame|muestra|lista|ens[e\\u00e9][n\\u00f1]ame|show(?:[ \\t]+me)?|list)[ \\t]+)?(?:(?:mis|my|las|the)[ \\t]+)?(?:notas|notes)(?:[ \\t]+(?:activas|active))?[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ActiveListPattern();

    [GeneratedRegex(
        "^(?:(?:mu[e\\u00e9]strame|muestra|lista|ens[e\\u00e9][n\\u00f1]ame|show(?:[ \\t]+me)?|list)[ \\t]+)?(?:(?:mis|my|las|the)[ \\t]+)?(?:activas|active)[ \\t]+(?:notas|notes)[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PrefixedActiveListPattern();

    [GeneratedRegex(
        "^(?:restaura|recupera)[ \\t]+(?:la[ \\t]+)?nota(?:[ \\t]+llamada)?[ \\t]+(?<title>.+)[ \\t]+de[ \\t]+(?:la[ \\t]+)?papelera[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishScopedRestorePattern();

    [GeneratedRegex(
        "^(?:restore|recover)[ \\t]+(?:the[ \\t]+)?note(?:[ \\t]+called)?[ \\t]+(?<title>.+)[ \\t]+from[ \\t]+(?:the[ \\t]+)?trash[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishScopedRestorePattern();

    [GeneratedRegex(
        "^(?:restaura|recupera|restore|recover)[ \\t]+(?:(?:la|the)[ \\t]+)?(?:nota|note)(?:[ \\t]+(?:llamada|called))?[ \\t]+(?<title>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex DirectRestorePattern();

    [GeneratedRegex(
        "^(?:mueve|env[i\\u00ed]a)[ \\t]+(?:la[ \\t]+)?nota(?:[ \\t]+llamada)?[ \\t]+(?<title>.+)[ \\t]+a[ \\t]+(?:la[ \\t]+)?papelera[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishMoveToTrashPattern();

    [GeneratedRegex(
        "^(?:mueve|env[i\\u00ed]a)[ \\t]+a[ \\t]+(?:la[ \\t]+)?papelera[ \\t]+(?:la[ \\t]+)?nota(?:[ \\t]+llamada)?[ \\t]+(?<title>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishMoveToTrashPrefixPattern();

    [GeneratedRegex(
        "^(?:move|send)[ \\t]+(?:the[ \\t]+)?note(?:[ \\t]+called)?[ \\t]+(?<title>.+)[ \\t]+to[ \\t]+(?:the[ \\t]+)?trash[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishMoveToTrashPattern();

    [GeneratedRegex(
        "^(?:move|send)[ \\t]+to[ \\t]+(?:the[ \\t]+)?trash[ \\t]+(?:the[ \\t]+)?note(?:[ \\t]+called)?[ \\t]+(?<title>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishMoveToTrashPrefixPattern();

    [GeneratedRegex(
        "^(?:borra|elimina|delete|trash)[ \\t]+(?:(?:la|the)[ \\t]+)?(?:nota|note)(?:[ \\t]+(?:llamada|called))?[ \\t]+(?<title>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex DirectTrashPattern();

    [GeneratedRegex(
        "^(?:lee|muestra|mu[e\\u00e9]strame|read|show(?:[ \\t]+me)?)[ \\t]+(?:(?:la|the)[ \\t]+)?(?:nota|note)(?:[ \\t]+(?:llamada|called))?[ \\t]+(?<title>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ReadPattern();

    [GeneratedRegex(
        "^(?:no|nunca|jam[a\\u00e1]s|don['\\u2019]?t|do[ \\t]+not|never|si|if)(?:[ \\t,]|$)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NegatedOrConditionalPrefixPattern();

    [GeneratedRegex(
        "(?:^|[ \\t,])(?:si[ \\t]+puedes|si[ \\t]+es[ \\t]+posible|if[ \\t]+possible|if[ \\t]+you[ \\t]+can)[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ConditionalSuffixPattern();

    [GeneratedRegex(
        "(?:^|[ \\t,;])(?:recu[e\\u00e9]rdame|recordatorio|remind[ \\t]+me|reminder)(?:$|[ \\t,;:.!?])",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ReminderCompositionPattern();

    [GeneratedRegex("[ \\t]+", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex HorizontalWhitespacePattern();

    [GeneratedRegex(
        "^(?:(?:todas?|varias?)(?:[ \\t]+las?)?[ \\t]+notas?|all(?:[ \\t]+the)?[ \\t]+notes?|every[ \\t]+note)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex BulkTitlePattern();

    [GeneratedRegex(
        "[ \\t]+(?:y|and)[ \\t]+(?:(?:la|the)[ \\t]+)?(?:nota|note)(?:[ \\t]+|$)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MultipleNoteSelectorPattern();

    [GeneratedRegex(
        "^(?:[a-z]:[\\\\/]|\\\\\\\\|\\./|\\.\\./|file:|https?://)|\\.(?:txt|md|json|exe)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex FilesystemNoisePattern();
}
