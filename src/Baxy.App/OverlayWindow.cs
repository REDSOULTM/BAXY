using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Automation.Provider;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;

namespace Baxy.App;

/// <summary>
/// The overlay itself (design: artifact «BAXY interfaz v5», boards 11 and 12): a small dark glass card in a corner of the
/// screen, on top of everything, that never takes the focus or the keyboard. A click on it brings BAXY to the front; a
/// card can be answered from it only when the person chose so.
/// </summary>
internal sealed class OverlayWindow : Window
{
    private const int EdgeGap = 20;
    private readonly Border _card = new() { CornerRadius = new CornerRadius(12), BorderThickness = new Thickness(1), ClipToBounds = true };
    private readonly StackPanel _body = new();
    private readonly StackPanel _top = new();
    private readonly Border _answers = new();
    private readonly Border _foot = new();
    private readonly ControlTemplate _flat = Flat();
    private readonly ApprovalGuard _guard = new(ArmMilliseconds);
    private readonly DispatcherTimer _arming;
    private string? _cardId;
    private string? _asks;
    private string? _answersFor;
    private Button? _yes;
    private Rect? _yesAt;
    private long? _pressedAt;
    private int _drawing;
    private bool _hidden;

    internal OverlayWindow()
    {
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        Topmost = true;
        ShowInTaskbar = false;
        ShowActivated = false;
        Focusable = false;
        ResizeMode = ResizeMode.NoResize;
        SizeToContent = SizeToContent.Height;
        Title = "BAXY";
        _card.Child = _body;
        // the answers stay the same buttons while their card waits: only what is above and below them is drawn again
        _body.Children.Add(_top);
        _body.Children.Add(_answers);
        _body.Children.Add(_foot);
        _arming = new DispatcherTimer(DispatcherPriority.Background, Dispatcher);
        _arming.Tick += (_, _) => ArmIfDue();
        _card.BorderBrush = new SolidColorBrush(Color.FromArgb(0x1A, 0xFF, 0xFF, 0xFF));
        _card.Effect = new System.Windows.Media.Effects.DropShadowEffect { BlurRadius = 24, ShadowDepth = 6, Opacity = 0.45, Color = Colors.Black };
        Content = new Border { Padding = new Thickness(12), Child = _card };
        _card.MouseLeftButtonUp += (_, e) =>
        {
            if (e.OriginalSource is DependencyObject source && FindButton(source) is null)
            {
                Opened?.Invoke();
            }
        };
        _card.Cursor = Cursors.Hand;
        // shown again (BAXY went behind once more): its Sí arms again, as for a card that just appeared
        IsVisibleChanged += (_, _) =>
        {
            _hidden = !IsVisible;
            Disarm();
        };
        // and so does a Sí that is not where it was, or not the size it was, on the screen
        LayoutUpdated += (_, _) => Track();
        LocationChanged += (_, _) => Track();
        SourceInitialized += (_, _) =>
        {
            nint handle = new WindowInteropHelper(this).Handle;
            nint style = NativeMethods.GetWindowLongPtr(handle, NativeMethods.ExtendedStyle);
            _ = NativeMethods.SetWindowLongPtr(handle, NativeMethods.ExtendedStyle, style | NativeMethods.NoActivate | NativeMethods.ToolWindow);
        };
    }

    /// <summary>A click on the card, anywhere but a button.</summary>
    internal event Action? Opened;

    /// <summary>The person answered the card shown: its id and yes or no.</summary>
    internal event Action<string, bool>? Answered;

    /// <summary>
    /// INT16 (blind review), OVL1: how long the Sí must have been drawn in its place, off, before it is lit and takes a
    /// press (<see cref="ApprovalGuard"/>): a click meant for what was under the corner must not approve. Only the
    /// button that authorizes is held, as Firefox's security.dialog_enable_delay does: the No never is.
    /// </summary>
    internal static int ArmMilliseconds => ApprovalGuard.Wait(NativeMethods.GetDoubleClickTime());

    /// <summary>Milliseconds of a steady clock (tests set it).</summary>
    internal Func<long> Ticks { get; init; } = static () => Environment.TickCount64;

    /// <summary>The clock input messages are stamped with (GetMessageTime; tests set it).</summary>
    internal Func<int> MessageTicks { get; init; } = static () => Environment.TickCount;

