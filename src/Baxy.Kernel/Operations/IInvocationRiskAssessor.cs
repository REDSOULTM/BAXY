using System.Text.Json;

namespace Baxy.Kernel.Operations;

/// <summary>
/// A handler whose risk depends on what this exact invocation touches (v3 r6 lectores, t2-r4 c04-5 «cierra
/// configuración» pidió confirmación). The catalog label of the operation stays as the historical seals cite it; the
/// engine asks the handler for the risk of the invocation in front of it. Closing a window that holds no document of
/// the person loses nothing, so that close is reversible; any other close keeps the declared risk.
/// </summary>
public interface IInvocationRiskAssessor
{
    /// <summary>
    /// The risk of this exact invocation, or null to keep the declared one. Never called for a forbidden operation.
    /// </summary>
    OperationRisk? AssessInvocationRisk(JsonElement arguments);
}
