using System.ComponentModel;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.IO;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using Baxy.App.Presentation;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;

namespace Baxy.App;

[SuppressMessage(
    "Design",
    "CA1001:Types that own disposable fields should be disposable",
    Justification = "WPF owns the Window lifetime; OnClosing releases every local resource.")]
public partial class MainWindow : Window
{
    private readonly MainWindowViewModel _viewModel;
    private readonly CancellationTokenSource _lifetimeCancellation = new();
    private readonly AppSurfaceNavigator _surfaceNavigator;
    private readonly MainWindowSurfacePresenter _surfacePresenter;
    // uso-116: the view recreated after its browser process died, with a growing wait; the same death again and again is
    // said and no longer retried. Counted anew once a view stayed up (StartupRetries.Stable).
    private readonly StartupRetries _fieldRetries = new();
    private bool _recreatingField;
    private readonly PresenceHost? _presence;
    private FieldUiBridge? _bridge;
    private AppSurfaceSession? _fieldNavigationLoadingSession;
    private int _fieldActivityRevision;
    private bool _closing;
    private bool _disposed;

    public MainWindow()
        : this(presence: null)
    {
    }

    internal MainWindow(PresenceHost? presence)
    {
        InitializeComponent();
        // Steam (2026-11-04): what a screen reader says of the window, in the interface's language at the start.
        bool english = UiLanguage.IsEnglish;
        AutomationProperties.SetName(this, UiLanguage.Say(english, "BAXY, asistente local", "BAXY, local assistant"));
        AutomationProperties.SetName(FieldWebView,
            UiLanguage.Say(english, "BAXY Field, interfaz local", "BAXY Field, local interface"));
        AutomationProperties.SetName(AppSurfaceLayer,
            UiLanguage.Say(english, "Superficie nativa de BAXY", "BAXY native surface"));
        Rect initialBounds = FitInitialBounds(
            new Size(Width, Height),
            new Size(MinWidth, MinHeight),
            SystemParameters.WorkArea);
        WindowStartupLocation = WindowStartupLocation.Manual;
        Width = initialBounds.Width;
        Height = initialBounds.Height;
        Left = initialBounds.Left;
        Top = initialBounds.Top;
        _presence = presence;
        _viewModel = new MainWindowViewModel();
        _surfacePresenter = new MainWindowSurfacePresenter(FieldWebView, AppSurfaceLayer);
        _surfaceNavigator = new AppSurfaceNavigator(AppSurfaceCatalog.CreateDefault(), _surfacePresenter);
        StateChanged += OnWindowPresentationChanged;
        IsVisibleChanged += OnWindowVisibilityChanged;
        _presence?.Attach(this, _viewModel);
    }

    internal static Rect FitInitialBounds(
        Size desired,
        Size minimum,
        Rect workArea)
    {
        const double Margin = 12;
        double width = Math.Min(desired.Width, Math.Max(0, workArea.Width - 2 * Margin));
        double height = Math.Min(desired.Height, Math.Max(0, workArea.Height - 2 * Margin));
        width = width >= minimum.Width ? width : Math.Min(minimum.Width, workArea.Width);
        height = height >= minimum.Height ? height : Math.Min(minimum.Height, workArea.Height);
        return new Rect(
            workArea.Left + (workArea.Width - width) / 2,
            workArea.Top + (workArea.Height - height) / 2,
            width,
            height);
    }

