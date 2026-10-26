namespace Baxy.App;

/// <summary>
/// What BAXY says aloud when a turn the person opened ends without an answer from the model (final 4, accesibilidad).
/// The identity: «Habla siempre: la respuesta se dice en voz alta escribas o hables» and «BAXY narra lo que hace». A
/// failed turn published no line, so nothing was said: the view showed the failure as its state (App.tsx FAILURE) and
/// someone who does not look at the screen heard silence. Each line says plainly that there was no answer and why, and
/// never claims a result: after a call the model may have acted, so the line says it does not know.
/// </summary>
internal static class TurnFailureSpeech
{
    /// <summary>The spoken line for a turn's failure code (<see cref="MainWindowViewModel.LastTurnFailure"/>); null for
    /// a code that is not a turn's.</summary>
    internal static string? LineOf(string? failure) => failure switch
    {
        "mind_unavailable" => "No pude responder: el modelo no está disponible ahora.",
        "decision_unavailable" => "No pude responder: el modelo no contestó. Pídemelo otra vez.",
        "decision_unavailable_after_call" =>
            "El modelo dejó de contestar después de actuar, así que no sé si terminé lo que pediste. Revísalo antes de pedirlo otra vez.",
        "turn_failed" => "No pude terminar lo que pediste: algo falló dentro de BAXY.",
        _ => null,
    };
}
