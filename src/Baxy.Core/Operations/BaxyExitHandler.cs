using System.Text.Json;
using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

/// <summary>
/// Encargo 25 (G12, uso real 02-11: «ciérrate» → app.close of BAXY → app_running_in_background): BAXY closes itself as
/// its tray's «Salir» does. The App already answers a named event with that same orderly exit (the development
/// launcher's, App.xaml.cs: the conversation kept, the icon removed, the engine and the mind stopped by their channel),
/// so this sets it. The App closes after this call answers, so the result says the request was delivered, never that
/// BAXY is closed; with no App listening nothing is asked.
/// </summary>
internal sealed class BaxyExitHandler(string eventName = BaxyExitHandler.AppExitEventName) : IOperationHandler
{
    internal const string Operation = "baxy.exit";

    /// <summary>The event the running App exits on (App.xaml.cs, main.py).</summary>
    public const string AppExitEventName = @"Local\BAXY.Product.App.Exit";

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(Operation);

    public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        EventWaitHandle? exit;
        try
        {
            if (!EventWaitHandle.TryOpenExisting(eventName, out exit))
            {
                return ValueTask.FromResult(OperationOutcome.Failure("baxy_app_not_listening"));
            }
        }
        catch (UnauthorizedAccessException)
        {
            // Another user's BAXY, as the App's own second start takes it: it cannot be asked.
            return ValueTask.FromResult(OperationOutcome.Failure("baxy_app_not_listening"));
        }

        using (exit)
        {
            if (!exit.Set())
            {
                return ValueTask.FromResult(OperationOutcome.Failure("baxy_app_not_listening"));
            }
        }

        using JsonDocument result = JsonDocument.Parse(
            """{"version":1,"exitRequested":true,"delivered":true,"authority":"baxy_app_exit_event"}""");
        return ValueTask.FromResult(OperationOutcome.Success(result.RootElement.Clone()));
    }
}
