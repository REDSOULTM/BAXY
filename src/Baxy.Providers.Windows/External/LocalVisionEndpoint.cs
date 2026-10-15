using System.Net;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The vision model that reads a capture, only when it runs on this PC: a loopback endpoint (a local multimodal
/// llama-server, for example). A capture is the person's screen, and nothing of the person leaves the machine
/// (identity; BAXY Renew audit 2026-10-15: the endpoint was accepted only over https, that is, a remote service).
/// </summary>
internal static class LocalVisionEndpoint
{
    internal static bool TryResolve(out Uri endpoint, out string model)
    {
        endpoint = null!;
        model = Environment.GetEnvironmentVariable("BAXY_VISION_MODEL") ?? string.Empty;
        if (string.IsNullOrWhiteSpace(model)
            || !Uri.TryCreate(Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT"), UriKind.Absolute, out Uri? uri)
            || uri.Scheme is not ("http" or "https")
            || !IsLoopback(uri))
        {
            return false;
        }

        endpoint = uri;
        return true;
    }

    internal static bool IsLoopback(Uri uri) =>
        uri.IsLoopback || (IPAddress.TryParse(uri.DnsSafeHost, out IPAddress? address) && IPAddress.IsLoopback(address));
}
