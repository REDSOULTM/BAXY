using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.Clipboard;

/// <summary>
/// Banco de uso 05-11 (S07): the model read a clipboard nobody had asked about, which held a command with a key, and told it
/// (identity: local and private). What looks like a key or a password by its form does not reach the model. Only the form is
/// compared, no word of the text: Yelp's detect-secrets and truffleHog scan the same way, a run of 20 characters or more that
/// is unlikely by its letters (Shannon entropy, 3.0 being detect-secrets' lower limit, the one for hexadecimal).
/// The form cannot tell a key from a hash, so a long hash goes too, and a short plain password («Perro2024») does not: the
/// receipt says that a part looks like one, never that the rest is not.
/// </summary>
public static partial class SecretShape
{
    public const string Shown = "•••";

    private const int KeyRun = 20;
    private const int KeySegment = 16;
    private const double KeyEntropy = 3.0;

    // How often the class of the next character changes in a segment: about 0.66 in random base64 and 0.47 in hexadecimal,
    // and 0.25 in a long CamelCase name, which has no digit, so letters alone need more than a name reaches.
    private const double ChangesWithDigits = 0.25;
    private const double ChangesLettersOnly = 0.45;

    private const int PasswordShortest = 8;
    private const int PasswordLongest = 64;
    private const double PasswordChanges = 0.4;

    /// <summary>The text with what looks like a key or a password as <see cref="Shown"/>, and how many such parts it had.</summary>
    public static string Mask(string text, out int parts)
    {
        ArgumentNullException.ThrowIfNull(text);
        int found = 0;
        string shown = Run().Replace(text, run =>
        {
            if (!LooksLikeKey(run.Value))
                return run.Value;
            found++;
            return Shown;
        });
        string alone = shown.Trim();
        shown = Word().Replace(shown, word =>
        {
            if (!LooksLikePassword(word.Value, word.Value == alone))
                return word.Value;
            found++;
            return Shown;
        });
        parts = found;
        return shown;
    }

    private static bool LooksLikeKey(string run)
    {
        if (run.Length < KeyRun)
            return false;
        string segment = Alphanumeric().Split(run).MaxBy(static part => part.Length) ?? string.Empty;
        return segment.Length >= KeySegment && Entropy(segment) >= KeyEntropy
            && Changes(segment) >= (segment.Any(char.IsDigit) ? ChangesWithDigits : ChangesLettersOnly);
    }

    // A word of every class of character, changing class often; alone in the text, three classes do if lower case is one:
    // an upper-case code or a date is not a password. An address, a path, a mail and a file's name have the form of what they
    // are. A hyphen, an underscore or a dot joins words and counts for no class: a version or a GUID has no other symbol.
    private static bool LooksLikePassword(string word, bool alone)
    {
        if (word.Length is < PasswordShortest or > PasswordLongest || word.Contains("://", StringComparison.Ordinal)
            || word.Contains('\\', StringComparison.Ordinal) || word[0] == '/' || Mail().IsMatch(word) || FileName().IsMatch(word))
            return false;
        bool lower = word.Any(char.IsLower);
        int classes = (lower ? 1 : 0) + (word.Any(char.IsUpper) ? 1 : 0) + (word.Any(char.IsDigit) ? 1 : 0)
            + (word.Any(static c => !char.IsLetterOrDigit(c) && c is not ('-' or '_' or '.')) ? 1 : 0);
        return (classes == 4 || (alone && classes == 3 && lower)) && Changes(word) >= PasswordChanges;
    }

    private static double Entropy(string text)
    {
        double bits = 0;
        foreach (IGrouping<char, char> letter in text.GroupBy(static c => c))
        {
            double share = (double)letter.Count() / text.Length;
            bits -= share * Math.Log2(share);
        }

        return bits;
    }

    private static double Changes(string text)
    {
        static int ClassOf(char c) => char.IsLower(c) ? 0 : char.IsUpper(c) ? 1 : char.IsDigit(c) ? 2 : 3;
        int changes = 0;
        for (int i = 1; i < text.Length; i++)
        {
            if (ClassOf(text[i]) != ClassOf(text[i - 1]))
                changes++;
        }

        return (double)changes / text.Length;
    }

    [GeneratedRegex(@"[^\s""'`,;:=()\[\]{}<>|&?#]+")]
    private static partial Regex Run();

    [GeneratedRegex(@"\S+")]
    private static partial Regex Word();

    [GeneratedRegex(@"[^\p{L}\p{Nd}]+")]
    private static partial Regex Alphanumeric();

    [GeneratedRegex(@"^[^@\s]+@[^@\s]+\.\p{L}{2,}$")]
    private static partial Regex Mail();

    [GeneratedRegex(@"\.\p{L}[\p{L}\p{Nd}]{1,4}$")]
    private static partial Regex FileName();
}
