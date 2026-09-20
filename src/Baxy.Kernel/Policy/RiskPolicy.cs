using Baxy.Kernel.Operations;

namespace Baxy.Kernel.Policy;

/// <summary>
/// Confirmation policy per mode. Decisión del dueño 2026-09-20 (D3,
/// artifacts/comprobaciones/C03/DECISIONES_DUENO_2026-09-20.md): «lo que debe
/// pedir permisos sólo deben ser cosas destructivas o irreparables». Reproducir,
/// navegar, copiar, capturar, pulsar, escribir, radios y ajustes van directos en
/// modo normal; lo que llega a otra persona (mensajes y correo) y lo que destruye
/// o interrumpe (work_loss, session_disruption, monetary) sigue preguntando. Las
/// etiquetas de riesgo del catálogo no cambian: los sellos históricos las citan.
/// </summary>
public static class RiskPolicy
{
    // External communication that reaches another person: the only external
    // operations that keep asking in normal mode.
    private static readonly HashSet<string> ExternalRequiringConfirmation = new(StringComparer.Ordinal)
    {
        "message.send",
        "message.send.test",
        "email.latest.reply",
        "email.send",
    };

    public static PolicyDecision Evaluate(
        OperationRisk risk,
        ConfirmationMode mode = ConfirmationMode.Normal,
        string? operation = null)
    {
        if (risk == OperationRisk.Forbidden)
        {
            return PolicyDecision.Deny;
        }

        if (mode == ConfirmationMode.Bypass)
        {
            return PolicyDecision.Allow;
        }

        // Identity: apagar / cerrar sesión van directos. The catalog still
        // labels system.power as work_loss so historical seals do not move.
        if (string.Equals(operation, "system.power", StringComparison.Ordinal))
        {
            return PolicyDecision.Allow;
        }

        return risk switch
        {
            OperationRisk.ReadOnly => PolicyDecision.Allow,
            OperationRisk.Reversible => PolicyDecision.Allow,
            // privacy_sensitive e installation: leer, copiar, capturar, escribir,
            // radios, ajustes e instalar no destruyen nada (D3).
            OperationRisk.Sensitive => PolicyDecision.Allow,
            OperationRisk.External => operation is not null && ExternalRequiringConfirmation.Contains(operation)
                ? PolicyDecision.RequireConfirmation
                : PolicyDecision.Allow,
            OperationRisk.Irreversible => PolicyDecision.RequireConfirmation,
            _ => PolicyDecision.Deny,
        };
    }
}
