namespace Baxy.App;

/// <summary>
/// Which line each utterance the voice starts says, for the conductor's <c>speech.start</c>/<c>speech.end</c>
/// (<see cref="ProductConductorHost"/>), and the turn's first sound and its response's first sound.
/// <para>
/// Renew al máximo: the voice itself says whether an utterance is the notice (its <c>sound</c> event,
/// <see cref="MainWindowViewModel.VoiceSounded"/>). The order of arrival said it before: the first sound after the
/// notice's acceptance was the notice. But the notice sounds from its ready audio at once, and its first sound reached
/// the App before the acceptance did (nb-int5-X-s0 E005: sound at 2514 ms, acceptance at 2517 ms), so the notice was
/// named with the last line BAXY published (the previous case's answer), taken for the response, and the case's own
/// answer, said after it, was named the notice or not read at all.
/// </para>
/// </summary>
internal sealed class ConductorUtterances
{
    private string _lastSaid = string.Empty;

    /// <summary>What the utterance sounding now (or the last one) says, and whether it is the turn's notice.</summary>
    internal (string Text, bool Notice) Current { get; private set; } = (string.Empty, false);

    /// <summary>The turn's first sound, the notice's when it was said first (ms since the turn started).</summary>
    internal long? SpeechStartedMs { get; private set; }

    /// <summary>The first sound of the turn's response (not its notice).</summary>
    internal long? ResponseSpeechStartedMs { get; private set; }

    internal void TurnStarted()
    {
        SpeechStartedMs = null;
        ResponseSpeechStartedMs = null;
    }

    /// <summary>A line BAXY published (the person's own lines are not said).</summary>
    internal void Published(string body) => _lastSaid = body;

    /// <summary>An utterance's first sound; <paramref name="notice"/> is the notice's phrase when the voice says this
    /// utterance is the notice, null when it is an answer (the last line BAXY published).</summary>
    internal (string Text, bool Notice) Sounded(long sinceTurnMs, string? notice)
    {
        SpeechStartedMs ??= sinceTurnMs;
        Current = notice is not null ? (notice, true) : (_lastSaid, false);
        if (!Current.Notice)
        {
            ResponseSpeechStartedMs ??= sinceTurnMs;
        }

        return Current;
    }
}
