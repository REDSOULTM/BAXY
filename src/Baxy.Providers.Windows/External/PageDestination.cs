using System.Net;
using System.Net.Sockets;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// PRIV-05: where a page read on the person's behalf may send a request. It is the rule of the page client's own
/// connection (SearchPageReader.ConnectToPublicAddressAsync: a public name, and every address it resolves to public),
/// for the reader that is a browser and connects by itself, so the rule has to be asked before each of its requests.
/// </summary>
public static class PageDestination
{
    /// <summary>
    /// What the address says by itself, with no lookup: http or https, no credentials, and a host that is a public
    /// address or a name that is not this PC's or a local network's.
    /// </summary>
    public static bool IsPublicByName(Uri address) => SearchPageReader.IsPublicPageAddress(address);

    /// <summary>The same, and its name resolves only to public addresses.</summary>
    public static ValueTask<bool> IsPublicAsync(Uri address, CancellationToken cancellationToken) =>
        IsPublicAsync(address, Dns.GetHostAddressesAsync, cancellationToken);

    /// <summary>The same, with the lookup given (a test's).</summary>
    public static async ValueTask<bool> IsPublicAsync(
        Uri address,
        Func<string, CancellationToken, Task<IPAddress[]>> resolve,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(address);
        ArgumentNullException.ThrowIfNull(resolve);
        if (!SearchPageReader.IsPublicPageAddress(address))
            return false;
        if (address.HostNameType != UriHostNameType.Dns)
            return true;
        try
        {
            IPAddress[] resolved = await resolve(address.IdnHost, cancellationToken).ConfigureAwait(false);
            return SearchPageReader.PublicEndpoint(resolved) is not null;
        }
        catch (Exception exception) when (exception is SocketException or ArgumentException)
        {
            // A name that resolves to nothing goes nowhere: the request is not let through to find out otherwise.
            return false;
        }
    }
}
