using System.Collections.ObjectModel;
using System.Text.RegularExpressions;
using Baxy.Contracts;

namespace Baxy.Kernel.Operations;

public sealed partial class OperationRegistry
{
    private readonly ReadOnlyDictionary<string, IOperationHandler> _handlers;

    public OperationRegistry(IEnumerable<IOperationHandler> handlers)
    {
        ArgumentNullException.ThrowIfNull(handlers);

        var byName = new Dictionary<string, IOperationHandler>(StringComparer.Ordinal);
        foreach (IOperationHandler handler in handlers)
        {
            ArgumentNullException.ThrowIfNull(handler);
            ValidateDefinition(handler.Definition);
            if (!byName.TryAdd(handler.Definition.Name, handler))
            {
                throw new ArgumentException(
                    $"Duplicate operation name '{handler.Definition.Name}'.",
                    nameof(handlers));
            }
        }

        _handlers = new ReadOnlyDictionary<string, IOperationHandler>(byName);
        Definitions = Array.AsReadOnly(
            byName.Values
                .Select(static handler => handler.Definition)
                .OrderBy(static definition => definition.Name, StringComparer.Ordinal)
                .ToArray());
        ToolDefinitions = Array.AsReadOnly(
            Definitions
                .Where(static definition =>
                    definition.ProductDescriptor?.ToolExposure == ToolExposure.Public)
                .ToArray());
        ToolDescriptors = Array.AsReadOnly(
            ToolDefinitions
                .Select(ProductCatalog.CreateToolDescriptor)
                .ToArray());
    }

    public IReadOnlyList<OperationDefinition> Definitions { get; }

    public IReadOnlyList<OperationDefinition> ToolDefinitions { get; }

    public IReadOnlyList<OperationDescriptor> ToolDescriptors { get; }

    public bool TryGet(string operationName, out IOperationHandler? handler)
    {
        if (operationName is null)
        {
            handler = null;
            return false;
        }

        return _handlers.TryGetValue(operationName, out handler);
    }

    private static void ValidateDefinition(OperationDefinition definition)
    {
        ArgumentNullException.ThrowIfNull(definition);
        if (!OperationNamePattern().IsMatch(definition.Name))
        {
            throw new ArgumentException(
                $"Invalid canonical operation name '{definition.Name}'.",
                nameof(definition));
        }

        if (string.IsNullOrWhiteSpace(definition.Description))
        {
            throw new ArgumentException("Operation description is required.", nameof(definition));
        }
    }

    [GeneratedRegex("^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*)+$", RegexOptions.CultureInvariant)]
    private static partial Regex OperationNamePattern();
}
