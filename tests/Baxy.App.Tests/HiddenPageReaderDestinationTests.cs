using System.Collections.Concurrent;
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
/// PRIV-05 (revisión de privacidad 2026-11-09): the hidden reader is a browser, and a page it reads could send it into
/// this PC or the local network (a redirect, a script that goes there, an image, a fetch, a frame, a socket): to the
/// model's own server, another program's, the router. In a real WebView2, hidden, with what the reader sets on its
/// browser and its view (HiddenPageReader.BrowserArguments, KeepPublic): a page with a public name is read, and
/// nothing it does reaches a second server that stands for the private one, asked by its address and by a name that
/// resolves into the local network. Both servers are this test's, on the loopback; the browser is told the two names
/// are there, and the reader is told what they resolve to «outside» (a public address, a local one).
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class HiddenPageReaderDestinationTests
{
    private const string PublicName = "publica.example";
    private const string LocalName = "interna.example";
    private static readonly TimeSpan Patience = TimeSpan.FromSeconds(20);

    [TestCase("https://example.com/a?b=1", true)]
    [TestCase("http://93.184.216.34/", true)]
    [TestCase("about:blank", true)]
    [TestCase("about:srcdoc", true)]
    [TestCase("data:text/html,hola", true)]
    [TestCase("blob:https://example.com/0b1e8a6c", true)]
    [TestCase("http://127.0.0.1:8080/v1/models", false)]
    [TestCase("http://localhost:11434/api/tags", false)]
    [TestCase("http://192.168.1.1/", false)]
    [TestCase("http://[::1]:8080/", false)]
    [TestCase("https://router/", false)]
    [TestCase("https://nas.local/", false)]
    [TestCase("https://user:pass@example.com/", false)]
    [TestCase("file:///C:/Users/x/secret.txt", false)]
    [TestCase("ftp://example.com/a", false)]
    [TestCase("no es una dirección", false)]
    [TestCase("", false)]
    public void OnlyAPublicAddressOrThePagesOwnContentMayStart(string uri, bool may)
    {
        Assert.That(HiddenPageReader.MayStart(uri), Is.EqualTo(may));
    }

    [Test]
    public void NothingAPageDoesReachesThisPcOrTheLocalNetwork()
    {
        Outcome outcome = OnAWindowThread(ReadThePagesAsync);

        if (outcome.Unavailable is { } why)
        {
            Assert.Ignore("No WebView2 on this machine: " + why);
        }

        Assert.Multiple(() =>
        {
            // The public page is still read, with what its script did after (it tells when it is done).
            Assert.That(outcome.Page, Is.EqualTo("loaded"), "the public page");
            Assert.That(outcome.Finished, Is.True, "the public page's script did not finish: " + string.Join(' ', outcome.Public));
            Assert.That(outcome.Private, Is.Empty, "requests that reached the private server");
            Assert.That(outcome.Reads.Select(static read => read.Key + " " + read.Value), Is.EqualTo(new[]
            {
                "ir failed", "ir-nombre failed", "directa failed", "directa-nombre failed",
            }), "pages that end on the private server");
            Assert.That(outcome.Socket, Is.Empty, "sockets that reached the private server");
        });
    }

    private static async Task<Outcome> ReadThePagesAsync()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        using var open = new Side();
        using var closed = new Side();
        string literal = $"http://127.0.0.1:{closed.Port}/";
        string named = $"http://{LocalName}:{closed.Port}/";
        string home = $"http://{PublicName}:{open.Port}/";
        closed.Answers = static _ => Reply.Page("<!doctype html><title>privada</title><p>secreto</p>");
        open.Answers = path => path switch
        {
            "/pagina" => Reply.Page(Busy(literal, named)),
            "/salta" => Reply.Elsewhere(literal + "saltada"),
            "/salta-nombre" => Reply.Elsewhere(named + "saltada-nombre"),
            "/ir" => Reply.Elsewhere(literal + "ida"),
            "/ir-nombre" => Reply.Elsewhere(named + "ida-nombre"),
            "/navega" => Reply.Page(Leaves(literal + "navegada", "/fin-navega")),
            "/navega-nombre" => Reply.Page(Leaves(named + "navegada-nombre", "/fin-navega-nombre")),
            "/zocalo" => Reply.Page(Sockets($"ws://127.0.0.1:{closed.Port}/", $"ws://{LocalName}:{closed.Port}/")),
            _ => Reply.Page("<!doctype html><title>prueba</title><p>hola</p>"),
        };
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
        // The browser lets go of its folder when its processes have ended, and says so: «BrowserProcessExited is raised
        // when the collection of WebView2 Runtime processes for the browser process of this CoreWebView2Environment
        // terminate due to browser process failure or normal shutdown (for example, when all associated WebViews are
        // closed), after all resources have been released (including the user data folder)» (WebView2 SDK reference,
        // CoreWebView2Environment.BrowserProcessExited, read 2026-11-09). Deleting before that left the folder behind.
        var released = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        try
        {
            IntPtr handle = new WindowInteropHelper(host).EnsureHandle();
            // The browser finds both names on the loopback; nothing here asks a name server.
            var options = new CoreWebView2EnvironmentOptions(HiddenPageReader.BrowserArguments + " --host-resolver-rules=\""
                + $"MAP {PublicName} 127.0.0.1, MAP {LocalName} 127.0.0.1\"");
            CoreWebView2Environment environment = await CoreWebView2Environment.CreateAsync(
                browserExecutableFolder: null, folder, options);
            environment.BrowserProcessExited += (_, _) => released.TrySetResult();
            controller = await environment.CreateCoreWebView2ControllerAsync(handle);
            controller.IsVisible = false;

            HiddenPageReader.KeepPublic(controller.CoreWebView2, environment, Outside);

            // The reader leaves a page once read (REV_APP HPR-1, HiddenPageReader.LeaveAsync): a page whose script has to
            // go on after the read is loaded again and left as it is (StayAsync), the view and its guard the same.
            string page = await ReadAsync(controller, home + "pagina");
            await StayAsync(controller, home + "pagina");
            bool finished = await SawAsync(open, "/fin", closed, null);
            var reads = new Dictionary<string, string>();
            foreach (string path in new[] { "ir", "ir-nombre" })
            {
                reads[path] = await ReadAsync(controller, home + path);
            }

            foreach (string path in new[] { "navega", "navega-nombre" })
            {
                await StayAsync(controller, home + path);
                await SawAsync(open, "/fin-" + path, closed, "/navegada");
            }

            reads["directa"] = await ReadAsync(controller, literal + "directa");
            reads["directa-nombre"] = await ReadAsync(controller, named + "directa-nombre");
            string[] before = closed.Asked;
            await StayAsync(controller, home + "zocalo");
            await SawAsync(open, "/fin-zocalo", closed, null);
            return new Outcome(null, page, finished, reads, before, open.Asked,
                string.Join(' ', closed.Asked.Skip(before.Length)));
        }
        catch (Exception exception) when (exception is WebView2RuntimeNotFoundException or DllNotFoundException)
        {
            return new Outcome(
                exception.GetType().Name, string.Empty, false, new Dictionary<string, string>(), [], [], string.Empty);
        }
        finally
        {
            if (controller is not null)
            {
                controller.Close();
                await Task.WhenAny(released.Task, Task.Delay(Patience));
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
                // The browser did not say it had ended in time: the temporary folder is swept with the rest.
            }
        }
    }

    // What the two names resolve to for the reader: one public address, one of a local network.
    private static Task<IPAddress[]> Outside(string host, CancellationToken cancellationToken) => host switch
    {
        PublicName => Task.FromResult<IPAddress[]>([IPAddress.Parse("93.184.216.34")]),
        LocalName => Task.FromResult<IPAddress[]>([IPAddress.Parse("192.168.1.10")]),
        _ => Task.FromException<IPAddress[]>(new SocketException((int)SocketError.HostNotFound)),
    };

    private static async Task<string> ReadAsync(CoreWebView2Controller controller, string address)
    {
        string line = await HiddenPageReader.ReadAsync(controller, new Uri(address), Patience, TimeSpan.Zero);
        using JsonDocument answer = JsonDocument.Parse(line);
        return answer.RootElement.GetProperty("outcome").GetString() ?? string.Empty;
    }

    // A page loaded in the reader's view and not left, so that its script runs on after it loaded.
    private static async Task StayAsync(CoreWebView2Controller controller, string address)
    {
        var loaded = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        void Completed(object? sender, CoreWebView2NavigationCompletedEventArgs completed) => loaded.TrySetResult();
        controller.CoreWebView2.NavigationCompleted += Completed;
        try
        {
            controller.CoreWebView2.Navigate(address);
            await Task.WhenAny(loaded.Task, Task.Delay(Patience));
        }
        finally
        {
            controller.CoreWebView2.NavigationCompleted -= Completed;
        }
    }

    // Waits for the page to say it is done (a request to the public server), or for the private server to be asked.
    private static async Task<bool> SawAsync(Side open, string done, Side closed, string? reached)
    {
        for (TimeSpan waited = TimeSpan.Zero; waited < Patience; waited += TimeSpan.FromMilliseconds(50))
        {
            if (open.Asked.Contains(done, StringComparer.Ordinal))
            {
                return true;
            }

            if (reached is not null && closed.Asked.Any(path => path.StartsWith(reached, StringComparison.Ordinal)))
            {
                return false;
            }

            await Task.Delay(50);
        }

        return false;
    }

    // A page that asks the private server every way a page can without a person: a fetch, an image, a frame and a
    // worker, by its address and by its name, and an image and a fetch of its own site that are sent there. When each
    // has ended, one way or the other, it says so.
    private static string Busy(string literal, string named) =>
        "<!doctype html><title>prueba</title><p>hola</p><script>\n"
        + "const ends = [];\n"
        + "const soon = settle => setTimeout(settle, 4000);\n"
        + "const image = at => new Promise(settle => { const i = new Image(); i.onload = i.onerror = settle; i.src = at; soon(settle); });\n"
        + "const frame = at => new Promise(settle => { const f = document.createElement('iframe'); f.onload = f.onerror = settle; f.src = at; document.body.appendChild(f); soon(settle); });\n"
        + "const worker = at => new Promise(settle => { try { const w = new Worker(URL.createObjectURL(new Blob([\"fetch('\" + at + \"', {mode: 'no-cors'}).catch(() => 0).finally(() => postMessage(1))\"]))); w.onmessage = w.onerror = settle; } catch (error) { settle(); } soon(settle); });\n"
        + "const asked = at => fetch(at, {mode: 'no-cors'}).catch(() => 0);\n"
        + $"for (const there of ['{literal}', '{named}']) {{\n"
        + "  ends.push(asked(there + 'pedida'), image(there + 'imagen'), frame(there + 'marco'), worker(there + 'obrero'));\n"
        + "}\n"
        + "ends.push(image('/salta'), asked('/salta'), image('/salta-nombre'), asked('/salta-nombre'));\n"
        + "Promise.allSettled(ends).then(() => fetch('/fin'));\n"
        + "</script>";

    private static string Sockets(string literal, string named) =>
        "<!doctype html><title>prueba</title><p>hola</p><script>\n"
        + "const socket = at => new Promise(settle => { try { const s = new WebSocket(at); s.onopen = s.onerror = s.onclose = settle; } catch (error) { settle(); } setTimeout(settle, 4000); });\n"
        + $"Promise.allSettled([socket('{literal}zocalo'), socket('{named}zocalo-nombre')]).then(() => fetch('/fin-zocalo'));\n"
        + "</script>";

    // A page whose script goes to the private server, and says so if it is still there afterwards.
    private static string Leaves(string there, string done) =>
        "<!doctype html><title>prueba</title><p>hola</p><script>\n"
        + $"setTimeout(() => {{ location.href = '{there}'; }}, 50);\n"
        + $"setTimeout(() => fetch('{done}'), 1500);\n"
        + "</script>";

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
            Name = "hidden-page-reader-destination-test",
        };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        if (!thread.Join(TimeSpan.FromMinutes(4)))
        {
            Assert.Fail("The hidden view did not answer in four minutes.");
        }

        if (failure is not null)
        {
            throw new AssertionException("The hidden view failed: " + failure);
        }

        return outcome ?? throw new AssertionException("The hidden view gave no outcome.");
    }

    private sealed record Outcome(
        string? Unavailable,
        string Page,
        bool Finished,
        IReadOnlyDictionary<string, string> Reads,
        string[] Private,
        string[] Public,
        string Socket);

    private sealed record Reply(int Status, string? Location, string Body)
    {
        internal static Reply Page(string body) => new(200, null, body);

        internal static Reply Elsewhere(string location) => new(302, location, string.Empty);
    }

    // A web server on the loopback that keeps the path of every request it was sent.
    private sealed class Side : IDisposable
    {
        private readonly TcpListener _listener = new(IPAddress.Loopback, 0);
        private readonly CancellationTokenSource _closing = new();
        private readonly ConcurrentQueue<string> _asked = new();

        internal Side()
        {
            _listener.Start();
            Port = ((IPEndPoint)_listener.LocalEndpoint).Port;
            _ = Task.Run(ServeAsync);
        }

        internal int Port { get; }

        internal Func<string, Reply> Answers { get; set; } = static _ => Reply.Page(string.Empty);

        internal string[] Asked => [.. _asked];

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

                    if (request?.Split(' ') is not [_, string path, ..])
                    {
                        return;
                    }

                    _asked.Enqueue(path);
                    Reply reply = Answers(path);
                    byte[] body = Encoding.UTF8.GetBytes(reply.Body);
                    string head = $"HTTP/1.1 {reply.Status} -\r\nConnection: close\r\nContent-Length: {body.Length}\r\n"
                        + "Content-Type: text/html; charset=utf-8\r\nAccess-Control-Allow-Origin: *\r\n"
                        + (reply.Location is null ? string.Empty : $"Location: {reply.Location}\r\n")
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
