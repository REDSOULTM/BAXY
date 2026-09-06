using System.ComponentModel;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.IO;
using System.Windows;
using Baxy.App.Presentation;
using Microsoft.Web.WebView2.Core;

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
        _surfaceNavigator = new AppSurfaceNavigator(
            AppSurfaceCatalog.CreateDefault(),
            new MainWindowSurfacePresenter(FieldWebView, AppSurfaceLayer));
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
                "Recuperando la interfaz histórica local…",
                diagnostic: null);
            // El motor local (core, mente y calentamiento del modelo) no
            // depende de WebView2. Arrancarlo en paralelo con la vista quita de
            // la ruta de arranque el tiempo serie de una sobre la otra sin
            // relajar ninguna comprobación: cada fallo se sigue observando y la
            // cancelación de cierre sigue cortando ambas.
            ShellTraceSink.Record(
                ShellTraceScopes.Startup,
                "boot",
                ShellTraceStages.StartupShellBegin);
            Task shell = _viewModel.InitializeAsync(_lifetimeCancellation.Token);
            try
            {
                ShellTraceSink.Record(
                    ShellTraceScopes.Startup,
                    "boot",
                    ShellTraceStages.StartupFieldBegin);
                await InitializeFieldUiAsync(_lifetimeCancellation.Token);
                ShellTraceSink.Record(
                    ShellTraceScopes.Startup,
                    "boot",
                    ShellTraceStages.StartupFieldReady);
            }
            finally
            {
                await shell;
                ShellTraceSink.Record(
                    ShellTraceScopes.Startup,
                    "boot",
                    ShellTraceStages.StartupShellReady);
            }

            ShellTraceSink.Record(
                ShellTraceScopes.Startup,
                "boot",
                ShellTraceStages.StartupReady);
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
                "BAXY Field failed to open. Check the local WebView2 runtime.",
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

        string localData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string webViewData = Path.Combine(localData, "BAXY", "webview2-field");
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
        _bridge = new FieldUiBridge(
            this,
            FieldWebView,
            _viewModel,
            new FieldTelemetrySampler(),
            _lifetimeCancellation.Token);
        core.Navigate(HistoricalFieldOriginPolicy.EntryPoint);
        await UpdateFieldActivityAsync();

        // Arranque de comprobación: teclea en el compositor real y lee lo que
        // la ventana muestra. Sin `--ui-probe` no se ejecuta nada de esto.
        string[] arguments = Environment.GetCommandLineArgs();
        if (FieldUiProbe.IsRequested(arguments))
        {
            await FieldUiProbe.RunAsync(core, arguments, _lifetimeCancellation.Token);
            // Cerrar la ventana no basta: la presencia mantiene el proceso vivo
            // y la siguiente comprobación choca con el mutex de instancia única.
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
            if (payload.data.indexOf('"type":"activity"') < 0) { return; }
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
            $"BAXY Field no cargó ({eventArgs.WebErrorStatus}).",
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

        _ = await ShowFieldFailureWhileOpenAsync(
            "La vista local se detuvo. Vuelve a abrir BAXY para restaurarla.",
            eventArgs.ProcessFailedKind.ToString());
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

    private static bool IsExpectedStartupFailure(Exception exception) => exception is
        FileNotFoundException
        or DirectoryNotFoundException
        or UnauthorizedAccessException
        or IOException
        or InvalidOperationException
        or WebView2RuntimeNotFoundException;

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

        if (_presence is { IsExitRequested: false })
        {
            eventArgs.Cancel = true;
            Hide();
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
