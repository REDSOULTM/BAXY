namespace Baxy.App;

/// <summary>
/// Whether BAXY's line asks the person about the call that waits for their «sí» (the confirmation route, with the Sí/No
/// buttons under it): only when that call is the turn's own (asked since the turn started). Ronda final 30 (regla 3): a
/// call offered to the model in this turn as what the person's words answer (asked before they arrived) is answered by
/// those words through the model, never by buttons under a line of this turn: a reply in words only («Vale, no lo
/// cierro. ¿Guardo algo primero?») is no question about that call, and a «Sí» under it ran it. A call a heartbeat held while the
/// person's words waited for their turn is neither: the model never read it, so its line asks nothing (audit, round B:
/// «¡De nada!» with Sí/No under it, and a «sí» there ran the heartbeat's call). A call is asked when its question is
/// published, not when it is held or the kernel challenges it: until then it is <see cref="Unpublished"/> and no words
/// of the person answer it (audit, round B: words said between the hold and the question confirmed it). Every moment is
/// a <see cref="System.Diagnostics.Stopwatch.GetTimestamp"/> timestamp.
/// </summary>
internal static class ConfirmationAsk
{
    /// <summary>The ask moment of a call held or challenged whose question is not published yet.</summary>
    internal const long Unpublished = long.MaxValue;

    /// <summary>The person's words or press, arrived at <paramref name="personAt"/>, answer the waiting call.</summary>
    internal static bool Answers(long askedAt, long personAt) => askedAt < personAt;

    internal static bool Asks(bool waiting, long askedAt, long turnStarted) => waiting && askedAt >= turnStarted;
}
