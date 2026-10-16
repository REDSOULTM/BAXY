namespace Baxy.App;

/// <summary>
/// Whether BAXY's line asks the person about the call that waits for their «sí» (the confirmation route, with the Sí/No
/// buttons under it): only when that call is the turn's own (asked since the turn started) or was offered to the model
/// in this turn as what the person's words answer (asked before they arrived). A call a heartbeat held while the
/// person's words waited for their turn is neither: the model never read it, so its line asks nothing (audit, round B:
/// «¡De nada!» with Sí/No under it, and a «sí» there ran the heartbeat's call). Every moment is a
/// <see cref="System.Diagnostics.Stopwatch.GetTimestamp"/> timestamp.
/// </summary>
internal static class ConfirmationAsk
{
    internal static bool Asks(bool waiting, long askedAt, long turnStarted, long personAt) =>
        waiting && (askedAt >= turnStarted || askedAt < personAt);
}
