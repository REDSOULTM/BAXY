using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class NamedBrowserAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly string _dataRoot;
    private readonly CdpBrowserSessionContext? _sessionContext;
    private CdpBrowserSession? _opera;

    internal NamedBrowserAdapter(string dataRoot)
        : this(dataRoot, sessionContext: null)
    {
    }

    internal NamedBrowserAdapter(
        string dataRoot,
        CdpBrowserSessionContext? sessionContext,
        CdpBrowserSession? opera = null)
    {
        _dataRoot = Path.GetFullPath(dataRoot);
        _sessionContext = sessionContext;
        _opera = opera;
    }

    public bool CanHandle(string operation) => operation == "browser.navigate.named";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        string browser;
        try
        {
            browser = ExternalJson.RequiredString(arguments, "browser");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "named_browser_invalid");
        }
        if (browser != "opera")
            return ExternalJson.Failure(operation, "named_browser_invalid");
        if (_opera is null)
        {
            string? executable = ResolveOpera();
            if (executable is null)
                return ExternalJson.Failure(operation, "opera_not_installed");
            _opera = new CdpBrowserSession(
                Path.Combine(_dataRoot, "opera-browser-profile"), executable);
        }
        Uri target;
        try
        {
            target = new Uri(ExternalJson.RequiredString(arguments, "url"), UriKind.Absolute);
            if (target.Scheme is not ("http" or "https"))
                return ExternalJson.Failure(operation, "named_browser_url_invalid");
        }
        catch (Exception exception) when (exception is UriFormatException or InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "named_browser_url_invalid");
        }
        _sessionContext?.Activate(_opera);
        CdpNavigationResult navigation;
        try
        {
            effectBoundary.Cross(cancellationToken);
            navigation = await _opera.NavigateAsync(target, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "opera_cdp_unavailable");
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "opera_cdp_timeout");
        }
        catch (Exception exception) when (exception is IOException or HttpRequestException
            or TimeoutException)
        {
            return effectBoundary.Failure(operation, "opera_cdp_unavailable");
        }
        if (!navigation.Verified)
            return effectBoundary.Failure(
                operation, navigation.ErrorCode, navigation.EffectObserved);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("browser", "opera");
            writer.WriteString("finalUrl", navigation.FinalUrl);
            writer.WriteString("targetId", navigation.TargetId);
            writer.WriteString("authority", "opera_cdp_url_postread");
            writer.WriteEndObject();
        }), navigation.EffectObserved);
    }

    public void Dispose()
    {
        if (_opera is not null)
        {
            _sessionContext?.Deactivate(_opera);
            _opera.Dispose();
        }
    }

    private static string? ResolveOpera()
    {
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        return new[]
        {
            Path.Combine(local, "Programs", "Opera", "opera.exe"),
            Path.Combine(local, "Programs", "Opera", "launcher.exe"),
            Path.Combine(local, "Programs", "Opera GX", "opera.exe"),
            Path.Combine(local, "Programs", "Opera GX", "launcher.exe"),
            Path.Combine(programFiles, "Opera", "opera.exe"),
        }.FirstOrDefault(File.Exists);
    }
}
