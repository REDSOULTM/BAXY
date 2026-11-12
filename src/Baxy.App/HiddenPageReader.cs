using System.IO;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;
using Baxy.Providers.Windows.External;
using Microsoft.Web.WebView2.Core;

namespace Baxy.App;

/// <summary>
/// SRCH1 (owner, 2026-11-07 17:35): a web search is read by a browser embedded in BAXY and never seen: the WebView2 the
/// App already brings, from the person's machine and address, with no window shown, no focus taken and no sound; never
/// the person's own browser opened in front of them. baxy-core (NativeAOT, which cannot host WebView2's COM objects)
/// starts this mode, «Baxy.exe --hidden-page-reader &lt;folder&gt;», and asks it one JSON line per page:
/// <c>{"url": "https://…", "withinMs": 10000}</c>; it answers one line with what the page answered:
/// <c>{"outcome": "loaded"|"failed"|"timeout"|"unavailable", "httpStatus": 200, "final": "…", "html": "…"}</c>.
/// The window that hosts the view is created and never shown (WindowInteropHelper.EnsureHandle), and the view itself is
/// not visible (CoreWebView2Controller.IsVisible, https://learn.microsoft.com/dotnet/api/microsoft.web.webview2.core.corewebview2controller.isvisible,
/// read 2026-11-07); it opens no other window (NewWindowRequested handled), asks for no permission, downloads nothing,
/// and its sound is muted. The mode ends when its input ends.
/// </summary>
internal static class HiddenPageReader
{
    internal const string Argument = "--hidden-page-reader";
    // No GPU process: nothing is drawn for anyone, and the card is the local model's (the same reason as the CDP
    // browser's --disable-gpu, WebBrowserAdapter.LaunchPlan).
    // PRIV-05, what the view's requests do not show: a WebSocket raises no WebResourceRequested (measured in WebView2
    // 157: with every request of the view asked first, «new WebSocket('ws://127.0.0.1:…')» still reached a server on
    // the loopback, from a real public page too). The browser decides where each scheme goes before it connects, so
    // what is not http or https is sent to a proxy nobody is (the discard port of this PC), and pages are read as
    // before, directly: «other proxies - A list of proxy server identifiers to use for everything else (whatever
    // isn't matched by the other two lists)», a WebSocket takes that list first («If "other proxies" is non-empty use
    // it»), and with one proxy in a list and no direct:// after it «if the proxy server was unreachable all requests
    // would fail with ERR_PROXY_CONNECTION_FAILED». This PC's own addresses skip any proxy unless told otherwise:
    // «adding the special proxy bypass rule <-loopback>. This has the effect of subtracting the implicit rules». A
    // proxy script cannot do it: «Proxy bypass lists only apply to manual settings» (measured: with one, the socket to
    // the loopback still arrived). https://chromium.googlesource.com/chromium/src/+/main/net/docs/proxy.md (read
    // 2026-11-09). The price, decided here: no page read hidden opens a socket, and a PC whose only way out is the
    // system's proxy reads nothing here (the page client's connection already goes only to a public address).
    internal const string BrowserArguments = "--disable-gpu --mute-audio"
        + " --proxy-server=\"http=direct://;https=direct://;socks=http://127.0.0.1:9\" --proxy-bypass-list=\"<-loopback>\"";
    // The page's markup as the reader hands it on, as much as baxy-core reads of an HTTP page (ReadBoundedTextAsync).
    private const int MaximumHtmlChars = 4_000_000;
    private static readonly TimeSpan LongestRead = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan SettleStep = TimeSpan.FromMilliseconds(250);
    // How long the empty page that takes a read page's place may take to arrive before what the page kept is forgotten.
    private static readonly TimeSpan LongestLeave = TimeSpan.FromSeconds(2);
    private const string Nothing = "about:blank";

    internal static bool IsRequested(string[] arguments) =>
        arguments.Length == 2 && arguments[0] == Argument && !string.IsNullOrWhiteSpace(arguments[1]);

