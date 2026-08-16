using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

internal sealed class AppStatusHandler : IOperationHandler
{
    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("app.status");

    public ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            _ = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.EmptyArguments)
                ?? throw new JsonException("Arguments cannot be null.");
        }
        catch (JsonException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_arguments"));
        }

        var status = new AppStatusResult(
            true,
            ProtocolVersion.Current,
            ProductCatalog.OperationNames);
        JsonElement result = JsonSerializer.SerializeToElement(
            status,
            CoreJsonContext.Default.AppStatusResult);
        return ValueTask.FromResult(OperationOutcome.Success(result));
    }
}
