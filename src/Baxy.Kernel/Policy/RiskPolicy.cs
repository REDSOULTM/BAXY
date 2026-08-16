using Baxy.Kernel.Operations;

namespace Baxy.Kernel.Policy;

public static class RiskPolicy
{
    public static PolicyDecision Evaluate(OperationRisk risk) => risk switch
    {
        OperationRisk.ReadOnly => PolicyDecision.Allow,
        OperationRisk.Reversible => PolicyDecision.Allow,
        OperationRisk.Sensitive => PolicyDecision.RequireConfirmation,
        OperationRisk.External => PolicyDecision.RequireConfirmation,
        OperationRisk.Irreversible => PolicyDecision.RequireConfirmation,
        OperationRisk.Forbidden => PolicyDecision.Deny,
        _ => PolicyDecision.Deny,
    };
}
