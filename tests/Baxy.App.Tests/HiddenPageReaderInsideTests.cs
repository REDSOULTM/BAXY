using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Revisión de la App 2026-11-09 (HPR-2): a page read where nobody sees it could go to an address Windows gives to a
/// program («ms-settings:», a mail client's, a game's), and nothing cancelled that launch. In a real WebView2, with what
/// the reader sets on its view (HiddenPageReader.KeepInside), on pages this test serves on the loopback: the launch and
/// a download are both cancelled before they start. The test's own handlers look at what the reader decided and then
/// cancel as well, so nothing opens on this PC even with the fix taken away.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class HiddenPageReaderInsideTests
{
    private static readonly TimeSpan Patience = TimeSpan.FromSeconds(20);

    [Test]
    public void APageReadUnseenOpensNoOtherApplicationAndDownloadsNothing()
    {
        Outcome outcome = OnAWindowThread(ReadBothPagesAsync);

        if (outcome.Unavailable is { } why)
        {
            Assert.Ignore("No WebView2 on this machine: " + why);
        }

        Assert.Multiple(() =>
        {
            Assert.That(outcome.LaunchCancelled, Is.True,
                "a page's address of another program was not cancelled (null: WebView2 never asked)");
            Assert.That(outcome.DownloadCancelled, Is.True,
                "a page's download was not cancelled (null: WebView2 never started one)");
        });
    }

    private static async Task<Outcome> ReadBothPagesAsync()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        using var pages = new Pages();
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
        CoreWebView2Controller? controller = null;
        try
        {
            IntPtr handle = new WindowInteropHelper(host).EnsureHandle();
            CoreWebView2Environment environment = await CoreWebView2Environment.CreateAsync(
                browserExecutableFolder: null, folder, new CoreWebView2EnvironmentOptions("--disable-gpu --mute-audio"));
            controller = await environment.CreateCoreWebView2ControllerAsync(handle);
            controller.IsVisible = false;
            CoreWebView2 view = controller.CoreWebView2;

            HiddenPageReader.KeepInside(view);

            // After every handler ran (the reader's among them), what was decided is read, and it is cancelled anyway.
            Dispatcher here = Dispatcher.CurrentDispatcher;
            var launch = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            var download = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            view.LaunchingExternalUriScheme += (_, asked) =>
            {
                CoreWebView2Deferral deferral = asked.GetDeferral();
                here.BeginInvoke(() =>
                {
                    launch.TrySetResult(asked.Cancel);
                    asked.Cancel = true;
                    deferral.Complete();
                });
            };
            view.DownloadStarting += (_, asked) =>
            {
                CoreWebView2Deferral deferral = asked.GetDeferral();
                here.BeginInvoke(() =>
                {
                    download.TrySetResult(asked.Cancel);
                    asked.Cancel = true;
                    deferral.Complete();
                });
            };

            view.Navigate(pages.Address + "abre");
            if (await Task.WhenAny(launch.Task, Task.Delay(Patience)) != launch.Task)
            {
                // A page's own script may be held back for want of a gesture; the address itself raises it as well.
                view.Navigate("ms-settings:about");
            }

            bool? launched = await Task.WhenAny(launch.Task, Task.Delay(Patience)) == launch.Task ? launch.Task.Result : null;
            view.Navigate(pages.Address + "baja");
            bool? downloaded = await Task.WhenAny(download.Task, Task.Delay(Patience)) == download.Task
                ? download.Task.Result
                : null;
            return new Outcome(launched, downloaded, null);
        }
        catch (Exception exception) when (exception is WebView2RuntimeNotFoundException or DllNotFoundException)
        {
            return new Outcome(null, null, exception.GetType().Name);
        }
        finally
        {
            controller?.Close();
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
    }

    // WebView2 answers on the thread that made it, which has to pump messages: a thread of this test's with a dispatcher.
    private static Outcome OnAWindowThread(Func<Task<Outcome>> work)
    {
        Outcome? outcome = null;
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
            Name = "hidden-page-reader-test",
        };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        if (!thread.Join(TimeSpan.FromMinutes(2)))
        {
            Assert.Fail("The hidden view did not answer in two minutes.");
        }

        if (failure is not null)
        {
            throw new AssertionException("The hidden view failed: " + failure);
        }

        return outcome!;
    }

    private sealed record Outcome(bool? LaunchCancelled, bool? DownloadCancelled, string? Unavailable);

    // Two pages on the loopback: one whose script goes to another program's address, one that is a file to download.
    private sealed class Pages : IDisposable
    {
        private readonly TcpListener _listener = new(IPAddress.Loopback, 0);
        private readonly CancellationTokenSource _closing = new();

        internal Pages()
        {
            _listener.Start();
            Address = $"http://127.0.0.1:{((IPEndPoint)_listener.LocalEndpoint).Port}/";
            _ = Task.Run(ServeAsync);
        }

        internal string Address { get; }

        public void Dispose()
        {
            _closing.Cancel();
            _listener.Stop();
            _closing.Dispose();
        }

        private async Task ServeAsync()
        {
            try
            {
                while (!_closing.IsCancellationRequested)
                {
                    // Each connection on its own: a browser opens some ahead of time and sends nothing on them.
                    TcpClient client = await _listener.AcceptTcpClientAsync(_closing.Token);
                    _ = Task.Run(() => AnswerAsync(client));
                }
            }
            catch (Exception exception) when (exception is OperationCanceledException or SocketException
                or ObjectDisposedException)
            {
                // The test ended.
            }
        }

        private async Task AnswerAsync(TcpClient connection)
        {
            try
            {
                using (TcpClient client = connection)
                {
                    using NetworkStream stream = client.GetStream();
                    using var reader = new StreamReader(stream, Encoding.ASCII, false, 4096, leaveOpen: true);
                    string? request = await reader.ReadLineAsync(_closing.Token);
                    while (await reader.ReadLineAsync(_closing.Token) is { Length: > 0 })
                    {
                    }

                    bool file = request?.Contains("/baja", StringComparison.Ordinal) == true;
                    byte[] body = file
                        ? [1, 2, 3, 4]
                        : Encoding.UTF8.GetBytes("<!doctype html><title>prueba</title><p>hola</p>"
                            + (request?.Contains("/abre", StringComparison.Ordinal) == true
                                ? "<script>location.href='ms-settings:about';</script>"
                                : string.Empty));
                    string head = "HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: " + body.Length + "\r\n"
                        + (file
                            ? "Content-Type: application/octet-stream\r\nContent-Disposition: attachment; filename=\"prueba.bin\"\r\n"
                            : "Content-Type: text/html; charset=utf-8\r\n")
                        + "\r\n";
                    await stream.WriteAsync(Encoding.ASCII.GetBytes(head), _closing.Token);
                    await stream.WriteAsync(body, _closing.Token);
                }
            }
            catch (Exception exception) when (exception is OperationCanceledException or IOException or SocketException
                or ObjectDisposedException)
            {
                // The test ended.
            }
        }
    }
}
