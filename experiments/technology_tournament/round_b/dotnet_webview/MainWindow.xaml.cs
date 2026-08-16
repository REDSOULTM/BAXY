using System.Text.Json;
using System.IO;
using System.Windows;
using Microsoft.Web.WebView2.Core;

namespace Baxy.Tournament.RoundB.Dotnet;

public partial class MainWindow : Window
{
    private CoreBridge? _core;
    private bool _closing;

    public MainWindow()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Closing += OnClosing;
    }

    private async void OnLoaded(object sender, RoutedEventArgs eventArgs)
    {
        try
        {
            _core = CoreBridge.Start();
            var dataRoot = Environment.GetEnvironmentVariable("BAXY_ROUND_B_DATA")
                ?? Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "BAXY",
                    "TournamentDotnet");
            var webViewData = Path.Combine(Path.GetFullPath(dataRoot), "WebView2");
            Directory.CreateDirectory(webViewData);
            var options = new CoreWebView2EnvironmentOptions
            {
                AdditionalBrowserArguments = string.Join(
                    ' ',
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-domain-reliability",
                    "--disable-sync",
                    "--metrics-recording-only",
                    "--no-pings",
                    "--no-proxy-server"),
            };
            var environment = await CoreWebView2Environment.CreateAsync(userDataFolder: webViewData, options: options);
            await WebView.EnsureCoreWebView2Async(environment);
            ConfigureWebView(WebView.CoreWebView2);
            var ui = Path.Combine(AppContext.BaseDirectory, "ui");
            if (!File.Exists(Path.Combine(ui, "index.html")))
            {
                throw new FileNotFoundException("No se encontraron los recursos de interfaz.");
            }
            WebView.CoreWebView2.SetVirtualHostNameToFolderMapping(
                "baxy.local",
                ui,
                CoreWebView2HostResourceAccessKind.DenyCors);
            WebView.NavigationCompleted += (_, args) =>
            {
                if (args.IsSuccess)
                {
                    StartupOverlay.Visibility = Visibility.Collapsed;
                }
                else
                {
                    StartupMessage.Text = "La interfaz local no pudo cargarse.";
                }
            };
            var automation = Environment.GetEnvironmentVariable("BAXY_ROUND_B_AUTOMATION") == "1";
            WebView.Source = new Uri($"https://baxy.local/index.html{(automation ? "?automation=1" : "")}");
        }
        catch (Exception)
        {
            StartupMessage.Text = "BAXY no pudo iniciar el core o la interfaz local.";
        }
    }

    private void ConfigureWebView(CoreWebView2 webView)
    {
        webView.Settings.AreDevToolsEnabled = false;
        webView.Settings.AreDefaultContextMenusEnabled = false;
        webView.Settings.AreBrowserAcceleratorKeysEnabled = false;
        webView.Settings.IsStatusBarEnabled = false;
        webView.Settings.IsWebMessageEnabled = true;
        webView.NavigationStarting += (_, args) =>
        {
            if (!args.Uri.StartsWith("https://baxy.local/", StringComparison.OrdinalIgnoreCase))
            {
                args.Cancel = true;
            }
        };
        webView.NewWindowRequested += (_, args) => args.Handled = true;
        webView.PermissionRequested += (_, args) => args.State = CoreWebView2PermissionState.Deny;
        webView.DownloadStarting += (_, args) => args.Cancel = true;
        webView.WebMessageReceived += OnWebMessageReceived;
    }

    private async void OnWebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs args)
    {
        string invocationId = "invalid-ui-request";
        try
        {
            var request = args.WebMessageAsJson;
            using var parsed = JsonDocument.Parse(request);
            invocationId = parsed.RootElement.GetProperty("invocation_id").GetString() ?? invocationId;
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            var response = await (_core ?? throw new InvalidOperationException("Core no disponible"))
                .SubmitAsync(request, timeout.Token);
            WebView.CoreWebView2.PostWebMessageAsJson(response);
        }
        catch (Exception)
        {
            var response = JsonSerializer.Serialize(new
            {
                schema_version = 1,
                invocation_id = invocationId,
                mission_id = $"failed-{invocationId}",
                state = "failed",
                intent = "internal",
                effect = "none",
                risk = "high",
                operations = Array.Empty<object>(),
                verification = new { status = "unverified", evidence = Array.Empty<object>() },
                response = "No pude completar la petición por un fallo interno local.",
                replayed = false,
            });
            WebView.CoreWebView2.PostWebMessageAsJson(response);
        }
    }

    private async void OnClosing(object? sender, System.ComponentModel.CancelEventArgs args)
    {
        if (_closing)
        {
            return;
        }
        args.Cancel = true;
        _closing = true;
        if (_core is not null)
        {
            await _core.DisposeAsync();
            _core = null;
        }
        WebView.Dispose();
        Close();
    }
}
