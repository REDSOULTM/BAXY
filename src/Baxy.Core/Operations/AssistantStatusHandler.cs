using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

/// <summary>
/// assistant.status reads what the App already holds for its view (its model's video memory and RAM, the session's
/// internet exits): the App answers it itself (NativeTurnLoop, OwnReadings) and never sends it here. The engine has none
/// of those readings, so a call that reaches it ends failed, with nothing said in their place.
/// </summary>
internal sealed class AssistantStatusHandler : IOperationHandler
{
    internal const string ReadByTheApp = "read_by_the_app";

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("assistant.status");

    public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken) =>
        ValueTask.FromResult(OperationOutcome.Failure(ReadByTheApp));
}
