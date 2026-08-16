using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Microsoft.Web.WebView2.Wpf;

namespace Baxy.App.Presentation;

internal sealed class MainWindowSurfacePresenter : IAppSurfacePresenter
{
    private readonly WebView2 _field;
    private readonly ContentControl _surfaceHost;

    internal MainWindowSurfacePresenter(
        WebView2 field,
        ContentControl surfaceHost)
    {
        _field = field ?? throw new ArgumentNullException(nameof(field));
        _surfaceHost = surfaceHost
            ?? throw new ArgumentNullException(nameof(surfaceHost));
    }

    public void ShowField()
    {
        VerifyAccess();
        _surfaceHost.Visibility = Visibility.Collapsed;
        _surfaceHost.Content = null;
        _field.Visibility = Visibility.Visible;
        _ = _field.Focus();
    }

    public void ShowSurface(AppSurfaceSession session)
    {
        ArgumentNullException.ThrowIfNull(session);
        VerifyAccess();
        try
        {
            _surfaceHost.Content = session.Content;
            _surfaceHost.Visibility = Visibility.Visible;
            _field.Visibility = Visibility.Collapsed;
            _ = session.Content.MoveFocus(
                new TraversalRequest(FocusNavigationDirection.First));
        }
        catch
        {
            ShowField();
            throw;
        }
    }

    private void VerifyAccess()
    {
        _field.Dispatcher.VerifyAccess();
        _surfaceHost.Dispatcher.VerifyAccess();
    }
}
