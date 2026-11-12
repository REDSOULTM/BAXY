using System.IO;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// RED2 (2026-11-10): RED1 measured BAXY's window sending SmartScreen («nav-edge», «data-edge», «telem-edge»
/// .smartscreen.microsoft.com) the address it opens, BAXY's own page, at every start, and the privacy policy did not say
/// it. Neither view needs it: the window opens only BAXY's own files, and the hidden reader hands a page's markup on and
/// lets nobody act on it (no download, no other window, no dialog). In a real WebView2, what the window sets on its view
/// (MainWindow.KeepToBaxy) and what the reader sets (HiddenPageReader.KeepInside) leave the reputation check off.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class WebViewReputationTests
{
    [Test]
    public void NeitherViewAsksSmartScreenAboutWhatItOpens()
    {
        (bool? window, bool? reader, string? unavailable) = OnAWindowThread(async () =>
        {
            // One folder each, as in the App (webview2-field, webview2-search): SmartScreen is decided per folder, so a
            // shared one would let either view's setting answer for the other.
            string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
            var host = new Window
            {
                ShowInTaskbar = false,
                ShowActivated = false,
                WindowStyle = WindowStyle.None,
                ResizeMode = ResizeMode.NoResize,
                Left = -32000,
                Top = -32000,
                Width = 800,
                Height = 600,
            };
            var controllers = new List<CoreWebView2Controller>();
            try
            {
                IntPtr handle = new WindowInteropHelper(host).EnsureHandle();
                foreach (string view in new[] { "window", "reader" })
                {
                    CoreWebView2Environment environment = await CoreWebView2Environment.CreateAsync(
                        browserExecutableFolder: null, Path.Combine(folder, view),
                        new CoreWebView2EnvironmentOptions("--disable-gpu --mute-audio"));
                    controllers.Add(await environment.CreateCoreWebView2ControllerAsync(handle));
                }

                MainWindow.KeepToBaxy(controllers[0].CoreWebView2.Settings);
                HiddenPageReader.KeepInside(controllers[1].CoreWebView2);
                return (controllers[0].CoreWebView2.Settings.IsReputationCheckingRequired,
                    controllers[1].CoreWebView2.Settings.IsReputationCheckingRequired, null);
            }
            catch (Exception exception) when (exception is WebView2RuntimeNotFoundException or DllNotFoundException)
            {
                return (null, null, exception.GetType().Name);
            }
            finally
            {
                foreach (CoreWebView2Controller controller in controllers)
                {
                    controller.Close();
                }

                host.Close();
                try
                {
                    if (Directory.Exists(folder))
                    {
                        Directory.Delete(folder, recursive: true);
                    }
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    // The browser processes are still letting go of the profile: the temporary folder is swept with the rest.
                }
            }
        });

        if (unavailable is not null)
        {
            Assert.Ignore("No WebView2 on this machine: " + unavailable);
        }

        Assert.Multiple(() =>
        {
            Assert.That(window, Is.False, "BAXY's window still asks SmartScreen about the page it opens");
            Assert.That(reader, Is.False, "the hidden reader still asks SmartScreen about the page it reads");
        });
    }

    // WebView2 answers on the thread that made it, which has to pump messages: a thread of this test's with a dispatcher.
    private static (bool?, bool?, string?) OnAWindowThread(Func<Task<(bool?, bool?, string?)>> work)
    {
        (bool?, bool?, string?) outcome = default;
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            Dispatcher dispatcher = Dispatcher.CurrentDispatcher;
            SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));
            dispatcher.BeginInvoke(async () =>
            {
                try
                {
                    outcome = await work();
                }
                catch (Exception exception)
                {
                    failure = exception;
                }
                finally
                {
                    dispatcher.BeginInvokeShutdown(DispatcherPriority.Background);
                }
            });
            Dispatcher.Run();
        })
        {
            IsBackground = true,
            Name = "webview-reputation-test",
        };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        if (!thread.Join(TimeSpan.FromMinutes(2)))
        {
            Assert.Fail("The views did not answer in two minutes.");
        }

        if (failure is not null)
        {
            throw new AssertionException("The views failed: " + failure);
        }

        return outcome;
    }
}
