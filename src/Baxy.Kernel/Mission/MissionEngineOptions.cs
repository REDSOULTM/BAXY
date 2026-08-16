using Baxy.Kernel.Operations;

namespace Baxy.Kernel.Mission;

/// <summary>
/// Dependencias opcionales de <see cref="MissionEngine"/>. Existe para que una
/// dependencia opcional nueva sea una propiedad más y no duplique el número de
/// constructores.
/// </summary>
public sealed class MissionEngineOptions
{
    /// <summary>
    /// Autentica el sobre de las operaciones privadas. Sin él, una operación
    /// privada se rechaza.
    /// </summary>
    public IPrivateOperationEnvelopeAuthenticator? PrivateEnvelopeAuthenticator { get; init; }

    /// <summary>
    /// Redacta el texto de los estados terminales. Por defecto, el narrador
    /// mínimo del kernel.
    /// </summary>
    public IOperationResponseNarrator? Narrator { get; init; }

    /// <summary>
    /// Reloj con el que caducan los retos de confirmación. Por defecto, el del
    /// sistema.
    /// </summary>
    public TimeProvider? TimeProvider { get; init; }

    /// <summary>
    /// Autoridad de confirmación ya construida. Sólo la usan las pruebas del
    /// kernel para observar la emisión y revocación de retos.
    /// </summary>
    internal InMemoryConfirmationAuthority? ConfirmationAuthority { get; init; }
}
