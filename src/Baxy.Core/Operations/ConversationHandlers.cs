using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

/// <summary>
/// pc-f6-sesiones (2026-10-25): the conversations with BAXY are the App's own (FieldProductChannel keeps them and the
/// one on screen), so the App runs conversation.* itself (NativeTurnLoop) and never sends them here. The engine still
/// registers them because its registry is the product catalog whole (ProductCatalog.ValidateAgainst); one that reaches
/// it anyway is refused, nothing changed.
/// </summary>
internal static class ConversationHandlers
{
    internal static IOperationHandler[] Create() =>
    [
        new AppOnly("conversation.list"),
        new AppOnly("conversation.new"),
        new AppOnly("conversation.open"),
        new AppOnly("conversation.rename"),
    ];

    private sealed class AppOnly(string name) : IOperationHandler
    {
        public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(name);

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken) =>
            ValueTask.FromResult(OperationOutcome.Failure("conversation_runs_in_app"));
    }
}
