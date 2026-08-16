using System.Globalization;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

internal static partial class NaturalAudioRequestParser
{
    public static bool IsAuditedCorrection(string text)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(text);
        return CorrectedVolumePattern().IsMatch(Fold(text));
    }

    public static bool TryParse(string text, out RoutedOperation? operation)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(text);
        string folded = Fold(text);
        string muteNormalized = NormalizeMuteText(text);

        if (AudioStatusPattern().IsMatch(folded))
        {
            operation = new RoutedOperation("audio.status", new JsonObject());
            return true;
        }

        if (TryResolveNamedAbsoluteVolume(folded, out int namedLevel))
        {
            operation = new RoutedOperation(
                "audio.volume",
                new JsonObject { ["level"] = namedLevel });
            return true;
        }

        Match volume = CorrectedVolumePattern().Match(folded);
        if (!volume.Success)
        {
            volume = SpanishVolumePattern().Match(folded);
        }

        if (!volume.Success)
        {
            volume = ShortSpanishVolumePattern().Match(folded);
        }

        if (!volume.Success)
        {
            volume = SpanishDeviceVolumeWithoutPrepositionPattern().Match(folded);
        }

        if (!volume.Success)
        {
            volume = EnglishSetVolumePattern().Match(folded);
        }

        if (!volume.Success)
        {
            volume = EnglishDropVolumePattern().Match(folded);
        }

        if (!volume.Success)
        {
            volume = EnglishTurnVolumePattern().Match(folded);
        }

        if (!volume.Success)
        {
            volume = EnglishMakeVolumePattern().Match(folded);
        }

        if (!volume.Success)
        {
            volume = NominalVolumePattern().Match(folded);
        }

        if (volume.Success
            && int.TryParse(
                volume.Groups["level"].Value,
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out int level)
            && level is >= 0 and <= 100)
        {
            operation = new RoutedOperation(
                "audio.volume",
                new JsonObject { ["level"] = level });
            return true;
        }

        if (MuteOnPattern().IsMatch(muteNormalized))
        {
            operation = new RoutedOperation(
                "audio.mute",
                new JsonObject { ["state"] = true });
            return true;
        }

        if (MuteOffPattern().IsMatch(muteNormalized))
        {
            operation = new RoutedOperation(
                "audio.mute",
                new JsonObject { ["state"] = false });
            return true;
        }

        operation = null;
        return false;
    }

    private static bool TryResolveNamedAbsoluteVolume(string folded, out int level)
    {
        if (folded.Length >= 2
            && folded[^1] is '.' or '!'
            && folded[^2] is '.' or '!')
        {
            level = -1;
            return false;
        }

        string canonical = folded.Length > 0 && (folded[^1] is '.' or '!')
            ? folded[..^1]
            : folded;
        level = canonical switch
        {
            "pone el volumen al minimo" or
            "pon el volumen del pc al minimo" => 0,
            "pon el volumen del pc a diez" or
            "pon el volumen del pc a diez por ciento" => 10,
            "pon el volumen del pc a veinte por ciento" => 20,
            "pon el volumen a la mitad" or
            "baja el volumen a la mitad" => 50,
            "subi el volumen al maximo" or
            "pon el volumen al maximo" => 100,
            _ => -1,
        };
        return level >= 0;
    }

    private static string Fold(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }

        return HorizontalWhitespacePattern()
            .Replace(builder.ToString(), " ")
            .Trim()
            .Normalize(NormalizationForm.FormC);
    }

    private static string NormalizeMuteText(string value) =>
        HorizontalWhitespacePattern()
            .Replace(
                value.Normalize(NormalizationForm.FormC).ToLowerInvariant(),
                " ")
            .Trim();

    [GeneratedRegex(
        "^\\u00bf?(?:que volumen tengo|mostrame el volumen|show me the volume|show me el volumen)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AudioStatusPattern();

    [GeneratedRegex(
        "^no, mejor pon el volumen a (?<level>100|[1-9]?[0-9])\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CorrectedVolumePattern();

    [GeneratedRegex(
        "^(?:pon|pone|cambia|deja|sube|subi|subile|baja) (?:el )?volumen(?: (?:del )?(?:pc|compu))? (?:a|al|en) (?<level>100|[1-9]?[0-9])(?: ?(?:%|por ciento|percent))?(?: porfa| y verifica)?\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishVolumePattern();

    [GeneratedRegex(
        "^(?:pon|pone) volumen(?: a| al)? (?<level>100|[1-9]?[0-9])(?: ?(?:%|por ciento|percent))?\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ShortSpanishVolumePattern();

    [GeneratedRegex(
        "^(?:pon|pone) (?:el )?volumen (?:del )?(?:pc|compu) (?<level>100|[1-9]?[0-9])(?: ?(?:%|por ciento|percent))?\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SpanishDeviceVolumeWithoutPrepositionPattern();

    [GeneratedRegex(
        "^(?:set|change) (?:the )?(?:pc )?volume to (?<level>100|[1-9]?[0-9])(?: ?(?:%|por ciento|percent))?\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishSetVolumePattern();

    [GeneratedRegex(
        "^drop the volume to (?<level>100|[1-9]?[0-9])(?: ?(?:%|por ciento|percent))?\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishDropVolumePattern();

    [GeneratedRegex(
        "^turn the volume (?:up |down )?to (?<level>100|[1-9]?[0-9])(?: ?(?:%|por ciento|percent))?\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishTurnVolumePattern();

    [GeneratedRegex(
        "^make it (?<level>100|[1-9]?[0-9]) percent volume\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EnglishMakeVolumePattern();

    [GeneratedRegex(
        "^(?:volumen|volume) (?:a|al|to) (?<level>100|[1-9]?[0-9])(?: ?(?:%|por ciento|percent))?\\.?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NominalVolumePattern();

    [GeneratedRegex(
        "^(?:mute|mute everything|mute system porfa|mute the sound|ponelo en mute|silencia el audio|silencia el pc)[.!]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MuteOnPattern();

    [GeneratedRegex(
        "^(?:unmute|unmute the pc|unmute the sound please|desmutea el pc|quita el mute del pc)[.!]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MuteOffPattern();

    [GeneratedRegex("[ \\t]+", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex HorizontalWhitespacePattern();
}
