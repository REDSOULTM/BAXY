using System.Windows;
using System.Windows.Input;
using System.Windows.Media;

namespace Baxy.App.Presentation;

/// <summary>
/// The tray icon's menu in BAXY's own look (design v4: dark panel, carmine accent, the icon): open the window, listen or
/// stop, rest or wake, exit. It opens at the pointer, above the taskbar, and closes when it loses the focus, as a menu
/// does; each row runs the same action as before (<see cref="PresenceHost"/>).
/// </summary>
internal sealed partial class TrayMenu : Window
{
    internal sealed record State(bool Listening, bool MicAvailable, bool Powered, bool Ready);

    private readonly Action _open;
    private readonly Action _listen;
    private readonly Action _power;
    private readonly Action _exit;
    private bool _closing;

    internal TrayMenu(State state, Action open, Action listen, Action power, Action exit)
    {
        _open = open;
        _listen = listen;
        _power = power;
        _exit = exit;
        InitializeComponent();
        ListenRow.Content = state.Listening ? "Dejar de escuchar" : "Escuchar «BAXY»";
        ListenRow.Tag = state.Listening ? "" : "";
        ListenRow.IsEnabled = state.MicAvailable && state.Powered;
        PowerRow.Content = state.Powered ? "Poner en reposo" : "Activar";
        StateText.Text = !state.Ready ? "Arrancando"
            : !state.Powered ? "En reposo"
            : state.Listening ? "Activo · responde a «BAXY»"
            : state.MicAvailable ? "Activo · micrófono en pausa"
            : "Activo · sin micrófono";
        StateDot.Fill = new SolidColorBrush(!state.Ready ? Color.FromRgb(0xE8, 0xC9, 0x8E)
            : state.Powered ? Color.FromRgb(0x7F, 0xD1, 0xA8) : Color.FromRgb(0x5B, 0x65, 0x80));
        // Losing the focus closes it, as a menu does; closing from anywhere (here, a row, a new menu) marks it first, so
        // the deactivation that closing itself causes never closes it twice.
        Closing += (_, _) => _closing = true;
        Deactivated += (_, _) => Dispatcher.BeginInvoke(Dismiss);
        PreviewKeyDown += OnKey;
    }

    /// <summary>Opens the menu with its corner at the pointer (device pixels), kept inside the work area.</summary>
    internal void ShowAt(int x, int y)
    {
        Show();
        UpdateLayout();
        DpiScale dpi = VisualTreeHelper.GetDpi(this);
        double px = x / dpi.DpiScaleX, py = y / dpi.DpiScaleY;
        Rect area = SystemParameters.WorkArea;
        Left = Math.Clamp(px - ActualWidth + 12, area.Left, area.Right - ActualWidth);
        Top = Math.Clamp(py - ActualHeight + 12, area.Top, area.Bottom - ActualHeight);
        Activate();
        OpenRow.Focus();
    }

    private void OnKey(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape)
        {
            e.Handled = true;
            Dismiss();
        }
        else if (e.Key is Key.Down or Key.Up)
        {
            e.Handled = true;
            (Keyboard.FocusedElement as UIElement)?.MoveFocus(new TraversalRequest(
                e.Key == Key.Down ? FocusNavigationDirection.Next : FocusNavigationDirection.Previous));
        }
    }

    private void Run(Action action)
    {
        Dismiss();
        action();
    }

    private void Dismiss()
    {
        if (_closing)
        {
            return;
        }

        _closing = true;
        Close();
    }

    private void OnOpen(object sender, RoutedEventArgs e) => Run(_open);

    private void OnListen(object sender, RoutedEventArgs e) => Run(_listen);

    private void OnPower(object sender, RoutedEventArgs e) => Run(_power);

    private void OnExit(object sender, RoutedEventArgs e) => Run(_exit);
}