    internal void Render(OverlaySnapshot shown, OverlaySettings settings, bool english)
    {
        ArgumentNullException.ThrowIfNull(shown);
        ArgumentNullException.ThrowIfNull(settings);
        (double width, double text) = settings.Size switch { "s" => (260d, 11.5), "l" => (380d, 14d), _ => (312d, 12.5) };
        Width = width + 24;
        Color accent = Accent(shown.Kind);
        _card.Background = new SolidColorBrush(Color.FromArgb((byte)Math.Round(settings.Opacity / 100d * 255), 10, 14, 20));
        if (shown.Kind == "ask")
        {
            _card.BorderBrush = new SolidColorBrush(Color.FromArgb(0x99, 0xE8, 0xB0, 0x4A));
        }
        else
        {
            _card.BorderBrush = new SolidColorBrush(Color.FromArgb(0x1A, 0xFF, 0xFF, 0xFF));
        }

        _top.Children.Clear();
        _top.Children.Add(Line(shown.Progress, accent));

        var head = new DockPanel { Margin = new Thickness(12, 10, 12, 6), LastChildFill = false };
        head.Children.Add(Mark(accent));
        head.Children.Add(Text("BAXY", text - 1.5, Colors.White, FontWeights.SemiBold, new Thickness(8, 0, 8, 0)));
        head.Children.Add(Text(shown.Title, text - 0.5, accent, FontWeights.Medium, new Thickness(0)));
        TextBlock clock = Text(shown.Elapsed, text - 1.5, Color.FromRgb(0x8A, 0x94, 0xA8), FontWeights.Normal, new Thickness(8, 0, 0, 0));
        clock.FontFamily = new FontFamily("Cascadia Mono, Consolas");
        DockPanel.SetDock(clock, Dock.Right);
        head.Children.Insert(0, clock);
        _top.Children.Add(head);

        if (shown.Say is { Length: > 0 } say)
        {
            TextBlock line = Text(say, text + 1, Color.FromRgb(0xE6, 0xE9, 0xF0), FontWeights.Medium, new Thickness(12, 0, 12, 8));
            line.TextWrapping = TextWrapping.Wrap;
            if (shown.Kind != "ask")
            {
                // a reply is cut at three lines; a card asking for the yes is shown whole (INT16, blind review)
                line.MaxHeight = (text + 6) * 3;
                line.TextTrimming = TextTrimming.CharacterEllipsis;
            }

            _top.Children.Add(line);
        }

        var list = new StackPanel { Margin = new Thickness(12, 0, 12, 10) };
        for (int i = 0; i < shown.Steps.Count; i++)
        {
            list.Children.Add(StepRow(shown.Steps[i], text, old: i < shown.Steps.Count - 2));
        }

        if (list.Children.Count > 0)
        {
            _top.Children.Add(list);
        }

        // another confirmation, by its id or by what it says it will do: a Sí meant for the one before must not approve it
        string? asks = shown.Card is { } asking ? asking + "\n" + shown.Say : null;
        bool another = asks != _asks;
        _asks = asks;
        _cardId = shown.Card;
        string? answersFor = shown.Card is { } pending && settings.Answer ? string.Join('\n', pending, english, text) : null;
        if (answersFor != _answersFor)
        {
            _answersFor = answersFor;
            another = true;
            _yes = null;
            _yesAt = null;
            _answers.Child = null;
            if (shown.Card is { } card && answersFor is not null)
            {
                var buttons = new UniformGrid2(new Thickness(12, 0, 12, 10));
                Button no = Button(UiLanguage.Say(english, "No", "No"), text);
                no.Click += (_, _) => Answer(card, approve: false);
                no.MouseEnter += (_, _) => no.Background = new SolidColorBrush(Color.FromArgb(0x1F, 0xFF, 0xFF, 0xFF));
                no.MouseLeave += (_, _) => no.Background = new SolidColorBrush(Color.FromArgb(0x0A, 0xFF, 0xFF, 0xFF));
                Button yes = Button(UiLanguage.Say(english, "Sí", "Yes"), text, takes: () => _guard.Takes(Ticks()), asked: () => _pressedAt = Ticks());
                yes.PreviewMouseLeftButtonDown += (_, e) => Pressed(e.Timestamp);
                yes.Click += (_, _) => Approve(card);
                // a press let go off the button clicks nothing: it is not the press of a later click (the button
                // lets go of the mouse before it raises its click, so this runs after it)
                yes.LostMouseCapture += (_, _) => Dispatcher.BeginInvoke(DispatcherPriority.Normal, () => _pressedAt = null);
                yes.MouseEnter += (_, _) => Look();
                yes.MouseLeave += (_, _) => Look();
                buttons.Add(no);
                buttons.Add(yes);
                _yes = yes;
                _answers.Child = buttons.Panel;
            }
        }

        if (another)
        {
            Disarm();
        }
        else
        {
            ArmIfDue();
        }

        _foot.Child = null;
        if (shown.Request is { Length: > 0 } request)
        {
            var foot = new DockPanel { Margin = new Thickness(0) };
            var rule = new Border { BorderBrush = new SolidColorBrush(Color.FromArgb(0x12, 0xFF, 0xFF, 0xFF)), BorderThickness = new Thickness(0, 1, 0, 0), Padding = new Thickness(12, 6, 12, 7), Child = foot };
            TextBlock open = Text(UiLanguage.Say(english, "Clic: abrir BAXY", "Click: open BAXY"), text - 1.5, Color.FromRgb(0x8A, 0x94, 0xA8), FontWeights.Normal, new Thickness(8, 0, 0, 0));
            DockPanel.SetDock(open, Dock.Right);
            foot.Children.Add(open);
            TextBlock asked = Text("«" + request + "»", text - 1.5, Color.FromRgb(0x8A, 0x94, 0xA8), FontWeights.Normal, new Thickness(0));
            asked.TextTrimming = TextTrimming.CharacterEllipsis;
            foot.Children.Add(asked);
            _foot.Child = rule;
        }
    }

