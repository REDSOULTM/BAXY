using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

/// <summary>
/// Motor de computer use (plan post-goal Fase 4, D21;
/// documentacion/computer-use/CONTRATO_VISTA_ACCION.md §4): el bucle —mirar,
/// elegir un paso, ejecutarlo, volver a mirar— lo conduce el shell, que es
/// quien tiene a la mente delante. El core sólo ejecuta las primitivas de
/// cada paso con su postlectura y las deja en el journal. Invocado
/// directamente, sin ese bucle, no puede decidir nada y lo dice antes de
/// tocar la pantalla.
/// </summary>
internal sealed class ComputerUseMissionHandler : IOperationHandler
{
    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("mission.computer.use");

    public ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return ValueTask.FromResult(OperationOutcome.Failure(
            "computer_use_loop_not_hosted",
            causeCode: "computer_use_requires_shell"));
    }
}
