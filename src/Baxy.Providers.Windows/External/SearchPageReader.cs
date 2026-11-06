using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// M98: reads a public page for web.fetch, as a stranger would. The request carries a generic
// User-Agent and nothing else: no cookie is kept or sent, no referrer, nothing of the person. Only a public web address
// is read: http or https, a public host name, never this PC, the local network or a link-local, carrier-grade NAT
// (Tailscale) or multicast address. Each redirect is checked again before it is followed, and the production client
// connects only to the public addresses its host name resolves to, so a name that points into the LAN is not read
// either. The page's text is decoded in the charset its response or its own <meta> declares.
internal sealed class SearchPageReader : IDisposable
{
    private const string UserAgent = "BAXY/1.0 page-read";
    private const int MaximumRedirects = 3;
    private const int MaximumBytes = 1_500_000;
    private const int CharsetSniffBytes = 2_048;

    private readonly HttpClient _http;
    private readonly bool _ownsClient;

    internal SearchPageReader()
    {
        _http = new HttpClient(new SocketsHttpHandler
        {
            UseCookies = false,
            AllowAutoRedirect = false,
            AutomaticDecompression = DecompressionMethods.All,
            ConnectCallback = ConnectToPublicAddressAsync,
        })
        { Timeout = TimeSpan.FromSeconds(10) };
        _ownsClient = true;
    }

    // The connection of the clients that ask public services for the person's search, weather or place (the search
    // sources, the place by this PC's address, the weather and a place's time zone). Renew al máximo (auditoría de
    // flujos): no cookie is kept or sent back, so one search is never tied to the next by what a service set.
    internal static SocketsHttpHandler StrangerHandler() => new()
    {
        UseCookies = false,
        AutomaticDecompression = DecompressionMethods.All,
    };

