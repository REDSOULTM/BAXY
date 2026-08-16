using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// Decide si una operación necesita que el modelo extraiga argumentos y lleva
/// los que extrajo a su forma canónica. Es el borde común de los planes directos
/// y los compuestos: ambos entran por aquí para recibir la misma identidad.
/// </summary>
internal static class MindArgumentNormalization
{
    internal static bool RequiresExtraction(ProductOperationDescriptor descriptor)
    {
        ArgumentNullException.ThrowIfNull(descriptor);
        return descriptor.ArgumentsSchema.Properties.Count > 0;
    }

    internal static JsonObject Normalize(
        string operationName,
        string objective,
        JsonObject extractedArguments)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        ArgumentException.ThrowIfNullOrWhiteSpace(objective);
        ArgumentNullException.ThrowIfNull(extractedArguments);
        if (string.Equals(operationName, "app.open", StringComparison.Ordinal)
            && extractedArguments["appId"] is JsonValue value
            && value.TryGetValue(out string? extractedAppId)
            && !string.IsNullOrWhiteSpace(extractedAppId)
            && NaturalApplicationRequestParser.TryNormalizeKnownAlias(
                extractedAppId,
                out string canonicalAppId))
        {
            // The model may preserve a natural alias such as "notepad".
            // Normalize at the common execution boundary so both direct and
            // compound plans receive the same canonical identity.
            JsonObject normalized = extractedArguments.DeepClone().AsObject();
            normalized["appId"] = canonicalAppId;
            return normalized;
        }

        return extractedArguments;
    }
}
