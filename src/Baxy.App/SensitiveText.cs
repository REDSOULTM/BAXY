using System.IO;
using System.Text.RegularExpressions;

namespace Baxy.App;

/// <summary>
/// Masking of sensitive data (privacy, not understanding): a secret the person typed or said — a password, an API key,
/// a credential-shaped token — never reaches the transcript, the conversation log or the voice, and is never kept in
/// memory. This reads nothing about what the person wants; the request still goes to the model as it is.
/// </summary>
internal static partial class SensitiveText
{
    private const int MaximumTokenLength = 256;

    /// <summary>What the transcript shows in place of a message that carries a secret.</summary>
    internal const string Hidden = "••••••";

    internal static bool Contains(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        if (SecretPattern().IsMatch(value))
        {
            return true;
        }

        foreach (string token in value.Split(
                     [' ', '\t', '\r', '\n', '"', '\'', '(', ')', '[', ']', '<', '>', ',', ';', ':'],
                     StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (LooksLikeCredentialToken(token.TrimEnd('.', '!', '?')))
            {
                return true;
            }
        }

        return false;
    }

    private static bool LooksLikeCredentialToken(string token)
    {
        if (token.Length is < 20 or > MaximumTokenLength)
        {
            return false;
        }

        bool hasLetter = false;
        bool hasDigit = false;
        int firstSeparator = -1;
        for (int index = 0; index < token.Length; index++)
        {
            char character = token[index];
            if (character is >= 'a' and <= 'z' or >= 'A' and <= 'Z')
            {
                hasLetter = true;
            }
            else if (character is >= '0' and <= '9')
            {
                hasDigit = true;
            }
            else if (character is '-' or '_' or '.')
            {
                firstSeparator = firstSeparator < 0 ? index : firstSeparator;
            }
            else
            {
                return false;
            }
        }

        // A file name with dates or ids is not a credential.
        if (DocumentExtensionPattern().IsMatch(Path.GetExtension(token)))
        {
            return false;
        }

        bool credentialPrefix = firstSeparator is >= 2 and <= 16
            && token.Length - firstSeparator - 1 >= 16
            && token[..firstSeparator].All(static character => char.IsAsciiLetter(character));
        return hasLetter && hasDigit && (credentialPrefix || token.Length >= 32);
    }

    [GeneratedRegex(
        "(?:api[ ]*key|clave[ ]+api|password|contrase(?:ñ|n)a?|\\brut\\b|\\bssn\\b|social[ ]+security|token[ ]+(?:secreto|secret)|\\b(?:sk[-_][a-z0-9_-]{4,}|gh[pousr]_[a-z0-9]{8,}|github_pat_[a-z0-9_]{8,}|glpat-[a-z0-9_-]{10,}|(?:akia|asia)[a-z0-9]{12,}|aiza[a-z0-9_-]{12,}|xox[baprs]-[a-z0-9-]{8,}|npm_[a-z0-9]{20,}|(?:rk|pk)_live_[a-z0-9]{8,}))",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SecretPattern();

    [GeneratedRegex(
        "^\\.(?:txt|md|json|docx?|xlsx?|pdf)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex DocumentExtensionPattern();
}
