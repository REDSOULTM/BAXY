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
    private const int MinimumEncodedSecretLength = 30;

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
            string candidate = token.TrimEnd('.', '!', '?');
            if (LooksLikeCredentialToken(candidate) || LooksLikeEncodedSecret(candidate))
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

    // A base64-shaped secret (a cloud provider's secret access key: 40 characters with / and +, or a padded value
    // with =) is not caught by the token rule above, which takes only letters, digits and - _ . . Conservative: the
    // token carries / or + or trailing = padding, nothing but base64 characters (no dot, so no URL or file name),
    // upper case, lower case and digits, and its letters and digits switch kind as often as random text does (a path
    // or an identifier made of words switches only at its word boundaries). «NAME=value» is judged by its value.
    private static bool LooksLikeEncodedSecret(string token)
    {
        int assignment = token.IndexOf('=');
        if (assignment > 0 && token.AsSpan(assignment).TrimStart('=').Length > 0)
        {
            return LooksLikeEncodedSecret(token[(assignment + 1)..].TrimStart('='));
        }

        string body = token.TrimEnd('=');
        if (token.Length - body.Length > 2
            || body.Length is < MinimumEncodedSecretLength or > MaximumTokenLength
            || (body.IndexOfAny(['/', '+']) < 0 && body.Length == token.Length))
        {
            return false;
        }

        int upper = 0;
        int lower = 0;
        int digits = 0;
        int pairs = 0;
        int switches = 0;
        int previous = 0;
        foreach (char character in body)
        {
            int kind = character switch
            {
                >= 'a' and <= 'z' => 1,
                >= 'A' and <= 'Z' => 2,
                >= '0' and <= '9' => 3,
                '/' or '+' or '-' or '_' => 0,
                _ => -1,
            };
            if (kind < 0)
            {
                return false;
            }

            upper += kind == 2 ? 1 : 0;
            lower += kind == 1 ? 1 : 0;
            digits += kind == 3 ? 1 : 0;
            if (kind != 0 && previous != 0)
            {
                pairs++;
                switches += kind != previous ? 1 : 0;
            }

            previous = kind;
        }

        // Random base64 switches kind about 6 times in 10; words switch about 2 in 10.
        return upper >= 2 && lower >= 2 && digits >= 2 && pairs > 0 && switches * 10 >= pairs * 4;
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
