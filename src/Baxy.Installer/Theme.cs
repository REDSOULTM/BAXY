using System.Windows;
using System.Windows.Media;

namespace Baxy.Installer;

internal enum ThemeKind
{
    Dark,
    Light,
    HighContrast,
}

/// <summary>BAXY's colors (src/Baxy.FieldUi/src/styles), chosen so each pair passes WCAG (ThemeTests measures them).</summary>
internal sealed record Palette(
    string Background,
    string Text,
    string Second,
    string Line,
    string Track,
    string Bar,
    string Ok,
    string Now,
    string Primary,
    string PrimaryHover,
    string OnPrimary,
    string Ring,
    string QuietHover,
    string Panel,
    string PanelText,
    string PanelLine,
    string PanelHover,
    string PanelRing);

internal static class Theme
{
    internal static readonly Palette Dark = new(
        "#0F1419", "#E4E8F0", "#B4BDD0", "#667089", "#2A3550", "#7B95D9", "#7FD1A8", "#9DB4F0", "#B83A4A", "#C94A5A",
        "#FFFFFF", "#9DB4F0", "#1F2733", "#060A18", "#E4E8F0", "#667089", "#1F2733", "#9DB4F0");

    internal static readonly Palette Light = new(
        "#F7F8FA", "#161B26", "#3E4759", "#6B7588", "#D6DBE4", "#2E4BA0", "#146B45", "#2E4BA0", "#A82E3E", "#8F2533",
        "#FFFFFF", "#2E4BA0", "#E9ECF2", "#060A18", "#E4E8F0", "#667089", "#1F2733", "#9DB4F0");

    internal static readonly Palette HighContrast = new(
        "#000000", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#000000", "#FFE500", "#FFFFFF", "#FFE500", "#FFE500", "#FFFFFF",
        "#000000", "#00E5FF", "#333333", "#000000", "#FFFFFF", "#FFFFFF", "#333333", "#00E5FF");

    /// <summary>With Windows in high contrast its own colors rule, whichever palette the person chose in Windows.</summary>
    internal static void Apply(ResourceDictionary resources, ThemeKind kind)
    {
        if (kind == ThemeKind.HighContrast && SystemParameters.HighContrast)
        {
            ApplySystem(resources);
            return;
        }

        Palette palette = kind switch
        {
            ThemeKind.Light => Light,
            ThemeKind.HighContrast => HighContrast,
            _ => Dark,
        };
        Set(resources, "Background", palette.Background);
        Set(resources, "Text", palette.Text);
        Set(resources, "Second", palette.Second);
        Set(resources, "Line", palette.Line);
        Set(resources, "Track", palette.Track);
        Set(resources, "Bar", palette.Bar);
        Set(resources, "Ok", palette.Ok);
        Set(resources, "Now", palette.Now);
        Set(resources, "Primary", palette.Primary);
        Set(resources, "PrimaryHover", palette.PrimaryHover);
        Set(resources, "OnPrimary", palette.OnPrimary);
        Set(resources, "Ring", palette.Ring);
        Set(resources, "QuietHover", palette.QuietHover);
        Set(resources, "Panel", palette.Panel);
        Set(resources, "PanelText", palette.PanelText);
        Set(resources, "PanelLine", palette.PanelLine);
        Set(resources, "PanelHover", palette.PanelHover);
        Set(resources, "PanelRing", palette.PanelRing);
    }

    private static void ApplySystem(ResourceDictionary resources)
    {
        resources["Background"] = SystemColors.WindowBrush;
        resources["Text"] = SystemColors.WindowTextBrush;
        resources["Second"] = SystemColors.WindowTextBrush;
        resources["Line"] = SystemColors.WindowTextBrush;
        resources["Track"] = SystemColors.WindowBrush;
        resources["Bar"] = SystemColors.HighlightBrush;
        resources["Ok"] = SystemColors.WindowTextBrush;
        resources["Now"] = SystemColors.HotTrackBrush;
        resources["Primary"] = SystemColors.HighlightBrush;
        resources["PrimaryHover"] = SystemColors.HotTrackBrush;
        resources["OnPrimary"] = SystemColors.HighlightTextBrush;
        resources["Ring"] = SystemColors.HotTrackBrush;
        resources["QuietHover"] = SystemColors.ControlBrush;
        resources["Panel"] = SystemColors.WindowBrush;
        resources["PanelText"] = SystemColors.WindowTextBrush;
        resources["PanelLine"] = SystemColors.WindowTextBrush;
        resources["PanelHover"] = SystemColors.ControlBrush;
        resources["PanelRing"] = SystemColors.HotTrackBrush;
    }

    private static void Set(ResourceDictionary resources, string key, string hex)
    {
        SolidColorBrush brush = new((Color)ColorConverter.ConvertFromString(hex));
        brush.Freeze();
        resources[key] = brush;
    }
}
