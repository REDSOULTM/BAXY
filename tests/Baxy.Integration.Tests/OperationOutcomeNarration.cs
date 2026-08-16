using Baxy.Core.Operations;
using Baxy.Kernel.Operations;

namespace Baxy.Integration.Tests;

internal static class OperationOutcomeNarration
{
    internal static string For(string operation, OperationOutcome outcome) =>
        ProductOperationNarrator.Instance.Narrate(operation, outcome);
}
