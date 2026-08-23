using Baxy.Contracts;

namespace Baxy.Kernel.Policy;

/// <summary>
/// Autocorrección: una afirmación no verificada se sustituye por el texto
/// que la verificación autoriza. Una sola función, el triple que se journala.
/// </summary>
public static class HonestyCorrection
{
    /// <summary>
    /// Etapa journalada mientras entiende. No afirma un resultado y no es
    /// prosa visible: la frase la formula el modelo por la cola de compose.
    /// </summary>
    public const string NonAssertingInProgress = "understanding";

    public static HonestyCorrectionTrace Correct(
        string inProgressSignal,
        string verificationDenial,
        string correctionMessage)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(inProgressSignal);
        ArgumentException.ThrowIfNullOrWhiteSpace(verificationDenial);
        ArgumentException.ThrowIfNullOrWhiteSpace(correctionMessage);
        return new HonestyCorrectionTrace(
            inProgressSignal,
            verificationDenial,
            correctionMessage);
    }
}
