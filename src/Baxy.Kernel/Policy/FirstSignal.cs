using System.Globalization;
using System.Text;

namespace Baxy.Kernel.Policy;

/// <summary>
/// Estimate, formulate, cadence. Three functions, no orchestrator.
/// Fast path stays silent. Slow path emits formulated progress that never
/// claims a result. A gap strictly over three seconds without BAXY output
/// emits a milestone.
/// </summary>
public static class FirstSignal
{
    public const double SilenceBudgetSeconds = 3.0;
    public const double EarlyThresholdSeconds = 1.5;
    public const string PathRecognizer = "explicit_effects";
    public const string PathClosedConversation = "explicit_conversation";
    public const string PathModel = "model";
    public const string KindEarly = "early";
    public const string KindMilestone = "hito";

    private const double RecognizerSeconds = 0.07;
    private const double ClosedConversationSeconds = 0.9;
    private const double ModelSeconds = 2.5;
    private const double ExtraStepSeconds = 2.0;
    private const int SnippetChars = 42;

    public static double EstimateTurnSeconds(string path, int stepCount = 1)
    {
        double cost = path switch
        {
            PathRecognizer => RecognizerSeconds,
            PathClosedConversation => ClosedConversationSeconds,
            _ => ModelSeconds,
        };
        int extra = Math.Max(0, stepCount - 1);
        return cost + extra * ExtraStepSeconds;
    }

    public static bool ShouldEmitEarly(string path, int stepCount = 1) =>
        EstimateTurnSeconds(path, stepCount) >= EarlyThresholdSeconds;

    public static bool ShouldEmitMilestone(
        DateTimeOffset? lastVisibleUtc,
        DateTimeOffset nowUtc,
        double budgetSeconds = SilenceBudgetSeconds) =>
        lastVisibleUtc is { } last && (nowUtc - last).TotalSeconds > budgetSeconds;

    public static string FormulateProgress(
        string userText,
        string kind = KindEarly,
        int step = 0,
        int total = 0,
        string? language = null)
    {
        string lang = language ?? ResponseLanguage(userText);
        string snippet = Snippet(userText);
        if (string.Equals(lang, "en", StringComparison.Ordinal))
        {
            if (kind == KindMilestone && total > 1 && step > 0)
            {
                string body = string.Format(
                    CultureInfo.InvariantCulture,
                    "Still working on step {0} of {1}",
                    step,
                    total);
                if (snippet.Length > 0)
                {
                    body = body + ": " + snippet;
                }

                return body + ".";
            }

            return snippet.Length > 0
                ? "Still working on " + snippet + "."
                : "Still working.";
        }

        if (kind == KindMilestone && total > 1 && step > 0)
        {
            string body = string.Format(
                CultureInfo.InvariantCulture,
                "Sigo en el paso {0} de {1}",
                step,
                total);
            if (snippet.Length > 0)
            {
                body = body + ": " + snippet;
            }

            return body + ".";
        }

        return snippet.Length > 0 ? "Sigo con " + snippet + "." : "Sigo.";
    }

    public static string VisibleAfterVerification(string inProgress, string correction)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(correction);
        _ = inProgress;
        return correction.Trim();
    }

    public static string ResponseLanguage(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return "es";
        }

        foreach (char character in text)
        {
            if (character is 'á' or 'é' or 'í' or 'ó' or 'ú' or 'ñ' or '¿' or '¡'
                or 'Á' or 'É' or 'Í' or 'Ó' or 'Ú' or 'Ñ')
            {
                return "es";
            }
        }

        int spanish = 0;
        int english = 0;
        foreach (string token in Tokenize(text))
        {
            if (token is "abre" or "algo" or "al" or "con" or "crea" or "cuentame"
                or "dime" or "el" or "explicame" or "la" or "las" or "los" or "me"
                or "pon" or "que" or "silencia" or "sube" or "una" or "volumen")
            {
                spanish++;
            }

            if (token is "about" or "and" or "how" or "me" or "mute" or "please"
                or "something" or "tell" or "the" or "what" or "walk")
            {
                english++;
            }
        }

        return english > spanish ? "en" : "es";
    }

    private static string Snippet(string text)
    {
        string collapsed = Collapse(text).Trim().Trim(" \t.,;:¡!¿?".ToCharArray());
        if (collapsed.Length <= SnippetChars)
        {
            return collapsed;
        }

        string clipped = collapsed[..SnippetChars];
        int lastSpace = clipped.LastIndexOf(' ');
        if (lastSpace > 0)
        {
            clipped = clipped[..lastSpace];
        }

        return clipped.Trim(" \t.,;:¡!¿?".ToCharArray());
    }

    private static string Collapse(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return string.Empty;
        }

        var builder = new StringBuilder(text.Length);
        bool pendingSpace = false;
        foreach (char character in text.Trim())
        {
            if (char.IsWhiteSpace(character))
            {
                pendingSpace = true;
                continue;
            }

            if (pendingSpace && builder.Length > 0)
            {
                builder.Append(' ');
            }

            pendingSpace = false;
            builder.Append(character);
        }

        return builder.ToString();
    }

    private static IEnumerable<string> Tokenize(string text)
    {
        var builder = new StringBuilder();
        foreach (char character in text.ToLowerInvariant())
        {
            if (character is >= 'a' and <= 'z')
            {
                builder.Append(character);
                continue;
            }

            if (builder.Length > 0)
            {
                yield return builder.ToString();
                builder.Clear();
            }
        }

        if (builder.Length > 0)
        {
            yield return builder.ToString();
        }
    }
}
