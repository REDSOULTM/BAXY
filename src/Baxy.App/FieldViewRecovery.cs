namespace Baxy.App;

/// <summary>What the App does when one of WebView2's processes fails (MainWindow.RecoveryFor).</summary>
internal enum FieldViewRecovery
{
    /// <summary>The runtime recovers by itself: the interface stays as it is.</summary>
    None,

    /// <summary>The main frame's renderer ended and left an error page: the page is loaded again.</summary>
    Reload,

    /// <summary>The browser process ended and closed the WebView: it has to be opened again.</summary>
    Recreate,
}
