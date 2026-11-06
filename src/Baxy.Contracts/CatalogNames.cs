using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace Baxy.Contracts;

/// <summary>
/// The one fold of an application or game name everything compares by (the catalogs, the resolver, the snapshot the
/// model reads): lower case, compatibility forms, no accents, runs of white space as one space; every other character
/// stays («Notepad++» is not «Notepad»; re-audit of the second round, 2026-10-15).
/// </summary>
public static partial class CatalogNames
{
    public static string Normalize(string value)
    {
        ArgumentNullException.ThrowIfNull(value);

        string folded = value
            .Replace("ß", "ss", StringComparison.Ordinal)
            .Replace("ẞ", "ss", StringComparison.Ordinal)
            .ToLowerInvariant()
            .Normalize(NormalizationForm.FormKD);
        var builder = new StringBuilder(folded.Length);
        bool previousSeparator = true;
        foreach (char character in folded)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character)
                == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (!char.IsWhiteSpace(character))
            {
                builder.Append(character);
                previousSeparator = false;
            }
            else if (!previousSeparator)
            {
                builder.Append(' ');
                previousSeparator = true;
            }
        }

        return builder.ToString().Trim();
    }

    /// <summary>
    /// Ajuste c4 (banco ciego c3, causas 1 y 16): the name folded, then without each qualifier at its end in turn, a group
    /// in parentheses or a version («4.76», «v23.01») or architecture («x64», «64-bit», «64») word: «IrfanView 64 4.76»
    /// is also «IrfanView 64» and «IrfanView», «PowerToys (Preview)» also «PowerToys». A number without a point names the
    /// product («Microsoft 365» stays), any other word or sign is part of the name, and a name never loses its last letter.
    /// </summary>
    public static IReadOnlyList<string> Stems(string value)
    {
        string stem = Normalize(value);
        var stems = new List<string> { stem };
        while (Unqualified(stem) is { } shorter && shorter.Any(char.IsLetter))
            stems.Add(stem = shorter);
        return stems;
    }

    // A folded name without its last qualifier; null when it ends in none.
    private static string? Unqualified(string name)
    {
        if (name.EndsWith(')') && name.LastIndexOf('(') is > 0 and int open)
            return name[..open].TrimEnd();
        int space = name.LastIndexOf(' ');
        return space > 0 && Qualifier().IsMatch(name[(space + 1)..]) ? name[..space] : null;
    }

    [GeneratedRegex(@"^(v?\d+(\.\d+)+|v\d+|x64|x86|arm64|64-bit|32-bit|64|32)$", RegexOptions.CultureInvariant)]
    private static partial Regex Qualifier();
}
