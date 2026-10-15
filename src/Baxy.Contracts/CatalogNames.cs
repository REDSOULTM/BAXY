using System.Globalization;
using System.Text;

namespace Baxy.Contracts;

/// <summary>
/// The one fold of an application or game name everything compares by (the catalogs, the resolver, the snapshot the
/// model reads): lower case, compatibility forms, no accents, runs of white space as one space; every other character
/// stays («Notepad++» is not «Notepad»; re-audit of the second round, 2026-10-15).
/// </summary>
public static class CatalogNames
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
}
