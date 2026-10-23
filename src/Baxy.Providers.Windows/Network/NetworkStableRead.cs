namespace Baxy.Providers.Windows.Network;

/// <summary>
/// Renew al máximo (w5): network.status, network.dns.status and network.ip.list answer only what two reads in a row
/// agree on. Two reads that differed were the answer «verification_failed» at once, so a network that was settling
/// (a Wi-Fi joining, a VPN coming up, an address renewed) had to be asked again by the person. Now a change is read
/// again every 100 ms, six reads at most (about 0.4 s more), and only a network still changing then is no answer.
/// </summary>
public static class NetworkStableRead
{
    internal const int MaximumReads = 6;

    internal static readonly TimeSpan Pause = TimeSpan.FromMilliseconds(100);

    /// <summary>The code of a network that kept changing for every read: the fact the next step needs.</summary>
    public const string ChangedDuringRead = "network_changed_during_read";

    internal static Task Delay(TimeSpan pause, CancellationToken cancellationToken) =>
        Task.Delay(pause, cancellationToken);

    internal static async ValueTask<T?> ReadAsync<T>(
        Func<T> read,
        Func<T, T, bool> same,
        Func<TimeSpan, CancellationToken, Task> delay,
        CancellationToken cancellationToken)
        where T : class
    {
        cancellationToken.ThrowIfCancellationRequested();
        T previous = read();
        for (int reads = 2; reads <= MaximumReads; reads++)
        {
            // The first pair is read back to back, as before; only a change waits before the next read.
            if (reads > 2)
                await delay(Pause, cancellationToken).ConfigureAwait(false);
            cancellationToken.ThrowIfCancellationRequested();
            T current = read();
            if (same(previous, current))
                return current;
            previous = current;
        }

        return null;
    }
}
