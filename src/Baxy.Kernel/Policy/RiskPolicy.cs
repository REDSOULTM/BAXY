using Baxy.Kernel.Operations;

namespace Baxy.Kernel.Policy;

public static class RiskPolicy
{
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
            OperationRisk.Sensitive => PolicyDecision.RequireConfirmation,
            OperationRisk.External => PolicyDecision.RequireConfirmation,
            OperationRisk.Irreversible => PolicyDecision.RequireConfirmation,
            _ => PolicyDecision.Deny,
        };
    }
}
