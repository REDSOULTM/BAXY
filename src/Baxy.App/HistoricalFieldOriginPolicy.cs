namespace Baxy.App;

internal static class HistoricalFieldOriginPolicy
{
    internal const string VirtualHost = "baxy.local";
    private const string EntryPath = "/index.html";
    private const string EventPath = "/events";

    internal static string EntryPoint => $"https://{VirtualHost}{EntryPath}";

    internal static bool IsTrustedDocumentSource(string source) =>
        Uri.TryCreate(source, UriKind.Absolute, out Uri? uri)
        && IsTrustedHttpsOrigin(uri)
        && uri.AbsolutePath == EntryPath;

    internal static bool IsTrustedEventSocket(string source) =>
        Uri.TryCreate(source, UriKind.Absolute, out Uri? uri)
        && HasTrustedAuthority(uri)
        && uri.Scheme == "wss"
        && uri.AbsolutePath == EventPath
        && uri.Query.Length == 0
        && uri.Fragment.Length == 0;

    internal static bool ShouldBlockNetworkResource(string source)
    {
        if (!Uri.TryCreate(source, UriKind.Absolute, out Uri? uri))
        {
            return true;
        }

        return uri.Scheme is "http" or "https"
            && !IsTrustedHttpsOrigin(uri);
    }

    private static bool IsTrustedHttpsOrigin(Uri uri) =>
        HasTrustedAuthority(uri)
        && uri.Scheme == Uri.UriSchemeHttps;

    private static bool HasTrustedAuthority(Uri uri) =>
        string.Equals(uri.Host, VirtualHost, StringComparison.OrdinalIgnoreCase)
        && uri.IsDefaultPort
        && uri.UserInfo.Length == 0;
}
