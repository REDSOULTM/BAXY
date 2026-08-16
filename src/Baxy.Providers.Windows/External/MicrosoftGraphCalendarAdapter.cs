using System.Buffers;
using System.Globalization;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class MicrosoftGraphCalendarAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly HttpClient _http;
    private readonly Func<string?> _token;
    private readonly bool _ownsHttp;

    internal MicrosoftGraphCalendarAdapter()
        : this(new HttpClient { Timeout = TimeSpan.FromSeconds(30) },
            () => Environment.GetEnvironmentVariable("BAXY_GRAPH_ACCESS_TOKEN"), true)
    {
    }

    internal MicrosoftGraphCalendarAdapter(HttpClient http, Func<string?> token, bool ownsHttp = false)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
        _token = token ?? throw new ArgumentNullException(nameof(token));
        _ownsHttp = ownsHttp;
    }

    public bool CanHandle(string operation) => !string.IsNullOrWhiteSpace(_token())
        && operation is "calendar.event.create" or "calendar.event.list";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation, JsonElement arguments, CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            DateTimeOffset start = RequireUtc(arguments, "startUtc");
            DateTimeOffset end = RequireUtc(arguments, "endUtc");
            if (end <= start || end - start > TimeSpan.FromDays(366))
                return ExternalJson.Failure(operation, "calendar_range_invalid");
            return operation == "calendar.event.list"
                ? await ListAsync(operation, start, end, cancellationToken).ConfigureAwait(false)
                : await CreateAsync(operation, ExternalJson.RequiredString(arguments, "title"), start, end,
                    effectBoundary, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "microsoft_graph_calendar_failed");
        }
        catch (Exception exception) when (exception is HttpRequestException or JsonException
            or InvalidDataException or IOException)
        {
            return effectBoundary.Failure(operation, "microsoft_graph_calendar_failed");
        }
    }

    public void Dispose()
    {
        if (_ownsHttp) _http.Dispose();
    }

    private async ValueTask<ExternalCapabilityReceipt> ListAsync(
        string operation, DateTimeOffset start, DateTimeOffset end, CancellationToken token)
    {
        string url = "https://graph.microsoft.com/v1.0/me/calendarView?startDateTime="
            + Uri.EscapeDataString(start.ToString("O")) + "&endDateTime="
            + Uri.EscapeDataString(end.ToString("O"))
            + "&$select=id,subject,start,end&$top=200";
        using JsonDocument response = await SendAsync(HttpMethod.Get, url, null, token)
            .ConfigureAwait(false);
        if (!response.RootElement.TryGetProperty("value", out JsonElement values)
            || values.ValueKind != JsonValueKind.Array)
            return ExternalJson.Failure(operation, "graph_calendar_list_invalid");
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteStartArray("events");
            foreach (JsonElement item in values.EnumerateArray().Take(200)) WriteEvent(writer, item);
            writer.WriteEndArray(); writer.WriteString("authority", "microsoft_graph_calendar_snapshot");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, false);
    }

    private async ValueTask<ExternalCapabilityReceipt> CreateAsync(
        string operation, string title, DateTimeOffset start, DateTimeOffset end,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        string transaction = new Guid(SHA256.HashData(Encoding.UTF8.GetBytes(
            title + "\n" + start.ToString("O") + "\n" + end.ToString("O")))[..16]).ToString();
        var payload = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(payload))
        {
            writer.WriteStartObject(); writer.WriteString("subject", title);
            writer.WriteStartObject("start"); writer.WriteString("dateTime", start.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture)); writer.WriteString("timeZone", "UTC"); writer.WriteEndObject();
            writer.WriteStartObject("end"); writer.WriteString("dateTime", end.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture)); writer.WriteString("timeZone", "UTC"); writer.WriteEndObject();
            writer.WriteString("transactionId", transaction); writer.WriteEndObject();
        }
        using JsonDocument created = await SendAsync(
            HttpMethod.Post, "https://graph.microsoft.com/v1.0/me/events",
            Encoding.UTF8.GetString(payload.WrittenSpan), token, effectBoundary).ConfigureAwait(false);
        string id = created.RootElement.TryGetProperty("id", out JsonElement idValue)
            ? idValue.GetString() ?? string.Empty : string.Empty;
        if (id.Length == 0) return ExternalJson.Failure(operation, "graph_calendar_create_invalid", true);
        using JsonDocument reread = await SendAsync(
            HttpMethod.Get,
            "https://graph.microsoft.com/v1.0/me/events/" + Uri.EscapeDataString(id)
                + "?$select=id,subject,start,end",
            null, token).ConfigureAwait(false);
        if (!Matches(reread.RootElement, title, start, end))
            return ExternalJson.Failure(operation, "graph_calendar_postread_mismatch", true);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); WriteEventFields(writer, reread.RootElement);
            writer.WriteString("authority", "microsoft_graph_calendar_postread"); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, true);
    }

    private async ValueTask<JsonDocument> SendAsync(
        HttpMethod method,
        string url,
        string? body,
        CancellationToken token,
        ExternalEffectBoundary? effectBoundary = null)
    {
        string bearer = _token() ?? throw new InvalidDataException("Graph token is unavailable.");
        using var request = new HttpRequestMessage(method, url);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearer);
        request.Headers.TryAddWithoutValidation("Prefer", "outlook.timezone=\"UTC\"");
        if (body is not null) request.Content = new StringContent(body, Encoding.UTF8, "application/json");
        effectBoundary?.Cross(token);
        using HttpResponseMessage response = await _http.SendAsync(request, token).ConfigureAwait(false);
        if (!response.IsSuccessStatusCode)
            throw new HttpRequestException("Microsoft Graph rejected calendar request.", null, response.StatusCode);
        return await JsonDocument.ParseAsync(
            await response.Content.ReadAsStreamAsync(token).ConfigureAwait(false),
            cancellationToken: token).ConfigureAwait(false);
    }

    private static bool Matches(JsonElement item, string title, DateTimeOffset start, DateTimeOffset end) =>
        string.Equals(item.GetProperty("subject").GetString(), title, StringComparison.Ordinal)
        && ParseGraphTime(item.GetProperty("start")) == start
        && ParseGraphTime(item.GetProperty("end")) == end;

    private static void WriteEvent(Utf8JsonWriter writer, JsonElement item)
    {
        writer.WriteStartObject(); WriteEventFields(writer, item); writer.WriteEndObject();
    }

    private static void WriteEventFields(Utf8JsonWriter writer, JsonElement item)
    {
        writer.WriteString("eventId", "event_" + Convert.ToHexStringLower(SHA256.HashData(
            Encoding.UTF8.GetBytes(item.GetProperty("id").GetString() ?? string.Empty)))[..24]);
        writer.WriteString("title", item.GetProperty("subject").GetString());
        writer.WriteString("startUtc", ParseGraphTime(item.GetProperty("start")).ToString("O"));
        writer.WriteString("endUtc", ParseGraphTime(item.GetProperty("end")).ToString("O"));
    }

    private static DateTimeOffset ParseGraphTime(JsonElement value)
    {
        string text = value.GetProperty("dateTime").GetString() ?? string.Empty;
        string zone = value.GetProperty("timeZone").GetString() ?? string.Empty;
        if (zone != "UTC" || !DateTimeOffset.TryParse(text + (text.EndsWith('Z') ? "" : "Z"), out DateTimeOffset parsed))
            throw new InvalidDataException("Graph calendar timestamp is not canonical UTC.");
        return parsed.ToUniversalTime();
    }

    private static DateTimeOffset RequireUtc(JsonElement arguments, string name)
    {
        string value = ExternalJson.RequiredString(arguments, name);
        if (!DateTimeOffset.TryParse(value, out DateTimeOffset parsed) || parsed.Offset != TimeSpan.Zero)
            throw new InvalidDataException($"{name} must be UTC.");
        return parsed;
    }
}
