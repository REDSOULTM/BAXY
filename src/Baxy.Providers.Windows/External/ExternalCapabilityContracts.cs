using System.Text.Json;
using Baxy.Kernel.Operations;

namespace Baxy.Providers.Windows.External;

public sealed record ExternalCapabilityReceipt(
    string Operation,
    bool EffectObserved,
    bool Verified,
    JsonElement? Result,
    string? ErrorCode)
{
    /// <summary>
    /// True when dispatch crossed an effect boundary but post-dispatch evidence was lost.
    /// This is intentionally separate from <see cref="EffectObserved"/>, which still means
    /// that the adapter obtained positive evidence of the effect.
    /// </summary>
    public bool EffectMayHaveOccurred { get; init; }

    /// <summary>
    /// v3 r6 lectores (t2-r4 c15 «turn bluetooth on» with the radio already on → «could not be observed»): the
    /// verified post-read shows the requested state and nothing had to change, so no boundary was crossed. It is
    /// the request done («ya estaba encendido», changed:false), never an observed effect.
    /// </summary>
    public bool StateAlreadyReached { get; init; }

    /// <summary>
    /// Ronda 19, revisión 2: the session BAXY itself left playing that this playback paused first (changing the way
    /// of playing), and whether it was resumed because the new playback failed before its effect.
    /// </summary>
    public IReadOnlyList<AssistantPlaybackPause> AssistantPlaybackPauses { get; init; } = [];

    /// <summary>
    /// Renew al máximo (guarda diálogo destructivo): a preflight's answer that this exact call needs the person's yes
    /// though its declared risk goes without (the «Sí» of a dialog that asks about replacing a file). Never a failure:
    /// nothing was done, and the call runs as always once the person says yes.
    /// </summary>
    public bool NeedsConfirmation { get; init; }

    /// <summary>
    /// ARR1: the arguments a call the schema takes lacks for what it asks (a places search without its kind), each with
    /// what it takes, refused before anything was sent. The engine refuses them as the kernel's validation does (P5.3).
    /// </summary>
    public IReadOnlyList<ArgumentProblem> ArgumentProblems { get; init; } = [];
}

/// <summary>A media session BAXY paused before a new playback: its source, its title and whether it plays again.</summary>
public sealed record AssistantPlaybackPause(string SourceAppUserModelId, string Title, bool Resumed);

public interface IExternalCapabilityProvider
{
    ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken);

    /// <summary>
    /// Al máximo, flujos: read only, before the person is asked for the call. A receipt that fails before any effect
    /// when the target the call names is not there once (none, or several, with its candidates); null when it is, or
    /// when the operation has no such read. The call itself resolves again.
    /// </summary>
    ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken) =>
        ValueTask.FromResult<ExternalCapabilityReceipt?>(null);

    /// <summary>
    /// Renew al máximo (guarda diálogo destructivo): pure, nothing read. Whether the preflight of this call may find it
    /// needs the person's yes though its declared risk goes without (<see cref="ExternalCapabilityReceipt.NeedsConfirmation"/>);
    /// only then is a call that would go without asking read first.
    /// </summary>
    bool PreflightMayRaise(string operation, JsonElement arguments) => false;

    /// <summary>Revisión R2 (H4): the person is being asked for this call now (IInvocationPreflight.NoteAskedAsync).</summary>
    ValueTask NoteAskedAsync(string operation, JsonElement arguments, CancellationToken cancellationToken) =>
        ValueTask.CompletedTask;

    /// <summary>Revisión R2 (H4): this call runs with no yes (IInvocationPreflight.ForgetAsked).</summary>
    void ForgetAsked(string operation, JsonElement arguments)
    {
    }
}

public sealed record InstalledGameCatalogEntry(
    string Provider,
    string AppId,
    string Name);

public sealed record InstalledGameCatalogSnapshot(
    bool Verified,
    bool Complete,
    IReadOnlyList<InstalledGameCatalogEntry> Entries);
