using Baxy.Contracts;

namespace Baxy.Core;

/// <summary>
/// The hello waits for the journal check only while the core is still inside
/// <see cref="CoreStartupBudget.HelloJournalWait"/> of its start. A check that
/// fails by then stops the core before its hello, as it always did. A check still
/// running then (a grown live segment on a loaded machine, measured 2026-10-09 at
/// 7.5 to 19.5 s) no longer costs the whole start: the hello goes out, and no
/// request is read until the check has passed, so nothing executes over a
/// journal that was not validated.
/// </summary>
internal static class HelloJournalWait
{
    internal static async Task WithinAsync(
        Task journalOpen,
        TimeSpan elapsedSinceStart,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(journalOpen);
        TimeSpan remaining = CoreStartupBudget.HelloJournalWait - elapsedSinceStart;
        if (remaining < TimeSpan.Zero)
        {
            remaining = TimeSpan.Zero;
        }

        try
        {
            await journalOpen.WaitAsync(remaining, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            // Still validating, or finished just as the budget ran out: either way
            // the core awaits it right after the hello, and a failure stops it there.
        }
    }
}
