using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class NamedBrowserAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly string _dataRoot;
    private readonly CdpBrowserSessionContext? _sessionContext;
    private readonly Dictionary<string, CdpBrowserSession> _browsers = new(StringComparer.Ordinal);

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
        if (opera is not null)
            _browsers.Add("opera", opera);
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
        if (browser is not ("opera" or "opera_gx" or "chrome" or "edge" or "brave"))
            return ExternalJson.Failure(operation, "named_browser_invalid");
        // WEB1739: error codes and the post-read authority name the browser family
        // («chrome_not_installed», «edge_cdp_url_postread»), never Opera for another browser.
        string family = browser is "opera" or "opera_gx" ? "opera" : browser;
        string requestedBrowser = browser;
        // WEB1797 «busca operagx en opera»: the person names the Opera family;
        // when plain Opera is absent and Opera GX is installed, the navigation
        // runs in Opera GX and the receipt names the browser actually used.
        // A session already held for «opera» is Opera: it is never redirected
        // (an injected session, or one this adapter opened when Opera resolved).
        if (browser == "opera" && !_browsers.ContainsKey("opera")
            && ResolveBrowser("opera") is null && ResolveBrowser("opera_gx") is not null)
            browser = "opera_gx";
        if (!_browsers.TryGetValue(browser, out CdpBrowserSession? session))
        {
            string? executable = ResolveBrowser(browser);
            if (executable is null)
                return ExternalJson.Failure(operation, family + "_not_installed");
            // La sesion de un navegador con nombre tambien es del equipo, no del
            // turno: vive donde la del navegador por defecto y sobrevive igual.
            session = new CdpBrowserSession(
                WebBrowserAdapter.SharedBrowserProfile(_dataRoot, browser), executable);
            _browsers.Add(browser, session);
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
        _sessionContext?.Activate(session);
        CdpNavigationResult navigation;
        try
        {
            effectBoundary.Cross(cancellationToken);
            navigation = await session.NavigateAsync(target, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, family + "_cdp_unavailable");
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, family + "_cdp_timeout");
        }
        catch (Exception exception) when (exception is IOException or HttpRequestException
            or TimeoutException)
        {
            return effectBoundary.Failure(operation, family + "_cdp_unavailable");
        }
        if (!navigation.Verified)
            return effectBoundary.Failure(
                operation, navigation.ErrorCode, navigation.EffectObserved);
        string? executablePath = session.ObservedExecutablePath;
        if (executablePath is null)
            return effectBoundary.Failure(operation, "named_browser_identity_not_verified", navigation.EffectObserved);
        if (!Uri.TryCreate(navigation.FinalUrl, UriKind.Absolute, out Uri? final)
            || !DestinationMatches(target, final))
            return effectBoundary.Failure(operation, "named_browser_destination_not_verified", navigation.EffectObserved);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("browser", browser);
            writer.WriteString("requestedBrowser", requestedBrowser);
            writer.WriteString("executablePath", executablePath);
            writer.WriteString("finalUrl", navigation.FinalUrl);
            writer.WriteString("targetId", navigation.TargetId);
            writer.WriteString("authority", family + "_cdp_url_postread");
            writer.WriteEndObject();
        }), navigation.EffectObserved);
    }

    public void Dispose()
    {
        foreach (CdpBrowserSession session in _browsers.Values)
        {
            _sessionContext?.Deactivate(session);
            session.Dispose();
        }
        _browsers.Clear();
    }

    private static bool DestinationMatches(Uri requested, Uri observed)
    {
        if (string.Equals(requested.AbsoluteUri, observed.AbsoluteUri, StringComparison.Ordinal))
            return true;
        // WEB1745 «abre youtube.com en Chrome»: a site answers on its canonical host
        // (youtube.com → www.youtube.com/). Same scheme, the same host modulo a
        // leading "www.", no user info and the same path is the same destination;
        // any other host or path (a login page, a redirect elsewhere) is not.
        static string BareHost(string host) =>
            host.StartsWith("www.", StringComparison.OrdinalIgnoreCase) ? host[4..] : host;
        if (requested.Scheme == observed.Scheme
            && string.Equals(BareHost(requested.Host), BareHost(observed.Host), StringComparison.OrdinalIgnoreCase)
            && observed.UserInfo.Length == 0
            && string.Equals(requested.AbsolutePath, observed.AbsolutePath, StringComparison.Ordinal))
            return true;
        // Search may add presentation parameters, but must retain the exact
        // public query on the same results page, never its first result.
        if (requested.Scheme != "https" || requested.Host != "www.bing.com"
            || requested.AbsolutePath != "/search"
            || requested.Scheme != observed.Scheme || requested.Host != observed.Host
            || requested.Port != observed.Port || requested.AbsolutePath != observed.AbsolutePath
            || observed.UserInfo.Length != 0)
            return false;
        var expected = System.Web.HttpUtility.ParseQueryString(requested.Query);
        var actual = System.Web.HttpUtility.ParseQueryString(observed.Query);
        string[]? expectedQuery = expected.GetValues("q");
        string[]? actualQuery = actual.GetValues("q");
        return expected.Count == 1 && expectedQuery is { Length: 1 }
            && actualQuery is { Length: 1 }
            && string.Equals(expectedQuery[0], actualQuery[0], StringComparison.Ordinal);
    }

    private static string? ResolveBrowser(string browser)
    {
        if (browser is "opera" or "opera_gx")
            return ResolveOpera(browser);
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        (string relative, string exe) = browser switch
        {
            "chrome" => (Path.Combine("Google", "Chrome", "Application"), "chrome.exe"),
            "edge" => (Path.Combine("Microsoft", "Edge", "Application"), "msedge.exe"),
            "brave" => (Path.Combine("BraveSoftware", "Brave-Browser", "Application"), "brave.exe"),
            _ => (string.Empty, string.Empty),
        };
        if (exe.Length == 0)
            return null;
        // The install locations Windows itself uses for these browsers (per-machine
        // Program Files editions and the per-user edition), the real binary only:
        // no launcher, no link.
        foreach (string directory in new[]
        {
            Path.Combine(programFiles, relative),
            Path.Combine(programFilesX86, relative),
            Path.Combine(local, relative),
        }.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (!Directory.Exists(directory) || new DirectoryInfo(directory).LinkTarget is not null)
                continue;
            string direct = Path.Combine(directory, exe);
            if (File.Exists(direct) && new FileInfo(direct).LinkTarget is null)
                return direct;
        }
        return null;
    }

    private static string? ResolveOpera(string browser)
    {
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        string edition = browser == "opera_gx" ? "Opera GX" : "Opera";
        foreach (string directory in new[]
        {
            Path.Combine(local, "Programs", edition),
            Path.Combine(programFiles, edition),
            Path.Combine(programFilesX86, edition),
        }.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (!Directory.Exists(directory) || new DirectoryInfo(directory).LinkTarget is not null)
                continue;
            string direct = Path.Combine(directory, "opera.exe");
            if (File.Exists(direct) && new FileInfo(direct).LinkTarget is null)
                return direct;
            // Launch the real browser binary, not launcher.exe whose process
            // identity can disappear before its child owns the CDP session.
            string? versioned = Directory.EnumerateDirectories(directory)
                .Where(path => Version.TryParse(Path.GetFileName(path), out _)
                    && new DirectoryInfo(path).LinkTarget is null)
                .OrderByDescending(path => Version.Parse(Path.GetFileName(path)))
                .Select(path => Path.Combine(path, "opera.exe"))
                .FirstOrDefault(path => File.Exists(path) && new FileInfo(path).LinkTarget is null);
            if (versioned is not null)
                return versioned;
        }
        return null;
    }
}