    internal static void Start(Application application, string userDataFolder)
    {
        // A window never shown: its handle hosts the view, and nothing of it reaches the screen, the taskbar or the
        // focus.
        var host = new Window
        {
            ShowInTaskbar = false,
            ShowActivated = false,
            WindowStyle = WindowStyle.None,
            ResizeMode = ResizeMode.NoResize,
            Left = -32000,
            Top = -32000,
            Width = 1280,
            Height = 900,
        };
        IntPtr handle = new WindowInteropHelper(host).EnsureHandle();
        application.Dispatcher.BeginInvoke(async () =>
        {
            CoreWebView2Controller? controller = await TryCreateAsync(application, handle, userDataFolder);
            if (controller is not null)
            {
                // What a reader of before this left in the folder (it kept every page's cookies there) goes first.
                await LeaveAsync(controller.CoreWebView2);
            }

            // The lines are read off the window's thread, and each page is read on it (WebView2 answers there).
            _ = Task.Run(() => ServeAsync(application, controller));
        });
    }

    private static async Task<CoreWebView2Controller?> TryCreateAsync(
        Application application, IntPtr handle, string userDataFolder)
    {
        try
        {
            Directory.CreateDirectory(userDataFolder);
            var options = new CoreWebView2EnvironmentOptions(BrowserArguments);
            CoreWebView2Environment environment = await CoreWebView2Environment.CreateAsync(
                browserExecutableFolder: null, userDataFolder, options);
            CoreWebView2Controller controller = await environment.CreateCoreWebView2ControllerAsync(handle);
            controller.IsVisible = false;
            CoreWebView2 view = controller.CoreWebView2;
            KeepInside(view);
            view.ProcessFailed += (_, failed) =>
            {
                if (EndsTheReader(failed.ProcessFailedKind))
                    application.Dispatcher.BeginInvoke(() => application.Shutdown(1));
            };
            KeepPublic(view, environment, Dns.GetHostAddressesAsync);
            return controller;
        }
        catch (Exception exception) when (exception is WebView2RuntimeNotFoundException or IOException
            or UnauthorizedAccessException or System.Runtime.InteropServices.COMException or ArgumentException)
        {
            Console.Error.WriteLine($"hidden page reader unavailable: {exception.GetType().Name}");
            return null;
        }
    }

    /// <summary>
    /// What a page read where nobody sees it may not do: sound, dialogs, other windows, permissions, downloads, and
    /// (revisión de la App 2026-11-09, HPR-2) opening another application. A page that goes to an address whose scheme
    /// Windows gives to a program («ms-settings:», «mailto:», a game's or a chat's own) raises it:
    /// «LaunchingExternalUriScheme is raised when a navigation request is made to a URI scheme that is registered with
    /// the OS», and left alone WebView2 asks in a dialog nobody sees here, or not even that: «The WebView2 may not display
    /// the default dialog based on user settings, browser settings, and whether the origin is determined as a
    /// trustworthy origin» (https://learn.microsoft.com/dotnet/api/microsoft.web.webview2.core.corewebview2.launchingexternalurischeme,
    /// read 2026-11-09). Its Cancel «determines whether to cancel the navigation»: always, here. A download is cancelled
    /// as it starts (CoreWebView2DownloadStartingEventArgs.Cancel, «Indicates whether to cancel the download»,
    /// https://learn.microsoft.com/dotnet/api/microsoft.web.webview2.core.corewebview2downloadstartingeventargs.cancel).
    /// RED2 (2026-11-10), SmartScreen off: for a page off its list of busy sites it was sent the whole address read, query
    /// and fragment, with the page's IP and an id of this PC (measured: «"destination":{"uri":"https://…?red2=uno#…"}» to
    /// nav-edge.smartscreen.microsoft.com). What it guards against is a person on a phishing page or a malicious download
    /// («Microsoft Defender SmartScreen protects against phishing or malware websites and applications, and the
    /// downloading of potentially malicious files», https://learn.microsoft.com/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/,
    /// read 2026-11-10); here nobody sees the page, types in it or gets a download, and only its markup is handed on.
    /// </summary>
    internal static void KeepInside(CoreWebView2 view)
    {
        view.Settings.IsReputationCheckingRequired = false;
        view.IsMuted = true;
        view.Settings.AreDefaultScriptDialogsEnabled = false;
        view.Settings.AreDevToolsEnabled = false;
        view.Settings.IsStatusBarEnabled = false;
        view.Settings.AreDefaultContextMenusEnabled = false;
        view.NewWindowRequested += static (_, asked) => asked.Handled = true;
        view.PermissionRequested += static (_, asked) => asked.State = CoreWebView2PermissionState.Deny;
        view.DownloadStarting += static (_, asked) => asked.Cancel = true;
        view.LaunchingExternalUriScheme += static (_, asked) => asked.Cancel = true;
    }

