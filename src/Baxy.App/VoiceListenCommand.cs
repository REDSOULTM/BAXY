using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace Baxy.App;

/// <summary>
/// Encendido y apagado de la escucha permanente de BAXY, por voz o por texto.
/// No es el mute del micrófono de Windows: es el interruptor de BAXY.
/// </summary>
internal static partial class VoiceListenCommand
{
    internal static bool TryParse(string? text, out bool enable)
    {
        enable = false;
        if (string.IsNullOrWhiteSpace(text)
            || text.Any(static character => char.IsControl(character)))
        {
            return false;
        }

        string normalized = Fold(text);
        if (OffPattern().IsMatch(normalized))
        {
            enable = false;
            return true;
        }

        if (OnPattern().IsMatch(normalized))
        {
            enable = true;
            return true;
        }

        return false;
    }

    private static string Fold(string text)
    {
        string formD = text.Trim().Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(formD.Length);
        foreach (char character in formD)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character)
                != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(character);
            }
        }

        return builder.ToString().Normalize(NormalizationForm.FormC).ToLowerInvariant();
    }

    [GeneratedRegex(
        "^(?:deja de escucharme|deja de oirme|apaga la escucha|apaga el oido|stop listening|don't listen|do not listen|turn off listening)[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex OffPattern();

    [GeneratedRegex(
        "^(?:escucha siempre|activa la escucha|activa la wake(?: word)?|enciende la escucha|start listening|listen for baxy|wake on)[.!?]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex OnPattern();
}
