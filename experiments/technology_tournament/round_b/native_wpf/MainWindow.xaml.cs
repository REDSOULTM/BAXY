using System.ComponentModel;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace Baxy.Tournament.RoundB.Dotnet;

public partial class MainWindow : Window
{
    private CoreBridge? _core;
    private bool _closing;
    private bool _busy;
    private bool _highContrast;

    public MainWindow()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Closing += OnClosing;
        SizeChanged += OnSizeChanged;
        MaxWidth = SystemParameters.WorkArea.Width;
        MaxHeight = SystemParameters.WorkArea.Height;
        Width = Math.Min(Width, MaxWidth);
        Height = Math.Min(Height, MaxHeight);
        if (Environment.GetEnvironmentVariable("BAXY_ROUND_B_SCALE") == "200")
        {
            Width = Math.Min(900, MaxWidth);
            Height = Math.Min(520, MaxHeight);
        }
        AutomationProperties.SetName(CoreLabel, "Motor local iniciando");
        SystemParameters.StaticPropertyChanged += OnSystemParametersChanged;
        if (SystemParameters.HighContrast)
        {
            _highContrast = true;
            ApplyContrastTheme(true);
            ContrastButton.SetValue(AutomationProperties.HelpTextProperty, "Contraste alto activado por Windows");
        }
        if (Environment.GetEnvironmentVariable("BAXY_ROUND_B_AUTOMATION") == "1")
        {
            AutomationPanel.Visibility = Visibility.Visible;
            AutomationRow.Height = GridLength.Auto;
        }
        AppendMessage(false, "Hola. Estoy lista para ayudarte con este equipo.", "Trabajo localmente y verifico antes de decir que algo terminó.");
    }

    private async void OnLoaded(object sender, RoutedEventArgs eventArgs)
    {
        MessageInput.IsEnabled = false;
        SendButton.IsEnabled = false;
        try
        {
            _core = CoreBridge.Start();
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
            var probe = JsonSerializer.Serialize(new
            {
                invocation_id = $"round-b-startup-{Guid.NewGuid():N}",
                message = "hola",
            });
            var raw = await _core.SubmitAsync(probe, timeout.Token);
            using var document = JsonDocument.Parse(raw);
            var response = document.RootElement;
            if (response.GetProperty("state").GetString() != "done"
                || string.IsNullOrWhiteSpace(response.GetProperty("response").GetString()))
            {
                throw new InvalidDataException("El core local no supero la atestacion de inicio.");
            }
            SetCoreStatus("CORE LISTO", (Brush)FindResource("OkBrush"), "#AFEED4");
            CoreLabel.Text = "disponible";
            AutomationProperties.SetName(CoreLabel, "Motor local disponible");
            _ = UIElementAutomationPeer.CreatePeerForElement(MissionState);
            _ = UIElementAutomationPeer.CreatePeerForElement(LiveAnnouncement);
            MessageInput.IsEnabled = true;
            SendButton.IsEnabled = true;
            MessageInput.Focus();
        }
        catch (Exception)
        {
            if (_core is not null)
            {
                await _core.DisposeAsync();
                _core = null;
            }
            SetCoreStatus("CORE NO DISPONIBLE", (Brush)FindResource("AccentBrush"), "#FFFFA0A8");
            CoreLabel.Text = "no disponible";
            AutomationProperties.SetName(CoreLabel, "Motor local no disponible");
            MissionState.Text = "FALLO";
            AppendMessage(false, "No pude iniciar el core local.", "BAXY permanece bloqueada para no fingir disponibilidad.");
        }
    }

    private void SetCoreStatus(string text, Brush dotBrush, string foreground)
    {
        CoreStatusDot.Fill = dotBrush;
        CoreStatusText.Text = text;
        CoreStatusText.Foreground = (Brush)new BrushConverter().ConvertFromString(foreground)!;
        AutomationProperties.SetName(CoreStatusText, text);
    }

    private void OnSizeChanged(object sender, SizeChangedEventArgs eventArgs)
    {
        var hideActivity = ActualWidth < 1040;
        ActivityRail.Visibility = hideActivity ? Visibility.Collapsed : Visibility.Visible;
        ActivityColumn.Width = hideActivity ? new GridLength(0) : new GridLength(292);
        var hideLeft = ActualWidth < 760;
        LeftRail.Visibility = hideLeft ? Visibility.Collapsed : Visibility.Visible;
        LeftColumn.Width = hideLeft ? new GridLength(0) : new GridLength(hideActivity ? 218 : 248);
        ConversationPanel.Margin = hideLeft
            ? new Thickness(20, 24, 20, 18)
            : hideActivity ? new Thickness(34, 28, 34, 20) : new Thickness(48, 32, 48, 24);
    }

    private async Task SubmitAsync()
    {
        var message = MessageInput.Text.Trim();
        if (_busy || string.IsNullOrWhiteSpace(message)) return;
        _busy = true;
        MessageInput.IsEnabled = false;
        SendButton.IsEnabled = false;
        AppendMessage(true, message, string.Empty);
        ProgressCard.Visibility = Visibility.Visible;
        ProgressTitle.Text = "Actuando";
        ProgressDetail.Text = "Solo dentro del espacio local autorizado…";
        MissionState.Text = "ACTUANDO";
        var invocationId = AutomationPanel.Visibility == Visibility.Visible && !string.IsNullOrWhiteSpace(InvocationInput.Text)
            ? InvocationInput.Text.Trim()
            : Guid.NewGuid().ToString();
        try
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            var request = JsonSerializer.Serialize(new { invocation_id = invocationId, message });
            var raw = await (_core ?? throw new InvalidOperationException("Core no disponible")).SubmitAsync(request, timeout.Token);
            using var document = JsonDocument.Parse(raw);
            var response = document.RootElement;
            var state = response.GetProperty("state").GetString() ?? "failed";
            var responseText = response.GetProperty("response").GetString() ?? "No recibí una respuesta utilizable.";
            var replayed = response.GetProperty("replayed").GetBoolean();
            MissionState.Text = state == "done" ? "VERIFICADO" : state == "blocked" ? "BLOQUEADO" : "FALLO";
            MissionState.Foreground = state == "done" ? (Brush)FindResource("OkBrush") : state == "blocked" ? (Brush)FindResource("AccentBrush") : Brushes.OrangeRed;
            Announce(MissionState);
            AppendMessage(false, responseText, replayed ? "Resultado recuperado sin repetir el efecto." : "Resultado del core local.");
            RenderActivity(response);
        }
        catch (Exception)
        {
            MissionState.Text = "FALLO";
            MissionState.Foreground = (Brush)FindResource("AccentBrush");
            Announce(MissionState);
            AppendMessage(false, "No pude completar la petición por un fallo interno local.", "No se declaró ningún efecto sin verificar.");
        }
        finally
        {
            ProgressCard.Visibility = Visibility.Collapsed;
            MessageInput.Clear();
            MessageInput.IsEnabled = true;
            SendButton.IsEnabled = true;
            _busy = false;
            MessageInput.Focus();
        }
    }

    private void AppendMessage(bool user, string text, string detail)
    {
        var row = new Grid { Margin = new Thickness(user ? 75 : 0, 0, user ? 0 : 75, 18), HorizontalAlignment = user ? HorizontalAlignment.Right : HorizontalAlignment.Left, MaxWidth = 760 };
        var border = new Border
        {
            Background = user ? new SolidColorBrush(Color.FromRgb(36, 40, 51)) : (Brush)FindResource("SurfaceBrush"),
            BorderBrush = (Brush)FindResource("LineBrush"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(user ? 15 : 4, user ? 4 : 15, 15, 15),
            Padding = new Thickness(15, 12, 15, 12),
        };
        var content = new StackPanel();
        var body = new TextBlock { Text = text, FontSize = 14, TextWrapping = TextWrapping.Wrap, LineHeight = 22 };
        AutomationProperties.SetName(body, $"{(user ? "Tú" : "BAXY")}: {text}");
        content.Children.Add(body);
        if (!string.IsNullOrEmpty(detail))
        {
            var small = new TextBlock { Text = detail, FontSize = 10, Foreground = (Brush)FindResource("MutedBrush"), Margin = new Thickness(0, 7, 0, 0), TextWrapping = TextWrapping.Wrap };
            AutomationProperties.SetName(small, detail);
            content.Children.Add(small);
        }
        border.Child = content;
        row.Children.Add(border);
        ConversationStack.Children.Add(row);
        ConversationScroller.ScrollToEnd();
        if (!user)
        {
            LiveAnnouncement.Text = string.IsNullOrEmpty(detail) ? text : $"{text} {detail}";
            Announce(LiveAnnouncement);
        }
    }

    private void RenderActivity(JsonElement response)
    {
        ActivityStack.Children.Clear();
        AddActivity("✓  Entendido", "Preparé un plan local.", false);
        var step = 0;
        foreach (var operation in response.GetProperty("operations").EnumerateArray())
        {
            _ = operation;
            step++;
            AddActivity($"✓  Paso {step} completado", "El efecto local quedó registrado.", false);
        }
        var verified = response.GetProperty("verification").GetProperty("status").GetString() == "verified";
        AddActivity(verified ? "✓  Verificado" : "•  Sin efecto verificable", verified ? "El estado real coincide." : "BAXY no declaró un éxito falso.", !verified);
    }

    private void AddActivity(string title, string detail, bool muted)
    {
        var titleBlock = new TextBlock { Text = title, FontWeight = FontWeights.SemiBold, FontSize = 11, Opacity = muted ? .65 : 1 };
        var detailBlock = new TextBlock { Text = detail, Foreground = (Brush)FindResource("MutedBrush"), FontSize = 10, Margin = new Thickness(22, 4, 0, 13), TextWrapping = TextWrapping.Wrap, Opacity = muted ? .65 : 1 };
        AutomationProperties.SetName(titleBlock, title);
        AutomationProperties.SetName(detailBlock, detail);
        ActivityStack.Children.Add(titleBlock);
        ActivityStack.Children.Add(detailBlock);
    }

    private void OnSendClick(object sender, RoutedEventArgs eventArgs) => _ = SubmitAsync();

    private void OnWindowPreviewKeyDown(object sender, KeyEventArgs eventArgs)
    {
        if ((eventArgs.Key == Key.Enter || eventArgs.Key == Key.Return)
            && Keyboard.Modifiers != ModifierKeys.Shift
            && MessageInput.IsKeyboardFocusWithin)
        {
            eventArgs.Handled = true;
            _ = SubmitAsync();
        }
    }

    private void OnCreateExample(object sender, RoutedEventArgs eventArgs) { MessageInput.Text = "Crea la nota ideas.txt con el texto: comprar té"; MessageInput.Focus(); }
    private void OnReadExample(object sender, RoutedEventArgs eventArgs) { MessageInput.Text = "Lee la nota ideas.txt"; MessageInput.Focus(); }
    private void OnTrashExample(object sender, RoutedEventArgs eventArgs) { MessageInput.Text = "Mueve la nota ideas.txt a la papelera"; MessageInput.Focus(); }
    private void OnMessageTextChanged(object sender, TextChangedEventArgs eventArgs) => ComposerPlaceholder.Visibility = string.IsNullOrEmpty(MessageInput.Text) ? Visibility.Visible : Visibility.Collapsed;

    private void OnContrastClick(object sender, RoutedEventArgs eventArgs)
    {
        _highContrast = !_highContrast;
        ApplyContrastTheme(_highContrast);
        ContrastButton.SetValue(AutomationProperties.HelpTextProperty, _highContrast ? "Contraste alto activado" : "Contraste alto desactivado");
    }

    private void ApplyContrastTheme(bool enabled)
    {
        var palette = enabled
            ? new Dictionary<string, string>
            {
                ["BackgroundBrush"] = "#FF000000",
                ["RailBrush"] = "#FF000000",
                ["SurfaceBrush"] = "#FF0A0A0A",
                ["SurfaceSoftBrush"] = "#FF000000",
                ["LineBrush"] = "#FFFFFFFF",
                ["TextBrush"] = "#FFFFFFFF",
                ["MutedBrush"] = "#FFE6E6E6",
                ["AccentBrush"] = "#FFFF6B76",
                ["AccentSoftBrush"] = "#55FF6B76",
                ["OkBrush"] = "#FF7CFFCB",
            }
            : new Dictionary<string, string>
            {
                ["BackgroundBrush"] = "#FF0A0E14",
                ["RailBrush"] = "#F20F1419",
                ["SurfaceBrush"] = "#FF161B22",
                ["SurfaceSoftBrush"] = "#FF0F1419",
                ["LineBrush"] = "#FF3A4554",
                ["TextBrush"] = "#FFF5F7FA",
                ["MutedBrush"] = "#FFAAB2C0",
                ["AccentBrush"] = "#FFB83A4A",
                ["AccentSoftBrush"] = "#33B83A4A",
                ["OkBrush"] = "#FF57C79E",
            };
        foreach (var (key, value) in palette)
        {
            Application.Current.Resources[key] = (Brush)new BrushConverter().ConvertFromString(value)!;
        }
        Root.Background = (Brush)FindResource("BackgroundBrush");
    }

    private void OnSystemParametersChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        if (eventArgs.PropertyName != nameof(SystemParameters.HighContrast)) return;
        _highContrast = SystemParameters.HighContrast;
        ApplyContrastTheme(_highContrast);
        ContrastButton.SetValue(
            AutomationProperties.HelpTextProperty,
            _highContrast ? "Contraste alto activado por Windows" : "Contraste alto desactivado");
    }

    private static void Announce(UIElement element)
    {
        var peer = UIElementAutomationPeer.FromElement(element) ?? UIElementAutomationPeer.CreatePeerForElement(element);
        peer?.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
    }

    private void OnMinimizeClick(object sender, RoutedEventArgs eventArgs) => WindowState = WindowState.Minimized;
    private void OnCloseClick(object sender, RoutedEventArgs eventArgs) => Close();

    private async void OnClosing(object? sender, System.ComponentModel.CancelEventArgs eventArgs)
    {
        SystemParameters.StaticPropertyChanged -= OnSystemParametersChanged;
        if (_closing) return;
        eventArgs.Cancel = true;
        _closing = true;
        if (_core is not null)
        {
            await _core.DisposeAsync();
            _core = null;
        }
        Close();
    }
}