    private async void OnLoaded(object sender, RoutedEventArgs eventArgs)
    {
        ShellTraceSink.Record(
            ShellTraceScopes.Startup,
            "boot",
            ShellTraceStages.StartupBegin);
        try
        {
            _fieldNavigationLoadingSession = await ShowFieldLoadingAsync(
                FieldLoadingSurface.Loading,
                diagnostic: null);
            // El motor local (core, mente y calentamiento del modelo) no
            // depende de WebView2. Arrancarlo en paralelo con la vista quita de
            // la ruta de arranque el tiempo serie de una sobre la otra sin
            // relajar ninguna comprobación: cada fallo se sigue observando y la
            // cancelación de cierre sigue cortando ambas.
            await ShellStartupSequence.RunAsync(
                () => _viewModel.InitializeAsync(_lifetimeCancellation.Token),
                () => InitializeFieldUiAsync(_lifetimeCancellation.Token),
                RequestedFieldUiProbe());
        }
        catch (OperationCanceledException) when (_lifetimeCancellation.IsCancellationRequested)
        {
            // The window closed while its local frontend or motor was starting.
        }
        catch (Exception exception) when (IsExpectedStartupFailure(exception))
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Startup,
                "boot",
                ShellTraceStages.StartupFailed);
            _ = await ShowFieldFailureWhileOpenAsync(
                UiLanguage.Say("BAXY Field no se abrió. Revisa el runtime local de WebView2.",
                    "BAXY Field failed to open. Check the local WebView2 runtime."),
                exception.Message);
        }
    }

    private async Task InitializeFieldUiAsync(CancellationToken cancellationToken)
    {
        string fieldRoot = Path.Combine(AppContext.BaseDirectory, "FieldUi");
        string indexPath = Path.Combine(fieldRoot, "index.html");
        string bridgePath = Path.Combine(
            AppContext.BaseDirectory,
            "FieldUiHost",
            "field-native-bridge.js");
        if (!File.Exists(indexPath) || !File.Exists(bridgePath))
        {
            throw new FileNotFoundException(
                "La exportación histórica de BAXY Field no está junto a la aplicación.");
        }

        if (!WebView2Runtime.IsInstalled())
        {
            if (_fieldNavigationLoadingSession is { } loading)
            {
                SetFieldLoadingStatus(
                    loading,
                    UiLanguage.Say("Instalando WebView2 de Microsoft, que BAXY necesita para su ventana…",
                        "Installing Microsoft WebView2, which BAXY needs for its window…"),
                    diagnostic: null);
            }

            await WebView2Runtime.InstallAsync(cancellationToken);
        }

        string webViewData = FieldViewDataFolder(
            Environment.GetEnvironmentVariable("BAXY_DATA_DIR"),
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData));
        Directory.CreateDirectory(webViewData);
        CoreWebView2Environment environment = await CoreWebView2Environment.CreateAsync(
            browserExecutableFolder: null,
            userDataFolder: webViewData);
        cancellationToken.ThrowIfCancellationRequested();
        await FieldWebView.EnsureCoreWebView2Async(environment);
        cancellationToken.ThrowIfCancellationRequested();

        CoreWebView2 core = FieldWebView.CoreWebView2
            ?? throw new InvalidOperationException("WebView2 no terminó su inicialización local.");
        core.Settings.AreDevToolsEnabled = false;
        core.Settings.AreDefaultContextMenusEnabled = false;
        core.Settings.AreBrowserAcceleratorKeysEnabled = false;
        core.Settings.IsStatusBarEnabled = false;
        core.Settings.IsZoomControlEnabled = false;
        core.SetVirtualHostNameToFolderMapping(
            HistoricalFieldOriginPolicy.VirtualHost,
            fieldRoot,
            CoreWebView2HostResourceAccessKind.DenyCors);
        core.NavigationStarting += OnNavigationStarting;
        core.NavigationCompleted += OnNavigationCompleted;
        core.NewWindowRequested += OnNewWindowRequested;
        core.ProcessFailed += OnWebViewProcessFailed;
        core.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
        core.WebResourceRequested += OnWebResourceRequested;

        string bridgeScript = await File.ReadAllTextAsync(
            bridgePath,
            cancellationToken);
        _ = await core.AddScriptToExecuteOnDocumentCreatedAsync(bridgeScript);
        if (ShellTraceSink.Current is not null)
        {
            _ = await core.AddScriptToExecuteOnDocumentCreatedAsync(
                DocumentPaintObserverScript);
        }
        _bridge ??= new FieldUiBridge(
            this,
            FieldWebView,
            _viewModel,
            new FieldTelemetrySampler(() => _viewModel.MindProcessId),
            _lifetimeCancellation.Token);
        core.Navigate(HistoricalFieldOriginPolicy.EntryPoint);
        await UpdateFieldActivityAsync();
    }

    // Arranque de comprobación: teclea en el compositor real y lee lo que la
    // ventana muestra. Sin `--ui-probe` no se ejecuta nada de esto. Corre
    // cuando la vista ya está lista, fuera de las marcas de arranque.
    private Func<Task>? RequestedFieldUiProbe()
    {
        string[] arguments = Environment.GetCommandLineArgs();
        if (!FieldUiProbe.IsRequested(arguments))
        {
            return null;
        }

        return async () =>
        {
            try
            {
                CoreWebView2 core = FieldWebView.CoreWebView2
                    ?? throw new InvalidOperationException("WebView2 no terminó su inicialización local.");
                await FieldUiProbe.RunAsync(
                    core,
                    arguments,
                    new FieldProbeWindow(this),
                    _lifetimeCancellation.Token);
            }
            finally
            {
                // Cerrar la ventana no basta: la presencia mantiene el proceso
                // vivo y la siguiente comprobación choca con el mutex de
                // instancia única. Se apaga también si la sonda falló: si no,
                // el lanzador esperaría para siempre.
                // Encargo I2 (tanda fin2 t4: un llama-server huérfano): se sale como
                // con «Salir» de la bandeja. Application.Shutdown cerraba la ventana
                // ignorando el Cancel de OnClosing, así que el desmontaje ordenado
                // (núcleo y mente parados por su canal) no llegaba a correr.
                Exit("probe");
            }
        };
    }

    /// <summary>Leaves BAXY as the tray's Exit does: the orderly teardown (core and mind stopped through their channel).</summary>
    internal void Exit(string via)
    {
        if (_presence is not null)
        {
            _presence.RequestExit(via);
        }
        else
        {
            Application.Current.Shutdown();
        }
    }

    internal static bool ShouldKeepFieldActive(bool isVisible, WindowState state) =>
        isVisible && state != WindowState.Minimized;

    private async void OnWindowPresentationChanged(object? sender, EventArgs eventArgs) =>
        await UpdateFieldActivityAsync();

    private async void OnWindowVisibilityChanged(
        object sender,
        DependencyPropertyChangedEventArgs eventArgs) =>
        await UpdateFieldActivityAsync();

    private async Task UpdateFieldActivityAsync()
    {
        CoreWebView2? core = FieldWebView.CoreWebView2;
        if (core is null || _closing || _disposed)
        {
            return;
        }

        int revision = ++_fieldActivityRevision;
        bool active = ShouldKeepFieldActive(IsVisible, WindowState);
        try
        {
            if (active)
            {
                if (core.IsSuspended)
                {
                    core.Resume();
                }

                FieldWebView.Visibility = Visibility.Visible;
                return;
            }

            FieldWebView.Visibility = Visibility.Collapsed;
            _ = await core.TrySuspendAsync();
            if (revision != _fieldActivityRevision
                && ShouldKeepFieldActive(IsVisible, WindowState))
            {
                if (core.IsSuspended)
                {
                    core.Resume();
                }

                FieldWebView.Visibility = Visibility.Visible;
            }
        }
        catch (InvalidOperationException) when (_closing || _disposed)
        {
        }
    }

    /// <summary>
    /// Observador de instrumentación. Sólo se inyecta cuando el registro está
    /// activo y sólo reporta dos marcas del vocabulario cerrado: cuándo el DOM
    /// aplicó un nodo nuevo y cuándo el compositor entregó el primer cuadro
    /// posterior. No lee contenido, no lo transmite y no altera la vista: el
    /// <c>dist</c> histórico queda intacto.
    /// </summary>
    private const string DocumentPaintObserverScript = """
        (function () {
          if (!window.chrome || !window.chrome.webview) { return; }
          var armed = 0;
          var post = function (stage) {
            try {
              window.chrome.webview.postMessage({
                channel: 'baxy.field.v1',
                kind: 'trace_mark',
                stage: stage,
                id: 'msg'
              });
            } catch (error) { /* la instrumentación nunca rompe la vista */ }
          };
          // Pulsación real de la persona. Se marca en captura, antes de que la
          // vista procese la tecla, para que el tramo teclado→submit exista y
          // no haya que llamar «Enter→paint» a algo que empieza en el bridge.
          // Sólo se reporta la etapa; nunca la tecla ni el texto escrito.
          window.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' && !event.shiftKey) { post('key.enter'); }
          }, true);
          // El FieldUi anima su lienzo de forma continua, así que una
          // observación libre mediría el bucle de render. El observador se arma
          // sólo cuando el puente entrega una actividad nueva: así la marca
          // corresponde al mensaje y no al fondo animado.
          window.chrome.webview.addEventListener('message', function (event) {
            var payload = event.data;
            if (!payload || payload.channel !== 'baxy.field.v1') { return; }
            if (payload.kind !== 'socket_event' || payload.event !== 'message') { return; }
            if (typeof payload.data !== 'string') { return; }
            if (payload.data.indexOf('"type":"item"') < 0) { return; }
            armed = 1;
          });
          var observe = function () {
            if (!document.body) { window.setTimeout(observe, 16); return; }
            new MutationObserver(function (records) {
              if (!armed) { return; }
              var added = false;
              for (var index = 0; index < records.length; index++) {
                if (records[index].addedNodes && records[index].addedNodes.length) {
                  added = true;
                  break;
                }
              }
              if (!added) { return; }
              armed = 0;
              post('dom.applied');
              window.requestAnimationFrame(function () {
                window.requestAnimationFrame(function () {
                  post('paint.observed');
                });
              });
            }).observe(document.body, { childList: true, subtree: true });
          };
          observe();
        })();
        """;

    private static void OnNavigationStarting(
        object? sender,
        CoreWebView2NavigationStartingEventArgs eventArgs)
    {
        if (!HistoricalFieldOriginPolicy.IsTrustedDocumentSource(eventArgs.Uri))
        {
            eventArgs.Cancel = true;
        }
    }

    private async void OnNavigationCompleted(
        object? sender,
        CoreWebView2NavigationCompletedEventArgs eventArgs)
    {
        if (_closing)
        {
            return;
        }

        if (eventArgs.IsSuccess)
        {
            _fieldRetries.Up(DateTimeOffset.UtcNow);
            AppSurfaceSession? loadingSession = _fieldNavigationLoadingSession;
            if (loadingSession is null)
            {
                return;
            }

            try
            {
                _ = await _surfaceNavigator.ReturnToFieldIfCurrentAsync(
                    loadingSession);
            }
            catch (ObjectDisposedException) when (_closing)
            {
            }
            finally
            {
                if (ReferenceEquals(
                        _fieldNavigationLoadingSession,
                        loadingSession))
                {
                    _fieldNavigationLoadingSession = null;
                }
            }
            return;
        }

        _ = await ShowFieldFailureWhileOpenAsync(
            UiLanguage.Say("BAXY Field no cargó", "BAXY Field did not load") + $" ({eventArgs.WebErrorStatus}).",
            diagnostic: null);
    }

    private static void OnNewWindowRequested(
        object? sender,
        CoreWebView2NewWindowRequestedEventArgs eventArgs)
    {
        eventArgs.Handled = true;
    }

    private async void OnWebViewProcessFailed(
        object? sender,
        CoreWebView2ProcessFailedEventArgs eventArgs)
    {
        if (_closing)
        {
            return;
        }

        CoreWebView2ProcessFailedKind kind = eventArgs.ProcessFailedKind;
        ShellTraceSink.Record(ShellTraceScopes.Startup, "view", "view.process_failed", kind.ToString().ToLowerInvariant());
        switch (RecoveryFor(kind))
        {
            case FieldViewRecovery.Reload when sender is CoreWebView2 core:
                core.Reload();
                return;
            case FieldViewRecovery.Recreate:
                await RecreateFieldViewAsync(kind.ToString());
                return;
            default:
                return;
        }
    }

    /// <summary>
    /// uso-116 (N23): with the PC out of memory WebView2's browser process crashed and the window was left saying «Vuelve
    /// a abrir BAXY» while the mind and the core went on. Microsoft: the controls «need to be recreated» («Handling
    /// process-related events in WebView2»), and its sample does it in place. The channel stays, so the conversation does.
    /// </summary>
    private async Task RecreateFieldViewAsync(string diagnostic)
    {
        if (_recreatingField)
        {
            return;
        }

        _recreatingField = true;
        try
        {
            if (_fieldRetries.Failed(diagnostic, DateTimeOffset.UtcNow) is not { } wait)
            {
                _ = await ShowFieldFailureWhileOpenAsync(
                    UiLanguage.Say("La vista local se detuvo varias veces seguidas. Cierra programas para liberar memoria y vuelve a abrir BAXY.",
                        "The local view stopped several times in a row. Close programs to free up memory and open BAXY again."),
                    diagnostic);
                return;
            }

            _fieldNavigationLoadingSession = await ShowFieldLoadingWhileOpenAsync(
                UiLanguage.Say("La vista local se detuvo. Recuperándola…", "The local view stopped. Recovering it…"),
                diagnostic);
            ReplaceFieldView();
            await Task.Delay(wait, _lifetimeCancellation.Token);
            await InitializeFieldUiAsync(_lifetimeCancellation.Token);
        }
        catch (OperationCanceledException) when (_lifetimeCancellation.IsCancellationRequested)
        {
            // The window closed meanwhile.
        }
        catch (Exception exception) when (IsExpectedStartupFailure(exception))
        {
            _ = await ShowFieldFailureWhileOpenAsync(
                UiLanguage.Say("La vista local se detuvo y no se pudo recuperar. Vuelve a abrir BAXY.",
                    "The local view stopped and could not be recovered. Open BAXY again."),
                exception.Message);
        }
        finally
        {
            _recreatingField = false;
        }
    }

    private void ReplaceFieldView()
    {
        WebView2 old = FieldWebView;
        var host = (Panel)old.Parent;
        int at = host.Children.IndexOf(old);
        var view = new WebView2
        {
            DefaultBackgroundColor = old.DefaultBackgroundColor,
            HorizontalAlignment = old.HorizontalAlignment,
            VerticalAlignment = old.VerticalAlignment,
            Visibility = Visibility.Collapsed,
        };
        AutomationProperties.SetAutomationId(view, AutomationProperties.GetAutomationId(old));
        AutomationProperties.SetName(view, AutomationProperties.GetName(old));
        _bridge?.Rebind(view);
        host.Children.RemoveAt(at);
        old.Dispose();
        FieldWebView = view;
        host.Children.Insert(at, view);
        _surfacePresenter.UseField(view);
    }

    /// <summary>
    /// Uso 95 (uso real 2026-11-04 12:06 and 2026-11-03 22:57): with the PC out of memory WebView2's GPU process died
    /// (its crash reports say gpu-process, «oom-mem») and the App replaced the whole interface with «La vista local se
    /// detuvo. Vuelve a abrir BAXY», for a failure the runtime recovers from by itself. What each kind asks of the app, as
    /// Microsoft documents it («Handling process-related events in WebView2», CoreWebView2ProcessFailedKind): the browser
    /// process gone closes the WebView, which has to be created again; the main frame's renderer gone leaves an error
    /// page that Reload recovers; an unresponsive renderer is raised again every few seconds while the system is busy;
    /// the GPU, utility, sandbox helper, a subframe's renderer and the rest are recreated by the runtime.
    /// </summary>
    internal static FieldViewRecovery RecoveryFor(CoreWebView2ProcessFailedKind kind) => kind switch
    {
        CoreWebView2ProcessFailedKind.BrowserProcessExited => FieldViewRecovery.Recreate,
        CoreWebView2ProcessFailedKind.RenderProcessExited => FieldViewRecovery.Reload,
        _ => FieldViewRecovery.None,
    };

    /// <summary>
    /// The view's WebView2 folder (preferences, its cache). 2026-11-04: it was always the one beside the default profile,
    /// so a window on another profile (a test's, BAXY_DATA_DIR) shared the view's preferences with the person's BAXY. The
    /// default profile keeps the folder it has always had; any other profile has its own, inside it.
    /// </summary>
    internal static string FieldViewDataFolder(string? configuredDataRoot, string localData)
    {
        string baxy = Path.Combine(localData, "BAXY");
        return string.IsNullOrWhiteSpace(configuredDataRoot)
            || string.Equals(
                Path.TrimEndingDirectorySeparator(Path.GetFullPath(configuredDataRoot)),
                Path.Combine(baxy, "1"),
                StringComparison.OrdinalIgnoreCase)
            ? Path.Combine(baxy, "webview2-field")
            : Path.Combine(configuredDataRoot, "webview2-field");
    }

    private static void OnWebResourceRequested(
        object? sender,
        CoreWebView2WebResourceRequestedEventArgs eventArgs)
    {
        if (!HistoricalFieldOriginPolicy.ShouldBlockNetworkResource(
                eventArgs.Request.Uri))
        {
            return;
        }

        if (sender is CoreWebView2 core)
        {
            eventArgs.Response = core.Environment.CreateWebResourceResponse(
                Stream.Null,
                403,
                "External network disabled",
                "Content-Type: text/plain\r\nCache-Control: no-store");
        }
    }

    // FT/proveedores goal (review of the App): WebView2 reports most of its start failures as a COMException (its data
    // folder still held by a killed instance, a broken runtime: EnsureCoreWebView2Async); uncaught, BAXY ended with no
    // word. It is a start failure shown like the others.
    private static bool IsExpectedStartupFailure(Exception exception) => exception is
        FileNotFoundException
        or DirectoryNotFoundException
        or UnauthorizedAccessException
        or IOException
        or InvalidOperationException
        or WebView2RuntimeNotFoundException
        or System.Runtime.InteropServices.COMException;

    private async Task<AppSurfaceSession> ShowFieldLoadingAsync(
        string message,
        string? diagnostic)
    {
        AppSurfaceSession session = await _surfaceNavigator.OpenAsync(
                AppSurfaceIds.FieldLoading,
                _lifetimeCancellation.Token)
            ?? throw new InvalidOperationException(
                "La superficie local de estado no está registrada.");
        SetFieldLoadingStatus(session, message, diagnostic);
        return session;
    }

    private async Task<AppSurfaceSession?> ShowFieldLoadingWhileOpenAsync(
        string message,
        string? diagnostic)
    {
        if (_closing)
        {
            return null;
        }

        try
        {
            AppSurfaceSession? session = await _surfaceNavigator.OpenFromFieldAsync(
                AppSurfaceIds.FieldLoading,
                _lifetimeCancellation.Token);
            if (session is null)
            {
                return null;
            }

            SetFieldLoadingStatus(session, message, diagnostic);
            return session;
        }
        catch (OperationCanceledException) when (_closing)
        {
            return null;
        }
        catch (ObjectDisposedException) when (_closing)
        {
            return null;
        }
    }

    private Task<AppSurfaceSession?> ShowFieldFailureWhileOpenAsync(
        string message,
        string? diagnostic)
    {
        _fieldNavigationLoadingSession = null;
        return ShowFieldLoadingWhileOpenAsync(message, diagnostic);
    }

    private static void SetFieldLoadingStatus(
        AppSurfaceSession session,
        string message,
        string? diagnostic)
    {
        if (session.Content is not FieldLoadingSurface loading)
        {
            throw new InvalidOperationException(
                "La superficie local de estado no tiene la vista esperada.");
        }

        loading.SetStatus(message, diagnostic);
    }

    private async void OnClosing(object? sender, CancelEventArgs eventArgs)
    {
        if (_disposed)
        {
            return;
        }

        if (_presence is { IsExitRequested: false } presence)
        {
            eventArgs.Cancel = true;
            // «Al cerrar la ventana» (Settings): BAXY stays in the tray, or closes for good as the tray's Exit does.
            if (_viewModel.Settings.CloseToTray)
            {
                Hide();
            }
            else
            {
                _ = Dispatcher.BeginInvoke(() => presence.RequestExit("window"));
            }

            return;
        }

        eventArgs.Cancel = true;
        if (_closing)
        {
            return;
        }

        _closing = true;
        StateChanged -= OnWindowPresentationChanged;
        IsVisibleChanged -= OnWindowVisibilityChanged;
        IsEnabled = false;
        _lifetimeCancellation.Cancel();
        try
        {
            await _surfaceNavigator.DisposeAsync();
        }
        catch (Exception exception)
        {
            Trace.TraceWarning(
                "app_surface_shutdown_failed: {0}",
                exception.GetType().Name);
        }
        if (_bridge is not null)
        {
            await _bridge.DisposeAsync();
            _bridge = null;
        }

        await _viewModel.DisposeAsync();
        FieldWebView.Dispose();
        _lifetimeCancellation.Dispose();
        _disposed = true;
        Close();
        if (_presence is not null)
        {
            Application.Current?.Shutdown();
        }
    }
}
