using Baxy.Contracts;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Core;

/// <summary>
/// The hello waits for the installed application catalog only while the core
/// is still inside <see cref="CoreStartupBudget.HelloCatalogWait"/> of its
/// start. A read still running then is not abandoned: it keeps filling the
/// provider's catalog for the operations that need it, and the hello carries
/// the catalog as unverified and incomplete.
/// </summary>
internal static class HelloCatalogWait
{
    internal static async Task<InstalledApplicationCatalogSnapshot> WithinAsync(
        Task<InstalledApplicationCatalogSnapshot> read,
        TimeSpan elapsedSinceStart,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(read);
        TimeSpan remaining = CoreStartupBudget.HelloCatalogWait - elapsedSinceStart;
        if (remaining < TimeSpan.Zero)
        {
            remaining = TimeSpan.Zero;
        }

        try
        {
            return await read.WaitAsync(remaining, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            _ = read.ContinueWith(
                static finished => _ = finished.Exception,
                CancellationToken.None,
                TaskContinuationOptions.OnlyOnFaulted | TaskContinuationOptions.ExecuteSynchronously,
                TaskScheduler.Default);
            return new InstalledApplicationCatalogSnapshot(false, false, Array.Empty<string>());
        }
    }
}
