namespace Baxy.Kernel.Operations;

public interface IOperationHandler
{
    OperationDefinition Definition { get; }

    ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken);
}
