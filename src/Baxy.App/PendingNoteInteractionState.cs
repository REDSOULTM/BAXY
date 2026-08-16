namespace Baxy.App;

internal abstract record PendingNoteInteraction
{
    private PendingNoteInteraction()
    {
    }

    internal sealed record AwaitingChoice(
        PendingNoteChoice Choice,
        PreparedOperation Source) : PendingNoteInteraction;

    internal sealed record ReconcilingSelection(
        PendingSelectedNote Pending) : PendingNoteInteraction;

    internal sealed record ReconcilingTitle(
        PendingTitleNote Pending) : PendingNoteInteraction;
}

internal sealed class PendingNoteInteractionState
{
    internal PendingNoteInteraction? Current { get; private set; }

    internal bool HasPending => Current is not null;

    internal void BeginChoice(
        PendingNoteChoice choice,
        PreparedOperation source)
    {
        ArgumentNullException.ThrowIfNull(choice);
        ArgumentNullException.ThrowIfNull(source);
        if (Current is not null and not PendingNoteInteraction.ReconcilingTitle)
        {
            throw new InvalidOperationException(
                "A note choice cannot replace the current pending interaction.");
        }

        Current = new PendingNoteInteraction.AwaitingChoice(choice, source);
    }

    internal void PromoteToSelection(
        PendingNoteInteraction.AwaitingChoice expected,
        PendingSelectedNote selected)
    {
        ArgumentNullException.ThrowIfNull(expected);
        ArgumentNullException.ThrowIfNull(selected);
        EnsureCurrent(expected);
        Current = new PendingNoteInteraction.ReconcilingSelection(selected);
    }

    internal void RestoreSelection(PendingSelectedNote selected)
    {
        ArgumentNullException.ThrowIfNull(selected);
        EnsureEmpty();
        Current = new PendingNoteInteraction.ReconcilingSelection(selected);
    }

    internal void RestoreTitle(PendingTitleNote title)
    {
        ArgumentNullException.ThrowIfNull(title);
        EnsureEmpty();
        Current = new PendingNoteInteraction.ReconcilingTitle(title);
    }

    internal void ClearChoice(PendingNoteInteraction.AwaitingChoice expected)
    {
        ArgumentNullException.ThrowIfNull(expected);
        EnsureCurrent(expected);
        Current = null;
    }

    internal bool TryClearResolved(PreparedOperation prepared)
    {
        ArgumentNullException.ThrowIfNull(prepared);
        bool matches = Current switch
        {
            PendingNoteInteraction.ReconcilingSelection selected =>
                ReferenceEquals(selected.Pending.Prepared, prepared),
            PendingNoteInteraction.ReconcilingTitle title =>
                ReferenceEquals(title.Pending.Prepared, prepared),
            _ => false,
        };
        if (matches)
        {
            Current = null;
        }

        return matches;
    }

    private void EnsureCurrent(PendingNoteInteraction expected)
    {
        if (!ReferenceEquals(Current, expected))
        {
            throw new InvalidOperationException(
                "The pending note interaction changed before its transition completed.");
        }
    }

    private void EnsureEmpty()
    {
        if (Current is not null)
        {
            throw new InvalidOperationException(
                "A recovered note interaction cannot replace an active interaction.");
        }
    }
}