    private static async Task ServeAsync(Application application, CoreWebView2Controller? controller)
    {
        using var input = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false));
        using var output = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true };
        string? line;
        while ((line = await input.ReadLineAsync()) is not null)
        {
            if (string.IsNullOrWhiteSpace(line))
                continue;
            string answer;
            try
            {
                using JsonDocument asked = JsonDocument.Parse(line);
                JsonElement root = asked.RootElement;
                if (root.TryGetProperty("cmd", out JsonElement command) && command.GetString() is { } name)
                {
                    if (name == "exit")
                        break;
                    answer = name == "ping" ? Ping(controller is not null) : Answer("failed", null, null, null);
                }
                else
                {
                    string url = root.GetProperty("url").GetString() ?? string.Empty;
                    TimeSpan within = root.TryGetProperty("withinMs", out JsonElement ms) && ms.TryGetInt32(out int given)
                        ? TimeSpan.FromMilliseconds(Math.Clamp(given, 500, (int)LongestRead.TotalMilliseconds))
                        : TimeSpan.FromSeconds(10);
                    TimeSpan settle = root.TryGetProperty("settleMs", out JsonElement settleMs)
                        && settleMs.TryGetInt32(out int settleGiven)
                        ? TimeSpan.FromMilliseconds(Math.Clamp(settleGiven, 0, (int)LongestRead.TotalMilliseconds))
                        : TimeSpan.Zero;
                    answer = controller is null || !Uri.TryCreate(url, UriKind.Absolute, out Uri? address)
                        || address.Scheme is not ("http" or "https")
                        ? Answer(controller is null ? "unavailable" : "failed", null, null, null)
                        : await application.Dispatcher.InvokeAsync(() => ReadAsync(controller, address, within, settle)).Task.Unwrap();
                }
            }
            catch (Exception exception) when (exception is JsonException or KeyNotFoundException
                or InvalidOperationException)
            {
                answer = Answer("failed", null, null, null);
            }
            await output.WriteLineAsync(answer);
        }
        await application.Dispatcher.InvokeAsync(() =>
        {
            controller?.Close();
            application.Shutdown(0);
        });
    }

    internal static async Task<string> ReadAsync(
        CoreWebView2Controller controller, Uri address, TimeSpan within, TimeSpan settle)
    {
        CoreWebView2 view = controller.CoreWebView2;
        // Only this page's navigation counts (its redirects keep its id): a page stopped before, still finishing, must
        // not answer for this one (SRCH1, measured: a stopped page's «completed» arrived 0.2 s into the next read).
        ulong? ours = null;
        var arrived = new TaskCompletionSource<CoreWebView2NavigationCompletedEventArgs>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var built = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        void Starting(object? sender, CoreWebView2NavigationStartingEventArgs starting)
        {
            if (ours is null && string.Equals(starting.Uri, address.AbsoluteUri, StringComparison.Ordinal))
                ours = starting.NavigationId;
        }
        void Content(object? sender, CoreWebView2DOMContentLoadedEventArgs loaded)
        {
            if (loaded.NavigationId == ours)
                built.TrySetResult();
        }
        void Completed(object? sender, CoreWebView2NavigationCompletedEventArgs completed)
        {
            if (completed.NavigationId == ours)
                arrived.TrySetResult(completed);
        }
        view.NavigationStarting += Starting;
        view.DOMContentLoaded += Content;
        view.NavigationCompleted += Completed;
        try
        {
            view.Navigate(address.AbsoluteUri);
            bool success;
            int? status = null;
            if (await Task.WhenAny(arrived.Task, Task.Delay(within)) == arrived.Task)
            {
                CoreWebView2NavigationCompletedEventArgs done = await arrived.Task;
                success = done.IsSuccess;
                status = done.HttpStatusCode > 0 ? done.HttpStatusCode : null;
            }
            else if (built.Task.IsCompleted)
            {
                // The document is there and something it loads is still coming (an ad, a stream): what it shows is read.
                success = true;
                view.Stop();
            }
            else
            {
                view.Stop();
                return Answer("timeout", null, null, null);
            }
            // What the page's scripts draw after it arrived: its visible text is read every quarter second until two
            // readings in a row are the same length, or the settle time is up.
            int last = -1;
            for (TimeSpan waited = TimeSpan.Zero; success && waited < settle; waited += SettleStep)
            {
                await Task.Delay(SettleStep);
                int length = JsonSerializer.Deserialize<int>(await view.ExecuteScriptAsync(
                    "document.body ? document.body.innerText.length : 0"));
                if (length > 0 && length == last)
                    break;
                last = length;
            }
            string markup = JsonSerializer.Deserialize<string>(
                await view.ExecuteScriptAsync("document.documentElement ? document.documentElement.outerHTML : ''"))
                ?? string.Empty;
            if (markup.Length > MaximumHtmlChars)
                markup = markup[..MaximumHtmlChars];
            return Answer(success ? "loaded" : "failed", status, view.Source, markup);
        }
        catch (Exception exception) when (exception is JsonException or InvalidOperationException
            or System.Runtime.InteropServices.COMException)
        {
            return Answer("failed", null, null, null);
        }
        finally
        {
            view.NavigationStarting -= Starting;
            view.DOMContentLoaded -= Content;
            view.NavigationCompleted -= Completed;
            await LeaveAsync(view);
        }
    }

    /// <summary>
    /// REV_APP HPR-1 (2026-11-09): a page that was read is left. It stayed loaded until the next read or the reader's end
    /// (ten minutes with nothing to read, HiddenPageReaderHost.IdleEnd) with its scripts running and asking the network
    /// (Stop «Does not stop scripts», https://learn.microsoft.com/dotnet/api/microsoft.web.webview2.core.corewebview2.stop,
    /// read 2026-11-09; measured on a loopback page that asks ten times a second: it went on asking after it was read),
    /// and the cookie and the storage it kept went with the next read and stayed in the folder from one search to the
    /// next, while the page read without a browser keeps none (SearchPageReader: «one search is never tied to the next by
    /// what a service set»). An empty page takes its place and the profile's site data is forgotten:
    /// ClearBrowsingDataAsync(AllSite), «all site data … inclusive of AllDomStorage and Cookies»
    /// (https://learn.microsoft.com/dotnet/api/microsoft.web.webview2.core.corewebview2browsingdatakinds, read 2026-11-09).
    /// SIS1 (REV10 M1): AllSite keeps the browsing history and the disk cache, so the address of every search read (the
    /// person's words, their city) stayed in the folder. What is forgotten is <see cref="Forgotten"/>.
    /// </summary>
    /// <summary>
    /// SIS1 (REV10 M1): what a page that was read leaves behind and is forgotten: its site data (AllSite), «disk cache»
    /// (DiskCache) and «browsing history data» (BrowsingHistory), which AllSite does not include; only AllProfile, its own
    /// value, does (https://learn.microsoft.com/dotnet/api/microsoft.web.webview2.core.corewebview2browsingdatakinds,
    /// read 2026-11-11). The reader keeps no download, autofill, password nor setting of the person's.
    /// </summary>
    internal const CoreWebView2BrowsingDataKinds Forgotten = CoreWebView2BrowsingDataKinds.AllSite
        | CoreWebView2BrowsingDataKinds.DiskCache | CoreWebView2BrowsingDataKinds.BrowsingHistory;

    /// <summary>
    /// SIS1 (REV10 M1): «Olvidar todo» left the reader's folder (the Core's, «webview2-search» in the data root,
    /// HiddenPageReaderHost) as it was. It is emptied too; links are not followed. A file a reader still running holds
    /// (it ends after a while unused) stays, and is said on stderr: that reader made its profile look new as it left
    /// each page (<see cref="Forgotten"/>). Returns how many entries stayed.
    /// </summary>
    internal static int Forget(string dataRoot)
    {
        var root = new DirectoryInfo(Path.Combine(dataRoot, FolderName));
        if (!root.Exists || root.Attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            return 0;
        }

        int stayed = 0;
        foreach (FileSystemInfo entry in root.EnumerateFileSystemInfos())
        {
            try
            {
                if (entry is DirectoryInfo directory && !entry.Attributes.HasFlag(FileAttributes.ReparsePoint))
                {
                    directory.Delete(recursive: true);
                }
                else
                {
                    entry.Delete();
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                stayed++;
            }
        }

        if (stayed > 0)
        {
            Console.Error.WriteLine($"hidden page reader folder: {stayed} entries held by a running reader stayed");
        }

        return stayed;
    }

    /// <summary>The reader's folder in the data root, as HiddenPageReaderHost names it.</summary>
    internal const string FolderName = "webview2-search";

    private static async Task LeaveAsync(CoreWebView2 view)
    {
        ulong? ours = null;
        var left = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        void Starting(object? sender, CoreWebView2NavigationStartingEventArgs starting)
        {
            if (ours is null && string.Equals(starting.Uri, Nothing, StringComparison.Ordinal))
                ours = starting.NavigationId;
        }
        void Completed(object? sender, CoreWebView2NavigationCompletedEventArgs completed)
        {
            if (completed.NavigationId == ours)
                left.TrySetResult();
        }
        view.NavigationStarting += Starting;
        view.NavigationCompleted += Completed;
        try
        {
            view.Stop();
            view.Navigate(Nothing);
            // The page is gone when the empty one arrived: only then can it keep nothing more.
            await Task.WhenAny(left.Task, Task.Delay(LongestLeave));
            await view.Profile.ClearBrowsingDataAsync(Forgotten);
        }
        catch (Exception exception) when (exception is InvalidOperationException or NotImplementedException
            or System.Runtime.InteropServices.COMException)
        {
            // The view closed (its browser ended: the reader ends too, EndsTheReader), or a WebView2 from before this.
            Console.Error.WriteLine($"hidden page reader could not leave the page: {exception.GetType().Name}");
        }
        finally
        {
            view.NavigationStarting -= Starting;
            view.NavigationCompleted -= Completed;
        }
    }

    /// <summary>
    /// PRIV-05 (revisión de privacidad 2026-11-09): this reader is a browser and connects by itself, so the rule of the
    /// page client's connection (SearchPageReader.ConnectToPublicAddressAsync: only a public address) did not hold
    /// here. A page could send it into this PC or the local network: measured in a real WebView2 157, a fetch, an image,
    /// a frame, a worker, a redirect and a script's navigation all reached a server on the loopback, and a page that
    /// redirected there was given as read. Every request of the view is asked first where it goes: «A web resource
    /// request with a resource context that matches this filter's resource context and a URI that matches this
    /// filter's URI wildcard string for corresponding request sources will be raised via the WebResourceRequested
    /// event» (the two-argument filter «is deprecated and does not behave as expected for iframes»), and «If a deferral
    /// is taken, then the web resource requested is blocked until the deferral is completed»: the time the name takes
    /// to resolve. One that is not public is answered here, with nothing, and never leaves. A navigation is stopped
    /// before it starts on what its address says by itself, the page's or a frame's: «Redirects raise this event as
    /// well», and with Cancel «the navigation is no longer present and the content of the current page is intact».
    /// https://learn.microsoft.com/dotnet/api/microsoft.web.webview2.core.corewebview2.addwebresourcerequestedfilter,
    /// .../corewebview2.webresourcerequested, .../corewebview2.navigationstarting and
    /// .../corewebview2navigationstartingeventargs.cancel (read 2026-11-09, pages of 2026-11-03).
    /// </summary>
    internal static void KeepPublic(
        CoreWebView2 view,
        CoreWebView2Environment environment,
        Func<string, CancellationToken, Task<IPAddress[]>> resolve)
    {
        Dispatcher here = Dispatcher.CurrentDispatcher;
        view.AddWebResourceRequestedFilter(
            "*", CoreWebView2WebResourceContext.All, CoreWebView2WebResourceRequestSourceKinds.All);
        view.WebResourceRequested += (_, asked) =>
        {
            if (!MayStart(asked.Request.Uri))
            {
                asked.Response = Refusal(environment);
                return;
            }
            var address = new Uri(asked.Request.Uri);
            if (address.HostNameType != UriHostNameType.Dns)
                return;
            CoreWebView2Deferral held = asked.GetDeferral();
            _ = AnswerAsync();

            async Task AnswerAsync()
            {
                bool goes = false;
                try
                {
                    goes = await PageDestination.IsPublicAsync(address, resolve, CancellationToken.None)
                        .ConfigureAwait(false);
                }
                finally
                {
                    // On the view's thread, and refused when the answer never came.
                    await here.InvokeAsync(() =>
                    {
                        try
                        {
                            if (!goes)
                                asked.Response = Refusal(environment);
                            held.Complete();
                        }
                        catch (Exception exception) when (exception is InvalidOperationException
                            or System.Runtime.InteropServices.COMException)
                        {
                            // The view closed while the name was being resolved: there is no request to answer.
                        }
                    });
                }
            }
        };
        view.NavigationStarting += static (_, starting) => starting.Cancel |= !MayStart(starting.Uri);
        view.FrameNavigationStarting += static (_, starting) => starting.Cancel |= !MayStart(starting.Uri);
    }

    // What an address says by itself, before anything is asked: a public web address, or content the page already
    // holds (about:, data:, blob:), which goes nowhere. Anything else (this PC, the local network, a file, what is not
    // an address) does not start.
    internal static bool MayStart(string uri) =>
        Uri.TryCreate(uri, UriKind.Absolute, out Uri? address)
        && (address.Scheme is "about" or "data" or "blob" || PageDestination.IsPublicByName(address));

    private static CoreWebView2WebResourceResponse Refusal(CoreWebView2Environment environment) =>
        environment.CreateWebResourceResponse(null, 403, "Forbidden", string.Empty);

    // INT10: a browser process that ended leaves the view closed for good: «The WebView automatically moves to the Closed
    // state. The app has to recreate a new WebView to recover» (CoreWebView2ProcessFailedKind.BrowserProcessExited,
    // https://learn.microsoft.com/dotnet/api/microsoft.web.webview2.core.corewebview2processfailedkind, read 2026-11-07).
    // Measured: every page then answered «failed» at once, with the reader alive, so the Core never replaced it. The
    // reader ends, and the Core starts another on the next page (HiddenPageReaderHost.EnsureStartedAsync). A render
    // process that ended is made again by the view's next navigation («A new render process is created automatically»).
    internal static bool EndsTheReader(CoreWebView2ProcessFailedKind kind) =>
        kind == CoreWebView2ProcessFailedKind.BrowserProcessExited;

    private static string Ping(bool ready)
    {
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteBoolean("ok", ready);
            writer.WriteEndObject();
        }
        return Encoding.UTF8.GetString(buffer.ToArray());
    }

    internal static string Answer(string outcome, int? status, string? final, string? html)
    {
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("outcome", outcome);
            if (status is { } code)
                writer.WriteNumber("httpStatus", code);
            if (final is not null)
                writer.WriteString("final", final);
            writer.WriteString("html", html ?? string.Empty);
            writer.WriteEndObject();
        }
        return Encoding.UTF8.GetString(buffer.ToArray());
    }
}
