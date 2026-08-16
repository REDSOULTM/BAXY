using System.Globalization;
using System.Text;

namespace Baxy.Contracts;

public static class GameCatalogContract
{
    public const int CurrentVersion = 1;
    public const int MaximumEntries = 4_096;
    public const int MaximumAppIdLength = 16;
    public const int MaximumNameUtf8Bytes = 512;
    public const int MaximumTotalUtf8Bytes = 512 * 1024;

    public static string NormalizeName(string value)
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