    /// <summary>Places the overlay in the chosen corner of the screen's work area (above the taskbar).</summary>
    internal void Place(string corner)
    {
        UpdateLayout();
        Rect area = SystemParameters.WorkArea;
        double height = ActualHeight > 0 ? ActualHeight : 200;
        Left = corner is "tl" or "bl" ? area.Left + EdgeGap - 12 : area.Right - Width - EdgeGap + 12;
        Top = corner is "tl" or "tr" ? area.Top + EdgeGap - 12 : area.Bottom - height - EdgeGap + 12;
    }

    /// <summary>Where the Sí is on the screen and its size, as last laid out (tests say it: they show no window).</summary>
    internal void SiAt(Rect at)
    {
        if (at != _yesAt)
        {
            _yesAt = at;
            Disarm();
        }
    }

    // The card the button was drawn for, if it is still the one shown.
    private void Answer(string card, bool approve)
    {
        if (card == _cardId)
        {
            Answered?.Invoke(card, approve);
        }
    }

    // The mouse went down on the Sí: when the person pressed is the time of the message, however late it is handled.
    // A press that came too soon starts the wait again.
    private void Pressed(int messageTime)
    {
        long at = Ticks() - Math.Max(0, unchecked(MessageTicks() - messageTime));
        _pressedAt = at;
        if (!_guard.Takes(at))
        {
            Disarm();
        }
    }

    // The Sí was clicked: by the press of the mouse that began it or, with none (an assistive tool), now.
    private void Approve(string card)
    {
        long at = _pressedAt ?? Ticks();
        _pressedAt = null;
        if (_guard.Takes(at))
        {
            Answer(card, approve: true);
        }
        else
        {
            Disarm();
        }
    }

