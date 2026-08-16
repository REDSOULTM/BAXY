using System.Globalization;
using System.Windows;
using System.Windows.Automation.Peers;
using System.Windows.Media;

namespace Baxy.App;

public sealed class AgentFieldGraph : FrameworkElement
{
    private static readonly Point[] Nodes =
    [
        new(0.50, 0.12),
        new(0.17, 0.30),
        new(0.83, 0.27),
        new(0.88, 0.58),
        new(0.10, 0.60),
        new(0.58, 0.87),
        new(0.31, 0.19),
        new(0.40, 0.08),
        new(0.63, 0.10),
        new(0.73, 0.18),
        new(0.94, 0.42),
        new(0.82, 0.74),
        new(0.71, 0.83),
        new(0.40, 0.93),
        new(0.28, 0.83),
        new(0.08, 0.43),
        new(0.30, 0.46),
        new(0.66, 0.40),
        new(0.34, 0.67),
        new(0.68, 0.62),
    ];

    private static readonly (int First, int Second)[] Edges =
    [
        (0, 6), (0, 7), (0, 8), (0, 9), (6, 1), (9, 2),
        (1, 15), (1, 16), (2, 10), (2, 17), (2, 3), (3, 10),
        (3, 11), (3, 12), (4, 15), (4, 16), (4, 18), (4, 14),
        (5, 11), (5, 12), (5, 13), (5, 14), (16, 17), (17, 19),
        (19, 18), (18, 16), (16, 0), (17, 2), (19, 3), (18, 4),
    ];

    internal static int NodeCount => Nodes.Length;

    internal static int EdgeCount => Edges.Length;

    internal static bool UsesAnimation => false;

    internal static bool IsAutomationContent => false;

    public static readonly DependencyProperty IsReadyProperty = DependencyProperty.Register(
        nameof(IsReady),
        typeof(bool),
        typeof(AgentFieldGraph),
        new FrameworkPropertyMetadata(false, FrameworkPropertyMetadataOptions.AffectsRender));

    public static readonly DependencyProperty IsBusyProperty = DependencyProperty.Register(
        nameof(IsBusy),
        typeof(bool),
        typeof(AgentFieldGraph),
        new FrameworkPropertyMetadata(false, FrameworkPropertyMetadataOptions.AffectsRender));

    public static readonly DependencyProperty HasErrorProperty = DependencyProperty.Register(
        nameof(HasError),
        typeof(bool),
        typeof(AgentFieldGraph),
        new FrameworkPropertyMetadata(false, FrameworkPropertyMetadataOptions.AffectsRender));

    public bool IsReady
    {
        get => (bool)GetValue(IsReadyProperty);
        set => SetValue(IsReadyProperty, value);
    }

    public bool IsBusy
    {
        get => (bool)GetValue(IsBusyProperty);
        set => SetValue(IsBusyProperty, value);
    }

    public bool HasError
    {
        get => (bool)GetValue(HasErrorProperty);
        set => SetValue(HasErrorProperty, value);
    }

    protected override void OnRender(DrawingContext drawingContext)
    {
        base.OnRender(drawingContext);
        if (ActualWidth <= 0 || ActualHeight <= 0)
        {
            return;
        }

        Brush accent = StateBrush();
        Brush edge = ResourceBrush("FieldEdgeBrush", Color.FromRgb(42, 53, 80));
        Brush node = ResourceBrush("GraphNodeBrush", Color.FromRgb(91, 127, 219));
        Brush label = ResourceBrush("MutedTextBrush", Color.FromRgb(91, 101, 128));
        var edgePen = new Pen(edge, 1);
        edgePen.Freeze();

        double padding = 18;
        double width = Math.Max(1, ActualWidth - (padding * 2));
        double height = Math.Max(1, ActualHeight - (padding * 2));
        Point Project(Point point) => new(
            padding + (point.X * width),
            padding + (point.Y * height));

        foreach ((int first, int second) in Edges)
        {
            drawingContext.DrawLine(edgePen, Project(Nodes[first]), Project(Nodes[second]));
        }

        for (int index = 0; index < Nodes.Length; index++)
        {
            Point point = Project(Nodes[index]);
            bool hub = index < 6;
            drawingContext.DrawEllipse(
                hub ? accent : node,
                null,
                point,
                hub ? 5.5 : 2.8,
                hub ? 5.5 : 2.8);
        }

        Point center = new(ActualWidth / 2, ActualHeight / 2);
        var halo = new RadialGradientBrush(
            ColorWithAlpha(ColorOf(accent), 150),
            ColorWithAlpha(ColorOf(accent), 0));
        halo.Freeze();
        double radius = Math.Clamp(Math.Min(ActualWidth, ActualHeight) * 0.16, 42, 94);
        drawingContext.DrawEllipse(halo, null, center, radius * 1.8, radius * 1.8);
        drawingContext.DrawEllipse(accent, null, center, radius * 0.42, radius * 0.42);
        drawingContext.DrawEllipse(
            ResourceBrush("TextBrush", Colors.White),
            null,
            center,
            radius * 0.13,
            radius * 0.13);

        string state = HasError ? "ERROR" : IsBusy ? "PENSANDO" : IsReady ? "LISTA" : "INICIANDO";
        var text = new FormattedText(
            state,
            CultureInfo.CurrentUICulture,
            FlowDirection.LeftToRight,
            new Typeface("Segoe UI Variable Text"),
            Math.Clamp(radius * 0.34, 16, 28),
            label,
            VisualTreeHelper.GetDpi(this).PixelsPerDip)
        {
            TextAlignment = TextAlignment.Center,
        };
        drawingContext.DrawText(text, new Point(center.X, center.Y + radius * 0.85));
    }

    protected override AutomationPeer OnCreateAutomationPeer() =>
        new DecorativeAutomationPeer(this);

    private Brush StateBrush()
    {
        if (HasError)
        {
            return ResourceBrush("ErrorBrush", Color.FromRgb(255, 123, 134));
        }

        if (IsBusy)
        {
            return ResourceBrush("ThinkingBrush", Color.FromRgb(91, 127, 219));
        }

        return IsReady
            ? ResourceBrush("AccentHoverBrush", Color.FromRgb(229, 83, 102))
            : ResourceBrush("MutedTextBrush", Color.FromRgb(91, 101, 128));
    }

    private Brush ResourceBrush(string key, Color fallback) =>
        TryFindResource(key) as Brush ?? new SolidColorBrush(fallback);

    private static Color ColorOf(Brush brush) =>
        brush is SolidColorBrush solid ? solid.Color : Color.FromRgb(184, 58, 74);

    private static Color ColorWithAlpha(Color color, byte alpha) =>
        Color.FromArgb(alpha, color.R, color.G, color.B);

    private sealed class DecorativeAutomationPeer(FrameworkElement owner)
        : FrameworkElementAutomationPeer(owner)
    {
        protected override bool IsContentElementCore() => false;

        protected override bool IsControlElementCore() => false;
    }
}
