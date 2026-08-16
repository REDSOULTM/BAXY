using System.Windows.Controls;

namespace Baxy.App.Presentation;

internal partial class FieldLoadingSurface : UserControl
{
    internal FieldLoadingSurface()
    {
        InitializeComponent();
    }

    internal void SetStatus(string message, string? diagnostic = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(message);
        StatusText.Text = message;
        StatusText.ToolTip = diagnostic;
    }
}