    // The Sí goes off; its wait starts once the window has drawn it so.
    private void Disarm()
    {
        bool took = _guard.Takes(Ticks());
        _guard.Restart();
        Told(took, false);
        _arming.Stop();
        int drawing = ++_drawing;
        Look();
        if (_yes is null || _hidden)
        {
            return;
        }

        _ = Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () =>
        {
            if (drawing == _drawing)
            {
                _guard.Placed(Ticks());
                ArmIfDue();
            }
        });
    }

    // Lights the Sí once its wait is over (it takes presses made after the window has drawn it lit), or asks to be
    // called when it will be.
    private void ArmIfDue()
    {
        _arming.Stop();
        if (_yes is null || _guard.IsLit)
        {
            return;
        }

        long now = Ticks();
        if (_guard.Light(now))
        {
            Look();
            int drawing = _drawing;
            _ = Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () =>
            {
                if (drawing == _drawing)
                {
                    _guard.Armed(Ticks());
                    Told(false, true);
                }
            });
        }
        else if (_guard.Left(now) is { } left)
        {
            _arming.Interval = TimeSpan.FromMilliseconds(left + 1);
            _arming.Start();
        }
    }

    // An assistive tool that is listening hears that the Sí now takes, or no longer takes, a press.
    private void Told(bool was, bool now)
    {
        if (was != now && _yes is { } yes)
        {
            UIElementAutomationPeer.FromElement(yes)?.RaisePropertyChangedEvent(AutomationElementIdentifiers.IsEnabledProperty, was, now);
        }
    }

    // A Sí that is off looks off: no colour, dim words, no hand. One that looks ready and does not answer is the trap.
    private void Look()
    {
        if (_yes is not { } yes)
        {
            return;
        }

        bool lit = _guard.IsLit;
        yes.Background = new SolidColorBrush(!lit ? Color.FromArgb(0x0A, 0xFF, 0xFF, 0xFF) : yes.IsMouseOver ? Color.FromRgb(0xCC, 0x4A, 0x5B) : Color.FromRgb(0xB8, 0x3A, 0x4A));
        yes.Foreground = new SolidColorBrush(lit ? Colors.White : Color.FromArgb(0x66, 0xFF, 0xFF, 0xFF));
        yes.Cursor = lit ? Cursors.Hand : Cursors.Arrow;
    }

    private void Track()
    {
        if (_yes is { IsVisible: true } yes && PresentationSource.FromVisual(yes) is not null)
        {
            SiAt(new Rect(yes.PointToScreen(default), yes.RenderSize));
        }
    }

    private static Color Accent(string kind) => kind switch
    {
        "working" or "read" => Color.FromRgb(0x8C, 0xA6, 0xFF),
        "ok" or "same" => Color.FromRgb(0x55, 0xC9, 0x94),
        "ask" or "sent" or "maybe" or "part" => Color.FromRgb(0xE8, 0xB0, 0x4A),
        "fail" => Color.FromRgb(0xFF, 0x84, 0x66),
        _ => Color.FromRgb(0xA9, 0xB2, 0xC3),
    };

    private static Border Line(double progress, Color accent)
    {
        var track = new Grid { Height = 2, Background = new SolidColorBrush(Color.FromArgb(0x14, 0xFF, 0xFF, 0xFF)) };
        track.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(Math.Clamp(progress, 0.02, 1), GridUnitType.Star) });
        track.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(Math.Max(0, 1 - Math.Clamp(progress, 0.02, 1)), GridUnitType.Star) });
        var fill = new Border { Background = new SolidColorBrush(accent) };
        Grid.SetColumn(fill, 0);
        track.Children.Add(fill);
        return new Border { Child = track };
    }

    private static Border Mark(Color accent) => new()
    {
        Width = 16,
        Height = 16,
        CornerRadius = new CornerRadius(8),
        BorderThickness = new Thickness(2),
        BorderBrush = new SolidColorBrush(accent),
        VerticalAlignment = VerticalAlignment.Center,
        Child = new Border { Width = 5, Height = 5, CornerRadius = new CornerRadius(2.5), Background = new SolidColorBrush(Color.FromRgb(0xFF, 0x6B, 0x7D)), HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center },
    };

    private static Grid StepRow(OverlayStep step, double text, bool old)
    {
        var row = new Grid { Margin = new Thickness(0, 3, 0, 3), Opacity = old ? 0.55 : 1 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(22) });
        row.ColumnDefinitions.Add(new ColumnDefinition());
        (string icon, Color color) = step.Status switch
        {
            "ok" or "same" or "read" => ("✓", Color.FromRgb(0x55, 0xC9, 0x94)),
            "fail" => ("✕", Color.FromRgb(0xFF, 0x84, 0x66)),
            "sent" => ("↗", Color.FromRgb(0xE8, 0xB0, 0x4A)),
            "maybe" => ("?", Color.FromRgb(0xE8, 0xB0, 0x4A)),
            "skip" => ("–", Color.FromRgb(0xA9, 0xB2, 0xC3)),
            _ => ("◌", Color.FromRgb(0x8C, 0xA6, 0xFF)),
        };
        TextBlock mark = Text(icon, text - 1, color, FontWeights.SemiBold, new Thickness(0, 1, 0, 0));
        row.Children.Add(mark);
        var words = new StackPanel();
        TextBlock label = Text(step.Label, text, Color.FromRgb(0xE6, 0xE9, 0xF0), FontWeights.Medium, new Thickness(0));
        label.TextTrimming = TextTrimming.CharacterEllipsis;
        words.Children.Add(label);
        if (step.Note is { } note)
        {
            TextBlock seen = Text(note, text - 1, step.Status == "fail" ? color : Color.FromRgb(0xA9, 0xB2, 0xC3), FontWeights.Normal, new Thickness(0, 1, 0, 0));
            seen.TextTrimming = TextTrimming.CharacterEllipsis;
            words.Children.Add(seen);
        }

        Grid.SetColumn(words, 1);
        row.Children.Add(words);
        return row;
    }

    private static TextBlock Text(string text, double size, Color color, FontWeight weight, Thickness margin) => new()
    {
        Text = text,
        FontSize = size,
        FontWeight = weight,
        Foreground = new SolidColorBrush(color),
        Margin = margin,
        FontFamily = new FontFamily("Segoe UI Variable Text, Segoe UI"),
        VerticalAlignment = VerticalAlignment.Center,
    };

    // The overlay never takes the keyboard: its buttons take no focus either (a key never presses them).
    private Held Button(string label, double text, Func<bool>? takes = null, Action? asked = null) => new(takes, asked)
    {
        Content = label,
        FontSize = text,
        Height = 28,
        Margin = new Thickness(3, 0, 3, 0),
        Foreground = Brushes.White,
        Background = new SolidColorBrush(Color.FromArgb(0x0A, 0xFF, 0xFF, 0xFF)),
        BorderBrush = new SolidColorBrush(Color.FromArgb(0x24, 0xFF, 0xFF, 0xFF)),
        BorderThickness = new Thickness(1),
        Cursor = Cursors.Hand,
        Focusable = false,
        Template = _flat,
    };

    // A face that shows only the colours the button is given: the system's own lights up under the pointer whatever
    // the button would answer.
    private static ControlTemplate Flat()
    {
        var face = new FrameworkElementFactory(typeof(Border));
        face.SetValue(Border.CornerRadiusProperty, new CornerRadius(4));
        face.SetValue(Border.BackgroundProperty, new TemplateBindingExtension(BackgroundProperty));
        face.SetValue(Border.BorderBrushProperty, new TemplateBindingExtension(BorderBrushProperty));
        face.SetValue(Border.BorderThicknessProperty, new TemplateBindingExtension(BorderThicknessProperty));
        var label = new FrameworkElementFactory(typeof(ContentPresenter));
        label.SetValue(HorizontalAlignmentProperty, HorizontalAlignment.Center);
        label.SetValue(VerticalAlignmentProperty, VerticalAlignment.Center);
        face.AppendChild(label);
        return new ControlTemplate(typeof(Button)) { VisualTree = face };
    }

    private static Button? FindButton(DependencyObject? node)
    {
        while (node is not null)
        {
            if (node is Button button)
            {
                return button;
            }

            node = node is Visual or System.Windows.Media.Media3D.Visual3D ? VisualTreeHelper.GetParent(node) : LogicalTreeHelper.GetParent(node);
        }

        return null;
    }

    // A button that tells UI Automation whether it takes a press now. An assistive tool's Invoke carries no time of its
    // own: it is judged when it reaches the window (UI Automation's calls come at Send, before anything queued behind
    // them can arm the Sí), refused while the button says it is not enabled, and once taken it is the press of the
    // click it posts, as the mouse going down is, however late that click is handled.
    private sealed class Held(Func<bool>? takes, Action? asked) : Button
    {
        protected override AutomationPeer OnCreateAutomationPeer() => new Peer(this, takes, asked);

        private void Press() => OnClick();

        private sealed class Peer(Held owner, Func<bool>? takes, Action? asked) : ButtonAutomationPeer(owner), IInvokeProvider
        {
            protected override bool IsEnabledCore() => base.IsEnabledCore() && (takes?.Invoke() ?? true);

            void IInvokeProvider.Invoke()
            {
                if (!IsEnabled())
                {
                    throw new ElementNotEnabledException();
                }

                asked?.Invoke();
                _ = Dispatcher.InvokeAsync(owner.Press, DispatcherPriority.Input);
            }
        }
    }

    private sealed class UniformGrid2(Thickness margin)
    {
        internal Grid Panel { get; } = new() { Margin = margin };

        internal void Add(UIElement element)
        {
            Panel.ColumnDefinitions.Add(new ColumnDefinition());
            Grid.SetColumn(element, Panel.ColumnDefinitions.Count - 1);
            Panel.Children.Add(element);
        }
    }

    private static class NativeMethods
    {
        internal const int ExtendedStyle = -20;
        internal const nint NoActivate = 0x08000000;
        internal const nint ToolWindow = 0x00000080;

        [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
        internal static extern nint GetWindowLongPtr(nint window, int index);

        [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")]
        internal static extern nint SetWindowLongPtr(nint window, int index, nint value);

        [DllImport("user32.dll")]
        internal static extern uint GetDoubleClickTime();
    }
}
