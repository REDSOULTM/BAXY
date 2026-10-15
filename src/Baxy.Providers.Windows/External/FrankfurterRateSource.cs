using System.Text.Json;

namespace Baxy.Providers.Windows.External;

// M51 (D32): web.search con source=currency pregunta a Frankfurter (api.frankfurter.dev),
// abierto y sin clave: tipos de referencia de bancos centrales, «no quotas… no monthly or
// daily caps», uso comercial permitido bajo los términos de cada proveedor de tipos. Los
// códigos ISO 4217 y la cantidad los escribe el modelo (from, to, amount); sale sólo el par
// de códigos, la cantidad se multiplica aquí y el recibo trae el tipo, su fecha y el
// resultado tal como salen de la respuesta.
internal sealed class FrankfurterRateSource(HttpClient http)
{
    internal const string Authority = "frankfurter_reference_rates";
    private const string Endpoint = "https://api.frankfurter.dev/v2/rates";

    private readonly HttpClient _http = http ?? throw new ArgumentNullException(nameof(http));

    internal readonly record struct CurrencyAsk(decimal Amount, string From, string To);

    internal readonly record struct Rate(string From, string To, decimal Amount, decimal Value, string Date, decimal Converted);

    internal static Uri RateUri(CurrencyAsk ask) =>
        new(Endpoint + "?base=" + ask.From + "&quotes=" + ask.To);

    // Null cuando el servicio no contestó; vacío cuando contestó sin un tipo del par pedido.
    internal async Task<List<Rate>?> ReadAsync(
        CurrencyAsk ask,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, RateUri(ask));
        request.Headers.TryAddWithoutValidation("User-Agent", WikipediaSearchSource.UserAgent);
        try
        {
            using HttpResponseMessage response = await _http
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode) return null;
            string body = await WebBrowserAdapter.ReadBoundedTextAsync(response, 64_000, cancellationToken)
                .ConfigureAwait(false);
            return Answer(body, ask);
        }
        catch (HttpRequestException)
        {
            return null;
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    // [{"date":"2026-09-28","base":"CAD","quote":"USD","rate":0.70774}]: the row of the pair asked.
    internal static List<Rate>? Answer(string body, CurrencyAsk ask)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        if (document.RootElement.ValueKind != JsonValueKind.Array) return null;
        foreach (JsonElement row in document.RootElement.EnumerateArray())
        {
            if (row.ValueKind != JsonValueKind.Object
                || !row.TryGetProperty("rate", out JsonElement rateElement)
                || !rateElement.TryGetDecimal(out decimal rate) || rate <= 0
                || !string.Equals(Text(row, "base"), ask.From, StringComparison.OrdinalIgnoreCase)
                || !string.Equals(Text(row, "quote"), ask.To, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }
            return [new Rate(ask.From, ask.To, ask.Amount, rate, Text(row, "date"), decimal.Round(ask.Amount * rate, 4))];
        }
        return [];
    }

    private static string Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;
}
