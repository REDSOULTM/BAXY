using System.Diagnostics;
using System.Net;
using System.Net.Http;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// fable/estab-wx-clima (tanda n6 t1-c05 «va a llover mañana en valpo?»: el servicio del clima falló a los 2,1 s y la
/// misma pregunta respondió en n5): una lectura de un servicio público que falla pronto por la red (sin respuesta, 5xx,
/// 408 o 429) se pide otra vez tras una pausa breve, una sola vez. Lo que responde a la primera no cambia; un tope del
/// cliente agotado, una respuesta que no es transitoria o el turno cancelado no se reintentan.
/// </summary>
internal static class TransientHttp
{
    internal static readonly TimeSpan Pause = TimeSpan.FromSeconds(1);

    // A failure later than this already spent the turn's time: asking again would only make the honest final later.
    internal static readonly TimeSpan QuickFailure = TimeSpan.FromSeconds(3);

    internal static async Task<string> GetStringAsync(
        Func<string, CancellationToken, Task<string>> fetch, string url, CancellationToken cancellationToken)
    {
        var clock = Stopwatch.StartNew();
        try
        {
            return await fetch(url, cancellationToken).ConfigureAwait(false);
        }
        catch (HttpRequestException exception) when (IsTransient(exception) && clock.Elapsed <= QuickFailure)
        {
            await Task.Delay(Pause, cancellationToken).ConfigureAwait(false);
        }

        return await fetch(url, cancellationToken).ConfigureAwait(false);
    }

    private static bool IsTransient(HttpRequestException exception) =>
        exception.StatusCode is null or HttpStatusCode.RequestTimeout or HttpStatusCode.TooManyRequests
            or >= HttpStatusCode.InternalServerError;
}