    // Tests answer from their own handler.
    internal SearchPageReader(HttpClient http)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
    }

    public void Dispose()
    {
        if (_ownsClient) _http.Dispose();
    }

    // A page read: its HTML with the address it was finally read from (after its checked redirects) and whether its
    // body went past the bound; or, with no HTML, why: a redirect to an address that is not public, a redirect without
    // a target, too many redirects, a status other than success, or content that is not HTML.
    internal sealed record PageRead(Uri? Final, string? Html, bool Truncated, string? Error)
    {
        internal static PageRead Failed(string error) => new(null, null, false, error);
    }

    internal async Task<PageRead> ReadPageAsync(Uri page, CancellationToken cancellationToken)
    {
        Uri current = page;
        for (int hop = 0; hop <= MaximumRedirects; hop++)
        {
            if (!IsPublicPageAddress(current)) return PageRead.Failed("web_fetch_redirect_not_public");
            using var request = new HttpRequestMessage(HttpMethod.Get, current);
            request.Headers.UserAgent.ParseAdd(UserAgent);
            using HttpResponseMessage response = await _http
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
            if ((int)response.StatusCode is >= 300 and < 400)
            {
                if (response.Headers.Location is not { } location) return PageRead.Failed("web_fetch_redirect_without_target");
                current = location.IsAbsoluteUri ? location : new Uri(current, location);
                continue;
            }
            if (!response.IsSuccessStatusCode)
                return PageRead.Failed("web_fetch_status_" + ((int)response.StatusCode).ToString(System.Globalization.CultureInfo.InvariantCulture));
            MediaTypeHeaderValue? type = response.Content.Headers.ContentType;
            if (type?.MediaType is not ("text/html" or "application/xhtml+xml"))
                return PageRead.Failed("web_fetch_not_html");
            // Renew al máximo (auditoría de flujos): the client's timeout covers only the headers; the body gets as long
            // again, so a page that trickles ends as one that took too long, not at the operation's own deadline.
            using var bodyDeadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            bodyDeadline.CancelAfter(_http.Timeout);
            (byte[] body, bool truncated) = await WebBrowserAdapter.ReadBoundedBytesAsync(
                response, MaximumBytes, bodyDeadline.Token).ConfigureAwait(false);
            return new PageRead(current, Decode(body, type.CharSet), truncated, null);
        }
        return PageRead.Failed("web_fetch_too_many_redirects");
    }

    // Encargo 35 (banco de uso, U31): the status a public page answers with, asked as a stranger reads it (HEAD: no body,
    // no cookie, nothing of the person; each redirect checked as a read's), so a navigation that reached an address can
    // say its site answered 404 (Playwright's page.goto does not fail on 404 either: its response.status() says it). Null
    // when it could not be asked: not a public address, no redirect target, too many redirects, no answer in time, or a
    // connection that failed for another reason than a host name that does not exist.
    // Encargo 70 (uso real 03-11, F7): a guessed address whose host name does not exist showed the browser's own error
    // page and was told as a navigation verified. A name the DNS says does not exist (WSAHOST_NOT_FOUND, or WSANO_DATA: a
    // valid name with no address) is told as such (PageStatus.NoSuchHost). SocketsHttpHandler throws the SocketException
    // inside an HttpRequestException (ConnectHelper.CreateWrappedException), so its code is read there: its HttpRequestError
    // does not tell them apart (NameResolutionError covers HostNotFound and TryAgain, NoData is ConnectionError). WSATRY_AGAIN
    // (no authoritative answer: a DNS server down, no network) says nothing of the site and stays null.
    internal async Task<PageStatus?> StatusAsync(Uri page, CancellationToken cancellationToken)
    {
        Uri current = page;
        int hop = 0;
        try
        {
            for (; hop <= MaximumRedirects; hop++)
            {
                if (!IsPublicPageAddress(current)) return null;
                using var request = new HttpRequestMessage(HttpMethod.Head, current);
                request.Headers.UserAgent.ParseAdd(UserAgent);
                using HttpResponseMessage response = await _http
                    .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                    .ConfigureAwait(false);
                int status = (int)response.StatusCode;
                if (status is < 300 or >= 400) return PageStatus.Answered(status);
                if (response.Headers.Location is not { } location) return null;
                current = location.IsAbsoluteUri ? location : new Uri(current, location);
            }
        }
        // Only the page's own host: a redirect to a name that does not exist is another site's fault, not this address's.
        catch (HttpRequestException exception) when (hop == 0 && IsNoSuchHost(exception))
        {
            return PageStatus.NoSuchHost;
        }
        catch (Exception exception) when (exception is HttpRequestException or IOException
            || (exception is OperationCanceledException && !cancellationToken.IsCancellationRequested))
        {
            return null;
        }
        return null;
    }

    private static bool IsNoSuchHost(HttpRequestException exception) =>
        exception.InnerException is SocketException { SocketErrorCode: SocketError.HostNotFound or SocketError.NoData };

    // What asking a page's status found: the HTTP status its site answered (Code), or that no site answers at its host
    // name because the DNS says that name does not exist (HostNotFound, with no Code).
    internal sealed record PageStatus(int? Code, bool HostNotFound)
    {
        internal static readonly PageStatus NoSuchHost = new(null, true);

        internal static PageStatus Answered(int code) => new(code, false);
    }

    internal static bool IsPublicPageAddress(Uri address)
    {
        if (!address.IsAbsoluteUri || address.Scheme is not ("http" or "https") || address.UserInfo.Length > 0)
            return false;
        if (address.HostNameType is UriHostNameType.IPv4 or UriHostNameType.IPv6)
            return IPAddress.TryParse(address.DnsSafeHost, out IPAddress? literal) && IsPublicAddress(literal);
        if (address.HostNameType != UriHostNameType.Dns) return false;
        string host = address.IdnHost.TrimEnd('.').ToLowerInvariant();
        return host.Contains('.', StringComparison.Ordinal)
            && !LocalSuffixes.Any(suffix => host == suffix[1..] || host.EndsWith(suffix, StringComparison.Ordinal));
    }

    private static readonly string[] LocalSuffixes =
        [".localhost", ".local", ".lan", ".home", ".internal", ".intranet", ".corp", ".home.arpa", ".ts.net"];

    internal static bool IsPublicAddress(IPAddress address)
    {
        if (address.IsIPv4MappedToIPv6) address = address.MapToIPv4();
        if (IPAddress.IsLoopback(address)) return false;
        if (address.AddressFamily == AddressFamily.InterNetwork)
        {
            byte[] b = address.GetAddressBytes();
            return !(b[0] is 0 or 10 or 127 or >= 224
                || (b[0] == 100 && b[1] >= 64 && b[1] <= 127)
                || (b[0] == 169 && b[1] == 254)
                || (b[0] == 172 && b[1] >= 16 && b[1] <= 31)
                || (b[0] == 192 && b[1] == 168)
                || (b[0] == 192 && b[1] == 0 && b[2] is 0 or 2)
                || (b[0] == 198 && b[1] is 18 or 19)
                || (b[0] == 198 && b[1] == 51 && b[2] == 100)
                || (b[0] == 203 && b[1] == 0 && b[2] == 113));
        }
        if (address.AddressFamily == AddressFamily.InterNetworkV6)
        {
            byte[] b = address.GetAddressBytes();
            return !(address.Equals(IPAddress.IPv6None) || address.IsIPv6LinkLocal || address.IsIPv6SiteLocal
                || address.IsIPv6Multicast || address.IsIPv6UniqueLocal
                || (b[0] == 0x20 && b[1] == 0x01 && b[2] == 0x0d && b[3] == 0xb8)
                || b.Take(12).All(static part => part == 0));
        }
        return false;
    }

    // The address a host name may be read at: one of the public ones it resolves to, or none when any of them is not
    // public (a name that also answers with a LAN address is not trusted with either).
    internal static IPAddress? PublicEndpoint(IReadOnlyList<IPAddress> resolved) =>
        resolved.Count > 0 && resolved.All(IsPublicAddress) ? resolved[0] : null;

    // The connection refused because the host resolves to an address that is not public (the cause of the
    // HttpRequestException the client throws), told apart from a page that could not be reached.
    internal sealed class AddressNotPublicException() : IOException("not a public address");

    internal static async ValueTask<Stream> ConnectToPublicAddressAsync(
        SocketsHttpConnectionContext context,
        CancellationToken cancellationToken)
    {
        IPAddress[] resolved = await Dns.GetHostAddressesAsync(context.DnsEndPoint.Host, cancellationToken)
            .ConfigureAwait(false);
        IPAddress address = PublicEndpoint(resolved)
            ?? throw new HttpRequestException(
                "The page's host does not resolve to a public address.", new AddressNotPublicException());
        var socket = new Socket(address.AddressFamily, SocketType.Stream, ProtocolType.Tcp) { NoDelay = true };
        try
        {
            await socket.ConnectAsync(new IPEndPoint(address, context.DnsEndPoint.Port), cancellationToken)
                .ConfigureAwait(false);
            return new NetworkStream(socket, ownsSocket: true);
        }
        catch
        {
            socket.Dispose();
            throw;
        }
    }

    private static readonly Regex MetaCharset = new(
        @"<meta\b[^>]*?charset\s*=\s*[""']?\s*(?<name>[A-Za-z0-9_\-:.]+)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, TimeSpan.FromSeconds(1));

    // The charset of the response, else the one the page's first bytes declare (<meta charset> or http-equiv), else
    // UTF-8. Latin-1 and ASCII labels are read as Windows-1252, as browsers do.
    internal static string Decode(byte[] body, string? headerCharset)
    {
        string? label = Clean(headerCharset);
        if (label is null)
        {
            string head = Encoding.Latin1.GetString(body, 0, Math.Min(body.Length, CharsetSniffBytes));
            try
            {
                Match declared = MetaCharset.Match(head);
                label = declared.Success ? Clean(declared.Groups["name"].Value) : null;
            }
            catch (RegexMatchTimeoutException)
            {
                label = null;
            }
        }
        return EncodingOf(label).GetString(body);
    }

    private static string? Clean(string? label)
    {
        string? cleaned = label?.Trim().Trim('"', '\'').Trim().ToLowerInvariant();
        return string.IsNullOrEmpty(cleaned) ? null : cleaned;
    }

    private static Encoding EncodingOf(string? label)
    {
        if (label is null) return Encoding.UTF8;
        if (label is "iso-8859-1" or "iso8859-1" or "latin1" or "l1" or "us-ascii" or "ascii" or "windows-1252"
            or "cp1252" or "x-cp1252")
        {
            return CodePagesEncodingProvider.Instance.GetEncoding(1252) ?? Encoding.Latin1;
        }
        try
        {
            return Encoding.GetEncoding(label);
        }
        catch (ArgumentException)
        {
            return CodePagesEncodingProvider.Instance.GetEncoding(label) ?? Encoding.UTF8;
        }
    }
}
