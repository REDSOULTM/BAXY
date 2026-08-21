using Baxy.Contracts;

namespace Baxy.Kernel.Policy;

/// <summary>
/// Autocorrección: una afirmación no verificada se sustituye por el texto
/// que la verificación autoriza. Una sola función, el triple que se journala.
/// </summary>
public static class HonestyCorrection
{
    /// <summary>
    /// Señal de progreso que la App publica mientras entiende. No afirma un
    /// resultado. Es el <c>Claim</c> de la traza cuando la verificación niega.
    /// </summary>
    public const string NonAssertingInProgress = "Estoy entendiendo tu petición.";

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
