using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// M98: reads the page of a search result for SearchPageExcerpt, as a stranger would. The request carries a generic
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

    // Tests answer from their own handler.
    internal SearchPageReader(HttpClient http)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
    }

    public void Dispose()
    {
        if (_ownsClient) _http.Dispose();
    }

    // The page's HTML, or null when it is not a public address, not HTML, not a success or redirects too often.
    internal async Task<string?> ReadHtmlAsync(Uri page, CancellationToken cancellationToken)
    {
        Uri current = page;
        for (int hop = 0; hop <= MaximumRedirects; hop++)
        {
            if (!IsPublicPageAddress(current)) return null;
            using var request = new HttpRequestMessage(HttpMethod.Get, current);
            request.Headers.UserAgent.ParseAdd(UserAgent);
            using HttpResponseMessage response = await _http
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
            if ((int)response.StatusCode is >= 300 and < 400)
            {
                if (response.Headers.Location is not { } location) return null;
                current = location.IsAbsoluteUri ? location : new Uri(current, location);
                continue;
            }
            MediaTypeHeaderValue? type = response.Content.Headers.ContentType;
            if (!response.IsSuccessStatusCode || type?.MediaType is not ("text/html" or "application/xhtml+xml"))
            {
                return null;
            }
            byte[] body = await WebBrowserAdapter.ReadBoundedBytesAsync(response, MaximumBytes, cancellationToken)
                .ConfigureAwait(false);
            return Decode(body, type.CharSet);
        }
        return null;
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

    private static async ValueTask<Stream> ConnectToPublicAddressAsync(
        SocketsHttpConnectionContext context,
        CancellationToken cancellationToken)
    {
        IPAddress[] resolved = await Dns.GetHostAddressesAsync(context.DnsEndPoint.Host, cancellationToken)
            .ConfigureAwait(false);
        IPAddress address = PublicEndpoint(resolved)
            ?? throw new HttpRequestException("The page's host does not resolve to a public address.");
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
