using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;

namespace Baxy.Integration.Tests;

internal static class OperationOutcomeNarration
{
    internal static string For(string operation, OperationOutcome outcome) =>
        ProductOperationNarrator.Instance.Narrate(operation, outcome);

    internal static JsonObject Facts(string operation, OperationOutcome outcome)
    {
        JsonNode? node = JsonNode.Parse(For(operation, outcome));
        return node as JsonObject
            ?? throw new InvalidOperationException("visible facts are not a JSON object");
    }
}
