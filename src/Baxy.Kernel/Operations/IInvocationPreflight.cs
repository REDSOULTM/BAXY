using System.Text.Json;

namespace Baxy.Kernel.Operations;

/// <summary>
/// What a handler reads of the exact invocation in front of it before the engine asks the person for it, with no effect.
/// v3 r6 lectores (t2-r4 c04-5 «cierra configuración» pidió confirmación): the risk depends on what this invocation
/// touches. The catalog label of the operation stays as the historical seals cite it; closing a window that holds no
/// document of the person loses nothing, so that close is reversible, and any other keeps the declared risk. Al máximo,
/// flujos («¿Borro viejo.txt?» → «sí» → «no existe»): a target that is not there once (none, or several) is that
/// failure now, with its candidates, and no yes is asked for what cannot run. The execution resolves again.
/// </summary>
public interface IInvocationPreflight
{
    /// <summary>
    /// Read only: never an effect. The engine asks only when the declared risk would ask the person.
    /// </summary>
    ValueTask<InvocationPreflightResult> PreflightAsync(JsonElement arguments, CancellationToken cancellationToken);

    /// <summary>
    /// Renew al máximo (guarda msconfig, guarda diálogo destructivo): whether this invocation may be riskier than its
    /// declared risk says (an opening that resolves to a tool configuring Windows, the «Sí» under «¿Quieres
    /// reemplazarlo?»). In normal mode the engine then reads it even when the declared risk would not ask, and takes only
    /// the higher risk it finds (<see cref="InvocationPreflightResult.Raised"/>). Pure: nothing is read here.
    /// </summary>
    bool MayRaise(JsonElement arguments) => false;

    /// <summary>
    /// Revisión R2 (H4): the engine is asking the person for this exact invocation now; never on the run their yes starts.
    /// What the yes is for may be resolved only when it runs (a click by its label alone, its window): the handler notes it
    /// here, so the run does not resolve it anew against what the person did since. Read only.
    /// </summary>
    ValueTask NoteAskedAsync(JsonElement arguments, CancellationToken cancellationToken) => ValueTask.CompletedTask;

    /// <summary>
    /// Revisión R2 (H4): this invocation comes with no yes (asked anew after a no, or nothing asks, or Bypass): whatever was
    /// noted when it was last asked for is not what it goes by. Called before its guard reads anything.
    /// </summary>
    void ForgetAsked(JsonElement arguments)
    {
    }
}

/// <summary>What a preflight found: a lower risk for this invocation, the failure it would end in, or neither.</summary>
public sealed record InvocationPreflightResult
{
    private InvocationPreflightResult(OperationRisk? risk, OperationOutcome? failure, JsonElement? facts = null)
    {
        Risk = risk;
        Failure = failure;
        Facts = facts;
    }

    public static InvocationPreflightResult Proceed { get; } = new(null, null);

    /// <summary>This invocation's own risk, below the declared one.</summary>
    public static InvocationPreflightResult Lowered(OperationRisk risk) => new(risk, null);

    /// <summary>Renew al máximo: this invocation's own risk, above the declared one (read when MayRaise).</summary>
    public static InvocationPreflightResult Raised(OperationRisk risk, JsonElement? facts = null) => new(risk, null, facts);

    /// <summary>
    /// The failure the execution would end in before any effect (a terminal failure with nothing done); anything else
    /// is not taken as one.
    /// </summary>
    public static InvocationPreflightResult Fails(OperationOutcome failure) =>
        new(null, failure ?? throw new ArgumentNullException(nameof(failure)));

    public OperationRisk? Risk { get; }

    public OperationOutcome? Failure { get; }

    /// <summary>
    /// Encargo 83: what the read found of a raised invocation, which the challenge carries for the person's question.
    /// </summary>
    public JsonElement? Facts { get; }
}
