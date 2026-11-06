using System.IO;
using System.Net;
using System.Net.Http;
using System.Text;

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

    /// <summary>
    /// The key a local server started with one (llama-server --api-key) asks for, from BAXY_VISION_API_KEY; the request
    /// only ever goes to the loopback endpoint TryResolve accepted.
    /// </summary>
    internal static void Authorize(HttpRequestMessage request)
    {
        string? apiKey = Environment.GetEnvironmentVariable("BAXY_VISION_API_KEY");
        if (!string.IsNullOrWhiteSpace(apiKey))
            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", apiKey);
    }

    /// <summary>
    /// PLAN_GENERAL A5: the server slot a vision question goes to (BAXY_VISION_SLOT), so it never takes the slot that
    /// holds the mind's conversation; null lets the server choose (a server of its own).
    /// </summary>
    internal static int? Slot() =>
        int.TryParse(Environment.GetEnvironmentVariable("BAXY_VISION_SLOT"), out int slot) && slot >= 0 ? slot : null;

    /// <summary>
    /// PLAN_GENERAL A5: where the server sets the slot's state aside around a vision question (its --slot-save-path,
    /// BAXY_VISION_SLOT_DIR); null when the state is not held (a server of its own).
    /// </summary>
    internal static string? SlotDirectory() =>
        Environment.GetEnvironmentVariable("BAXY_VISION_SLOT_DIR") is { Length: > 0 } directory
            && Path.IsPathFullyQualified(directory) ? directory : null;

    // One file per slot: on a server several machines' minds share (encargo 11), each sets its own slot aside.
    private static string HeldFile => $"baxy_vision_hold_{Slot() ?? 0}.bin";

    // The server's slot endpoint for the vision slot (its own address, never another host).
    private static Uri SlotUri(Uri endpoint, string action) => new(endpoint, $"/slots/{Slot() ?? 0}?action={action}");

    /// <summary>
    /// The slot's state written to the server's slot directory, before a question that would evict the mind's
    /// conversation; the file's name, or null when the server did not save it.
    /// </summary>
    internal static async Task<string?> HoldSlotAsync(HttpClient http, Uri endpoint, CancellationToken cancellationToken)
    {
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, SlotUri(endpoint, "save"))
            {
                Content = new StringContent("{\"filename\":\"" + HeldFile + "\"}", Encoding.UTF8, "application/json"),
            };
            Authorize(request);
            using HttpResponseMessage response = await http.SendAsync(request, cancellationToken).ConfigureAwait(false);
            return response.IsSuccessStatusCode ? HeldFile : null;
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException or IOException)
        {
            return null;
        }
    }

    /// <summary>
    /// The slot's state read back, and its file removed: it holds the person's conversation and stays on disk no longer.
    /// </summary>
    internal static async Task PutSlotBackAsync(HttpClient http, Uri endpoint, string file)
    {
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, SlotUri(endpoint, "restore"))
            {
                Content = new StringContent("{\"filename\":\"" + file + "\"}", Encoding.UTF8, "application/json"),
            };
            Authorize(request);
            using HttpResponseMessage response = await http.SendAsync(request, CancellationToken.None).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException or IOException)
        {
            // Not restored: the next decision re-reads the conversation, slower but whole.
        }
        finally
        {
            try
            {
                if (SlotDirectory() is { } directory)
                    File.Delete(Path.Combine(directory, file));
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
            }
        }
    }

    internal static bool IsLoopback(Uri uri) =>
        uri.IsLoopback || (IPAddress.TryParse(uri.DnsSafeHost, out IPAddress? address) && IPAddress.IsLoopback(address));
}
