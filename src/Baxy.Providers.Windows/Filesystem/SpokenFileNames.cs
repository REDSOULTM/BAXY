using System.Globalization;
using System.Text;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// A file's name as a person says it. A voice dictates no separator between a name's words (holdout v5 V5E052
/// «factura marzo.pdf» for factura-marzo.pdf; holdout v6 V6F010 «lista invitados» for lista_invitados.txt), so the
/// words between space, -, _ and . are the name, whatever separates them. Every tool that matches a name the person
/// gave against the names of files and folders compares them here; a name spelled exactly (case aside) is still the
/// one meant before any that only has its words.
/// </summary>
public static class SpokenFileNames
{
    /// <summary>The words of a name in lower case, joined by one space where space, -, _ or . separated them:
    /// «Lista_Invitados.txt» and «lista invitados.txt» are «lista invitados txt».</summary>
    public static string Words(string name) => Join(name, withoutAccents: false);

    /// <summary><see cref="Words"/> also without accents («Canción.txt» is «cancion txt»): the names alike a tool
    /// offers, never one it acts on.</summary>
    public static string Folded(string name) => Join(name, withoutAccents: true);

    /// <summary>Whether a file's name is the name said, its words otherwise separated (case aside).</summary>
    public static bool Same(string fileName, string said) =>
        Words(said) is { Length: > 0 } words && Words(fileName) == words;

    /// <summary>Whether a file's name holds the part said, its words otherwise separated (case aside).</summary>
    public static bool Contains(string fileName, string part) =>
        Words(part) is { Length: > 0 } words && Words(fileName).Contains(words, StringComparison.Ordinal);

    private static string Join(string name, bool withoutAccents)
    {
        string text = name;
        try
        {
            text = name.Normalize(withoutAccents ? NormalizationForm.FormD : NormalizationForm.FormC);
        }
        catch (ArgumentException)
        {
            // a name Windows allows with a lone surrogate has no normal form
        }

        var joined = new StringBuilder(text.Length);
        bool gap = false;
        foreach (char character in text)
        {
            if (withoutAccents && CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
                continue;
            if (character is ' ' or '-' or '_' or '.')
            {
                gap = joined.Length > 0;
                continue;
            }

            if (gap) joined.Append(' ');
            gap = false;
            joined.Append(char.ToLowerInvariant(character));
        }

        return joined.ToString();
    }
}
