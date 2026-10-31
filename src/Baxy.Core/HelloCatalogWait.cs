using Baxy.Contracts;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Core;

/// <summary>
/// The hello waits for the installed application catalog only while the core
/// is still inside <see cref="CoreStartupBudget.HelloCatalogWait"/> of its
/// start. A read still running then is not abandoned: it keeps filling the
/// provider's catalog for the operations that need it, the hello carries the
/// list the last verified read kept (or none, unverified, on a first start),
/// and the read is sent to the App when it ends (<see cref="LateUpdate"/>).
/// </summary>
internal static class HelloCatalogWait
{
    private static readonly InstalledApplicationCatalogSnapshot None = new(false, false, Array.Empty<string>());

    internal static async Task<InstalledApplicationCatalogSnapshot> WithinAsync(
        Task<InstalledApplicationCatalogSnapshot> read,
        TimeSpan elapsedSinceStart,
        Func<InstalledApplicationCatalogSnapshot?> kept,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(read);
        ArgumentNullException.ThrowIfNull(kept);
        TimeSpan remaining = CoreStartupBudget.HelloCatalogWait - elapsedSinceStart;
        if (remaining < TimeSpan.Zero)
        {
            remaining = TimeSpan.Zero;
        }

        try
        {
            InstalledApplicationCatalogSnapshot live = await read.WaitAsync(remaining, cancellationToken).ConfigureAwait(false);
            return live.Verified ? live : kept() ?? live;
        }
        catch (TimeoutException)
        {
            _ = read.ContinueWith(
                static finished => _ = finished.Exception,
                CancellationToken.None,
                TaskContinuationOptions.OnlyOnFaulted | TaskContinuationOptions.ExecuteSynchronously,
                TaskScheduler.Default);
            return kept() ?? None;
        }
    }

    /// <summary>
    /// Ajuste c3 (humos del 31-10): what the App is sent once the read ends after the hello: the read, when it is
    /// verified and says other names than the hello did; otherwise nothing.
    /// </summary>
    internal static InstalledApplicationCatalogSnapshot? LateUpdate(
        InstalledApplicationCatalogSnapshot sent,
        InstalledApplicationCatalogSnapshot live) =>
        live.Verified && (!sent.Verified || sent.Complete != live.Complete || !sent.Names.SequenceEqual(live.Names, StringComparer.Ordinal))
            ? live
            : null;
}
