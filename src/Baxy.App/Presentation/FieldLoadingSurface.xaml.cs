using System.Windows.Automation;
using System.Windows.Controls;

namespace Baxy.App.Presentation;

internal sealed partial class FieldLoadingSurface : UserControl
{
    internal FieldLoadingSurface()
    {
        InitializeComponent();
        // Steam (2026-11-04): the start's screen speaks the interface's language kept from the last run (UiLanguage).
        bool english = UiLanguage.IsEnglish;
        AutomationProperties.SetName(Frame, UiLanguage.Say(english, "Estado de carga de BAXY Field", "BAXY Field loading state"));
        StatusText.Text = LoadingIn(english);
    }

    /// <summary>What the screen says while the view loads.</summary>
    internal static string Loading => LoadingIn(UiLanguage.IsEnglish);

    private static string LoadingIn(bool english) =>
        UiLanguage.Say(english, "Recuperando la interfaz histórica local…", "Loading the local interface…");

    internal void SetStatus(string message, string? diagnostic = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(message);
        StatusText.Text = message;
        StatusText.ToolTip = diagnostic;
    }
}
