using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// M51 (D32): una conversión entre dos divisas la contesta Frankfurter
// (api.frankfurter.dev), abierto y sin clave: tipos de referencia de bancos centrales,
// «no quotas… no monthly or daily caps», uso comercial permitido bajo los términos de
// cada proveedor de tipos. Sale sólo el par de divisas; la cantidad se multiplica aquí,
// y el recibo trae el resultado ya hecho para que la respuesta no calcule nada suyo.
// El «dólar blue» (mercado informal argentino) no es un tipo de referencia: no se
// pregunta aquí.
internal sealed class FrankfurterRateSource(HttpClient http)
{
    internal const string Authority = "frankfurter_reference_rates";
    private const string Endpoint = "https://api.frankfurter.dev/v2/rates";

    private readonly HttpClient _http = http ?? throw new ArgumentNullException(nameof(http));

    internal readonly record struct CurrencyAsk(decimal Amount, string From, string To);

    // Códigos que no son también palabras corrientes («pen», «cop», «try» quedan fuera:
    // el sol y el peso colombiano se nombran por su nombre).
    private static readonly HashSet<string> Codes = new(StringComparer.Ordinal)
    {
        "usd", "eur", "gbp", "jpy", "cad", "aud", "nzd", "chf", "cny", "hkd", "sgd", "krw",
        "inr", "mxn", "clp", "ars", "brl", "uyu", "sek", "nok", "dkk", "pln", "czk", "huf",
        "zar",
    };

    private static readonly HashSet<string> RegionalPesos = new(StringComparer.Ordinal)
    {
        "CLP", "MXN", "ARS", "COP", "UYU", "DOP", "PHP",
    };

    // Las dos divisas nombradas y la primera cantidad escrita. Se convierte desde la
    // divisa que sigue a la cantidad («cuántos pesos son 1.000 dólares»); sin cantidad
    // pegada a una divisa, desde la primera nombrada. Null cuando no nombra dos
    // divisas distintas.
    internal static CurrencyAsk? Parse(string query, RegionInfo region)
    {
        string[] words = WikipediaSearchSource.FoldedWords(query);
        var named = new List<string>();
        int amountAt = Array.FindIndex(words, static word => word.All(char.IsAsciiDigit));
        while (amountAt >= 0 && amountAt + 1 < words.Length && words[amountAt + 1].All(char.IsAsciiDigit)) amountAt++;
        string? amounted = null;
        for (int index = 0; index < words.Length; index++)
        {
            string word = words[index];
            string next = index + 1 < words.Length ? words[index + 1] : string.Empty;
            string previous = index > 0 ? words[index - 1] : string.Empty;
            string? code = word switch
            {
                _ when Codes.Contains(word) => word.ToUpperInvariant(),
                "dolar" or "dolares" or "dollar" or "dollars" => next switch
                {
                    "blue" => "blue",
                    "canadiense" or "canadienses" or "canadian" => "CAD",
                    "australiano" or "australianos" or "australian" => "AUD",
                    _ => previous switch
                    {
                        "canadian" => "CAD",
                        "australian" => "AUD",
                        _ => "USD",
                    },
                },
                "euro" or "euros" => "EUR",
                "libra" or "libras" when next is "esterlina" or "esterlinas" => "GBP",
                "pound" or "pounds" when next == "sterling" || previous == "british" => "GBP",
                "yen" or "yenes" => "JPY",
                "yuan" or "yuanes" or "renminbi" => "CNY",
                "franco" or "francos" when next is "suizo" or "suizos" => "CHF",
                "franc" or "francs" when previous == "swiss" => "CHF",
                "real" or "reales" when next is "brasileno" or "brasilenos" => "BRL",
                "reais" => "BRL",
                "rupia" or "rupias" or "rupee" or "rupees" => "INR",
                "soles" => "PEN",
                "peso" or "pesos" => next switch
                {
                    "mexicano" or "mexicanos" or "mexican" => "MXN",
                    "chileno" or "chilenos" or "chilean" => "CLP",
                    "argentino" or "argentinos" or "argentine" => "ARS",
                    "colombiano" or "colombianos" or "colombian" => "COP",
                    "uruguayo" or "uruguayos" => "UYU",
                    _ => RegionalPesos.Contains(region.ISOCurrencySymbol) ? region.ISOCurrencySymbol : "unknown",
                },
                _ => null,
            };
            if (code is null) continue;
            if (code is "blue" or "unknown") return null;
            if (!named.Contains(code)) named.Add(code);
            if (amountAt >= 0 && index == amountAt + 1) amounted = code;
        }
        if (named.Count != 2) return null;
        string from = amounted ?? named[0];
        return new CurrencyAsk(AmountOf(query), from, named[0] == from ? named[1] : named[0]);
    }

    private static readonly Regex Amount = new(
        @"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])",
        RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(1));

    // «500», «1.000», «1,000», «12,5»: separadores de miles de tres en tres, si no, decimal.
    private static decimal AmountOf(string query)
    {
        Match found = Amount.Match(query);
        if (!found.Success) return 1m;
        string text = found.Value;
        text = Regex.IsMatch(text, @"^\d{1,3}(?:[.,]\d{3})+$", RegexOptions.None, TimeSpan.FromSeconds(1))
            ? text.Replace(".", string.Empty, StringComparison.Ordinal).Replace(",", string.Empty, StringComparison.Ordinal)
            : text.Replace(',', '.');
        return decimal.TryParse(text, NumberStyles.Number, CultureInfo.InvariantCulture, out decimal value) && value > 0
            ? value
            : 1m;
    }

    internal static Uri RateUri(CurrencyAsk ask) =>
        new(Endpoint + "?base=" + ask.From + "&quotes=" + ask.To);

    // Null cuando el servicio no contestó con un tipo del par pedido.
    internal async Task<List<(string Title, string Url, string Snippet)>?> ReadAsync(
        CurrencyAsk ask,
        CancellationToken cancellationToken)
    {
        Uri uri = RateUri(ask);
        using var request = new HttpRequestMessage(HttpMethod.Get, uri);
        request.Headers.TryAddWithoutValidation("User-Agent", WikipediaSearchSource.UserAgent);
        try
        {
            using HttpResponseMessage response = await _http
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode) return null;
            string body = await WebBrowserAdapter.ReadBoundedTextAsync(response, 64_000, cancellationToken)
                .ConfigureAwait(false);
            return Answer(body, ask, uri);
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

    // [{"date":"2026-09-28","base":"CAD","quote":"USD","rate":0.70774}]
    internal static List<(string Title, string Url, string Snippet)>? Answer(string body, CurrencyAsk ask, Uri uri)
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
            string date = Text(row, "date");
            decimal converted = ask.Amount * rate;
            string title = Number(ask.Amount) + " " + ask.From + " = " + Number(converted) + " " + ask.To;
            string snippet = "Reference rate" + (date.Length > 0 ? " on " + date : string.Empty)
                + ": 1 " + ask.From + " = " + rate.ToString("0.######", CultureInfo.InvariantCulture) + " " + ask.To + ".";
            return [(title, uri.AbsoluteUri, snippet)];
        }
        return null;
    }

    private static string Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    // Dos decimales; lo que no llega a una unidad lleva cuatro cifras significativas.
    private static string Number(decimal value) =>
        value >= 1m || value == 0m
            ? decimal.Round(value, 2).ToString("0.##", CultureInfo.InvariantCulture)
            : value.ToString("0.####", CultureInfo.InvariantCulture);
}
