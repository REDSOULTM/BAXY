using System.Globalization;
using System.Text;

namespace Baxy.Contracts;

/// <summary>
/// The one fold of an application or game name the catalogs compare by (auditoría final 2, fila 20: it was written
/// twice, identical, in ApplicationCatalogContract and GameCatalogContract): lower case, compatibility forms, no
/// accents, letters and digits separated by single spaces.
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

            if (character is >= 'a' and <= 'z' or >= '0' and <= '9')
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
