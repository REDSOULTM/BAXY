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
    /// <summary>
    /// First hito after last visible BAXY output. Strictly over the 3 s
    /// silence bar, short of a 1 s pulse's next tick at 4 s.
    /// </summary>
    public const double MilestoneDueSeconds = SilenceBudgetSeconds + 0.01;
    public static readonly TimeSpan MilestoneDueDelay =
        TimeSpan.FromSeconds(MilestoneDueSeconds);
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

    /// <summary>
    /// The formulated progress notice: short, in the person's language, claiming no result. Estabilidad cu-v3
    /// 2026-10-08 (FirstSignal «Sigo con abre obs y agrega una escena nueva que se.», 16 times in one case; «Sigo con
    /// search my onenote notebooks for receta.»): it never repeats the person's words, raw, cut mid-sentence or in
    /// another language. <paramref name="language"/> is the turn's decided language when known; the request's own
    /// reading is only the fallback before the turn is decided.
    /// </summary>
    public static string FormulateProgress(
        string userText,
        string kind = KindEarly,
        int step = 0,
        int total = 0,
        string? language = null)
    {
        bool english = string.Equals(
            language is "es" or "en" ? language : ResponseLanguage(userText), "en", StringComparison.Ordinal);
        if (kind == KindMilestone && total > 1 && step > 0)
        {
            return string.Format(
                CultureInfo.InvariantCulture,
                english ? "Still working, step {0} of {1}." : "Sigo en el paso {0} de {1}.",
                step,
                total);
        }

        return english ? "Still working on it." : "Sigo trabajando en ello.";
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
