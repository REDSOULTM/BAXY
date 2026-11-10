using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// REV_APP HPR-1 (2026-11-09): a page read where nobody sees it stayed loaded after it was read, its scripts running and
/// asking the network until the reader ended (ten minutes with nothing to read, HiddenPageReaderHost.IdleEnd), and what
/// it kept (a cookie, its storage) was there for the next page, on the disk, from one search to the next. In a real
/// WebView2, with the reader's own read (HiddenPageReader.ReadAsync), on pages this test serves on the loopback.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class HiddenPageReaderAfterTests
{
    private static readonly TimeSpan Within = TimeSpan.FromSeconds(15);
    private Seen? _seen;

    [OneTimeSetUp]
    public void ReadTwoPages() => _seen = OnAWindowThread(ReadTwoPagesAsync);

    [Test]
    public void APageAlreadyReadAsksTheNetworkNothingMore()
    {
        Seen seen = Available();
        Assert.Multiple(() =>
        {
            Assert.That(seen.First, Is.EqualTo("loaded"));
            Assert.That(seen.AskedWhileRead, Is.GreaterThan(0), "the page's script never ran: the test saw nothing");
            Assert.That(seen.AskedLater, Is.EqualTo(seen.AskedOnceRead),
                "the page went on asking the network after it was read");
        });
    }

    [Test]
    public void WhatAPageKeptIsNotThereForTheNextOne()
    {
        Seen seen = Available();
        Assert.Multiple(() =>
        {
            Assert.That(seen.Second, Is.EqualTo("loaded"));
            Assert.That(seen.CookieSentBack, Is.Null.Or.Empty, "the cookie the first page set went with the next read");
            Assert.That(seen.SecondMarkup, Does.Contain("<title>nada</title>"),
                "what the first page stored was there for the next one");
        });
    }

    private Seen Available()
    {
        Seen seen = _seen!;
        if (seen.Unavailable is { } why)
        {
            Assert.Ignore("No WebView2 on this machine: " + why);
        }

        return seen;
    }

    private static async Task<Seen> ReadTwoPagesAsync()
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

            var clock = Stopwatch.StartNew();
            string first = await HiddenPageReader.ReadAsync(controller, new Uri(pages.Address + "vive"), Within, TimeSpan.FromSeconds(1));
            TimeSpan firstTook = clock.Elapsed;
            int whileRead = pages.Asked("/late");
            // A request already on its way when the read ended may still arrive.
            await Task.Delay(500);
            int onceRead = pages.Asked("/late");
            await Task.Delay(2000);
            int later = pages.Asked("/late");

            clock.Restart();
            string second = await HiddenPageReader.ReadAsync(controller, new Uri(pages.Address + "otra"), Within, TimeSpan.Zero);
            await TestContext.Progress.WriteLineAsync(
                $"hidden reads: first {firstTook.TotalMilliseconds:0} ms (1 s of settle), second {clock.Elapsed.TotalMilliseconds:0} ms; "
                + $"asked while read {whileRead}, once read {onceRead}, 2 s later {later}");
            using JsonDocument one = JsonDocument.Parse(first);
            using JsonDocument two = JsonDocument.Parse(second);
            return new Seen(
                one.RootElement.GetProperty("outcome").GetString(),
                whileRead,
                onceRead,
                later,
                two.RootElement.GetProperty("outcome").GetString(),
                pages.CookieOf("/otra"),
                two.RootElement.GetProperty("html").GetString() ?? string.Empty,
                null);
        }
        catch (Exception exception) when (exception is WebView2RuntimeNotFoundException or DllNotFoundException)
        {
            return new Seen(null, 0, 0, 0, null, null, string.Empty, exception.GetType().Name);
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
                // The browser's processes are still letting go of the profile: the temporary folder is swept with the rest.
            }
        }
    }

    // WebView2 answers on the thread that made it, which has to pump messages: a thread of this test's with a dispatcher.
    private static Seen OnAWindowThread(Func<Task<Seen>> work)
    {
        Seen? seen = null;
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            Dispatcher dispatcher = Dispatcher.CurrentDispatcher;
            SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));
            dispatcher.BeginInvoke(async () =>
            {
                try
                {
                    seen = await work();
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
            Name = "hidden-page-reader-after-test",
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

        return seen!;
    }

    private sealed record Seen(
        string? First,
        int AskedWhileRead,
        int AskedOnceRead,
        int AskedLater,
        string? Second,
        string? CookieSentBack,
        string SecondMarkup,
        string? Unavailable);

    // Two pages on the loopback. «vive» sets a cookie, stores a word and asks for «late» at once and then ten times a second, as a
    // page with a counter or an ad does; «otra» says in its title what it found stored, and the server notes its cookie.
    private sealed class Pages : IDisposable
    {
        private const string Lives = "<!doctype html><title>vive</title><p>hola</p><script>"
            + "try { localStorage.setItem('visto', 'si'); } catch (e) {}"
            + "function ask() { fetch('/late?' + Date.now()).catch(function () {}); } ask(); setInterval(ask, 100);</script>";
        private const string Other = "<!doctype html><title>otra</title><p>hola</p><script>"
            + "var kept = null; try { kept = localStorage.getItem('visto'); } catch (e) {}"
            + "document.title = kept || 'nada';</script>";

        private readonly TcpListener _listener = new(IPAddress.Loopback, 0);
        private readonly CancellationTokenSource _closing = new();
        private readonly object _sync = new();
        private readonly List<(string Path, string? Cookie)> _asked = [];

        internal Pages()
        {
            _listener.Start();
            Address = $"http://127.0.0.1:{((IPEndPoint)_listener.LocalEndpoint).Port}/";
            _ = Task.Run(ServeAsync);
        }

        internal string Address { get; }

        internal int Asked(string path)
        {
            lock (_sync)
            {
                return _asked.Count(asked => asked.Path.StartsWith(path, StringComparison.Ordinal));
            }
        }

        internal string? CookieOf(string path)
        {
            lock (_sync)
            {
                return _asked.LastOrDefault(asked => asked.Path.StartsWith(path, StringComparison.Ordinal)).Cookie;
            }
        }

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
                    string? cookie = null;
                    while (await reader.ReadLineAsync(_closing.Token) is { Length: > 0 } header)
                    {
                        if (header.StartsWith("Cookie:", StringComparison.OrdinalIgnoreCase))
                        {
                            cookie = header["Cookie:".Length..].Trim();
                        }
                    }

                    string[] parts = request?.Split(' ') ?? [];
                    if (parts.Length < 2)
                    {
                        return;
                    }

                    string path = parts[1];
                    lock (_sync)
                    {
                        _asked.Add((path, cookie));
                    }

                    bool lives = path.StartsWith("/vive", StringComparison.Ordinal);
                    byte[] body = Encoding.UTF8.GetBytes(
                        lives ? Lives : path.StartsWith("/otra", StringComparison.Ordinal) ? Other : string.Empty);
                    string head = "HTTP/1.1 200 OK\r\nConnection: close\r\nCache-Control: no-store\r\nContent-Length: "
                        + body.Length + "\r\nContent-Type: text/html; charset=utf-8\r\n"
                        + (lives ? "Set-Cookie: visto=si; Max-Age=3600; Path=/\r\n" : string.Empty)
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
