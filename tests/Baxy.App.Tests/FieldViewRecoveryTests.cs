using Microsoft.Web.WebView2.Core;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Uso 95 (uso real 2026-11-04 12:06): with the PC out of memory WebView2's GPU process died twice and the App replaced
/// the interface with «Vuelve a abrir BAXY» for a failure the runtime recovers from by itself (Microsoft, «Handling
/// process-related events in WebView2»).
/// </summary>
[TestFixture]
public sealed class FieldViewRecoveryTests
{
    [TestCase(CoreWebView2ProcessFailedKind.GpuProcessExited, "None")]
    [TestCase(CoreWebView2ProcessFailedKind.UtilityProcessExited, "None")]
    [TestCase(CoreWebView2ProcessFailedKind.SandboxHelperProcessExited, "None")]
    [TestCase(CoreWebView2ProcessFailedKind.FrameRenderProcessExited, "None")]
    [TestCase(CoreWebView2ProcessFailedKind.RenderProcessUnresponsive, "None")]
    [TestCase(CoreWebView2ProcessFailedKind.UnknownProcessExited, "None")]
    [TestCase(CoreWebView2ProcessFailedKind.RenderProcessExited, "Reload")]
    [TestCase(CoreWebView2ProcessFailedKind.BrowserProcessExited, "Recreate")]
    public void EachFailedProcessGetsWhatTheRuntimeAsksFor(CoreWebView2ProcessFailedKind kind, string expected)
    {
        Assert.That(MainWindow.RecoveryFor(kind), Is.EqualTo(Enum.Parse<FieldViewRecovery>(expected)));
    }

    // A window on another profile no longer shares the view's preferences with the person's BAXY; the person's folder stays.
    [TestCase(null, @"C:\L\BAXY\webview2-field")]
    [TestCase("  ", @"C:\L\BAXY\webview2-field")]
    [TestCase(@"C:\L\BAXY\1", @"C:\L\BAXY\webview2-field")]
    [TestCase(@"c:\l\baxy\1\", @"C:\L\BAXY\webview2-field")]
    [TestCase(@"D:\prueba\perfil", @"D:\prueba\perfil\webview2-field")]
    [TestCase(@"C:\L\BAXY\nv-p1", @"C:\L\BAXY\nv-p1\webview2-field")]
    public void EachProfileHasItsViewFolder(string? profile, string expected)
    {
        Assert.That(MainWindow.FieldViewDataFolder(profile, @"C:\L"), Is.EqualTo(expected));
    }
}
