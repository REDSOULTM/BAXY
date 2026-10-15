using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Pasada r15b v3-57 «abre edge en una pestaña nueva y busca clima en guadalajara»: browser.navigate.named read
// bing.com/search?q=clima+en+guadalajara in the CDP Edge BAXY started (profile browser-session-v1\edge, its
// DevToolsActivePort written 00:40:58.86), the final went out at 00:41:01, the profile's last write was 00:41:01.23
// and at 00:41:07 no Edge window was left: the browser had been started from the core, inside the App's kill-on-close
// job, and Dispose killed its tree (DevToolsActivePort was never removed and Preferences never saved: no clean exit).
// The page is the person's window, so it leaves the job like an application BAXY opens and outlives BAXY.
[TestFixture]
public sealed class CuV3HonestidadR15b2EdgeTests
{
    private const string Edge = @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";
    private const string Profile = @"C:\Users\usuario\AppData\Local\BAXY\browser-session-v1\edge";

    [Test]
    public void TwinV357TheBrowserLeavesTheJobAndInheritsNothing()
    {
        var environment = new System.Collections.Hashtable { ["Path"] = @"C:\Windows", ["TEMP"] = @"C:\Temp" };

        InvokerLaunch.StartRequest request = InvokerLaunch.PrepareOutsideBaxy(
            CdpBrowserSession.LaunchPlan(Edge, Profile), environment);

        Assert.Multiple(() =>
        {
            Assert.That(
                request.CreationFlags & InvokerLaunch.CreateBreakawayFromJob,
                Is.EqualTo(InvokerLaunch.CreateBreakawayFromJob));
            Assert.That(request.InheritHandles, Is.False);
            Assert.That(request.WorkingDirectory, Is.EqualTo(@"C:\Program Files (x86)\Microsoft\Edge\Application"));
            Assert.That(request.EnvironmentBlock, Is.EqualTo("Path=C:\\Windows\0TEMP=C:\\Temp\0\0"),
                "the core's environment as it is: no compatibility layer for the browser");
            Assert.That(request.CommandLine, Does.StartWith("\"" + Edge + "\" --remote-debugging-port=0 "));
            Assert.That(request.CommandLine, Does.Contain(" --user-data-dir=" + Profile + " "));
            Assert.That(request.CommandLine, Does.EndWith(" about:blank"));
        });
    }

    [Test]
    public void AProfilePathWithSpacesStaysOneArgument()
    {
        InvokerLaunch.LaunchPlan plan = CdpBrowserSession.LaunchPlan(Edge, @"D:\Datos de BAXY\edge");

        Assert.That(plan.Arguments, Does.Contain("\"--user-data-dir=D:\\Datos de BAXY\\edge\""));
    }

    [Test]
    public void TheOwnerRecordNamesTheProcessAndItsStart()
    {
        string record = CdpBrowserSession.OwnerRecord(12524, 639_000_000_000_000_000);

        Assert.That(CdpBrowserSession.ParseOwnerRecord(record), Is.EqualTo((12524, 639_000_000_000_000_000L)));
    }

    // Counter-cases: a record that does not name one process and its start reattaches to nothing (a new browser starts).
    [TestCase(null)]
    [TestCase("")]
    [TestCase("12524")]
    [TestCase("0 639000000000000000")]
    [TestCase("-5 639000000000000000")]
    [TestCase("12524 abc")]
    [TestCase("12524 639000000000000000 7")]
    public void AnUnreadableOwnerRecordReattachesToNothing(string? record)
    {
        Assert.That(CdpBrowserSession.ParseOwnerRecord(record), Is.Null);
    }

    // Revisión de v3-57. A browser that outlives BAXY must not be drivable by any web page that finds its port: BAXY's
    // own client sends no Origin, so no origin is allowed. Counter-case: the debugging port itself is still opened.
    [Test]
    public void TheBrowserThatOutlivesBaxyAllowsNoWebOrigin()
    {
        InvokerLaunch.LaunchPlan plan = CdpBrowserSession.LaunchPlan(Edge, Profile);

        Assert.That(plan.Arguments, Does.Not.Contain("--remote-allow-origins"));
        Assert.That(plan.Arguments, Does.Contain("--remote-debugging-port=0"));
    }

    private const string PersonAndBaxyPages =
        """[{"id":"PERSON","type":"page","url":"https://example.org/form","webSocketDebuggerUrl":"ws://127.0.0.1:1/devtools/page/PERSON"},"""
        + """{"id":"BAXY","type":"page","url":"https://example.org/","webSocketDebuggerUrl":"ws://127.0.0.1:1/devtools/page/BAXY"}]""";

    [Test]
    public void AReattachedSessionNeverChoosesThePersonsTab()
    {
        using JsonDocument targets = JsonDocument.Parse(PersonAndBaxyPages);

        Assert.Multiple(() =>
        {
            Assert.That(CdpBrowserSession.ChoosePageTarget(targets.RootElement, new HashSet<string>()), Is.Null,
                "nothing of its own yet: a new tab is opened instead");
            Assert.That(CdpBrowserSession.ChoosePageTarget(
                    targets.RootElement, new HashSet<string> { "BAXY" })?.TargetId, Is.EqualTo("BAXY"));
        });
    }

    // Counter-case: a session that started the browser itself keeps acting on its first page, as before.
    [Test]
    public void ASessionThatStartedTheBrowserKeepsItsFirstPage()
    {
        using JsonDocument targets = JsonDocument.Parse(PersonAndBaxyPages);

        Assert.That(CdpBrowserSession.ChoosePageTarget(targets.RootElement, null)?.TargetId, Is.EqualTo("PERSON"));
    }

    // End to end against a fake CDP endpoint, with a hidden child process standing in for the browser left open: the
    // session reattaches to it, opens its own tab instead of taking the person's, keeps using that tab, and Dispose
    // leaves the process running.
    [Test]
    public async Task ReattachingOpensANewTabAndDisposeLeavesTheBrowserRunning()
    {
        using var server = new FakeCdpEndpoint();
        using var browser = BrowserStandIn.Start();
        string profile = NewProfile(server.Port, CdpBrowserSession.OwnerRecord(browser.Process.Id, browser.StartTicks));
        try
        {
            var session = new CdpBrowserSession(profile, BrowserStandIn.Executable);
            Uri? endpoint = await session.TryReattachAsync(
                Path.Combine(profile, "DevToolsActivePort"), BrowserStandIn.Executable, CancellationToken.None);
            Assert.That(endpoint, Is.EqualTo(new Uri($"http://127.0.0.1:{server.Port}/")));

            string first = (await session.ResolveTargetAsync(endpoint!, createIfMissing: true, CancellationToken.None)).TargetId;
            string again = (await session.ResolveTargetAsync(endpoint!, createIfMissing: true, CancellationToken.None)).TargetId;
            session.Dispose();

            Assert.Multiple(() =>
            {
                Assert.That(first, Is.EqualTo("BAXY-1"), "a new tab, never the person's");
                Assert.That(again, Is.EqualTo("BAXY-1"), "the tab this session opened is the one it keeps using");
                Assert.That(server.NewTabs, Is.EqualTo(1));
                Assert.That(browser.Process.HasExited, Is.False, "Dispose releases the connection only");
            });
        }
        finally
        {
            Directory.Delete(profile, recursive: true);
        }
    }

    // Counter-cases: a record that does not name the very process left open (another start, another executable, a
    // process that ended, an endpoint that does not answer, a missing record or port) reattaches to nothing.
    [TestCase("start")]
    [TestCase("executable")]
    [TestCase("exited")]
    [TestCase("silent")]
    [TestCase("no-record")]
    [TestCase("no-port")]
    public async Task ARecordThatDoesNotNameTheBrowserLeftOpenReattachesToNothing(string mismatch)
    {
        using var server = new FakeCdpEndpoint();
        using var browser = BrowserStandIn.Start();
        long ticks = mismatch == "start" ? browser.StartTicks + 1 : browser.StartTicks;
        string profile = NewProfile(server.Port, CdpBrowserSession.OwnerRecord(browser.Process.Id, ticks));
        try
        {
            string executable = mismatch == "executable"
                ? Path.Combine(Environment.SystemDirectory, "cmd.exe")
                : BrowserStandIn.Executable;
            if (mismatch == "exited")
            {
                browser.Process.Kill();
                await browser.Process.WaitForExitAsync();
            }
            if (mismatch == "silent")
                server.Dispose();
            if (mismatch == "no-record")
                File.Delete(Path.Combine(profile, CdpBrowserSession.OwnerRecordName));
            if (mismatch == "no-port")
                File.Delete(Path.Combine(profile, "DevToolsActivePort"));
            var session = new CdpBrowserSession(profile, executable);

            Uri? reattached = await session.TryReattachAsync(
                Path.Combine(profile, "DevToolsActivePort"), executable, CancellationToken.None);
            session.Dispose();

            Assert.That(reattached, Is.Null);
        }
        finally
        {
            Directory.Delete(profile, recursive: true);
        }
    }

    private static string NewProfile(int port, string ownerRecord)
    {
        string profile = Path.Combine(Path.GetTempPath(), "baxy-r15b2-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(profile);
        File.WriteAllText(Path.Combine(profile, "DevToolsActivePort"), port + "\n/devtools/browser/x\n");
        File.WriteAllText(Path.Combine(profile, CdpBrowserSession.OwnerRecordName), ownerRecord);
        return profile;
    }

    // A hidden, windowless process that just waits: the stand-in for the browser a previous session left open.
    private sealed class BrowserStandIn : IDisposable
    {
        private BrowserStandIn(Process process)
        {
            Process = process;
            StartTicks = process.StartTime.ToUniversalTime().Ticks;
        }

        internal Process Process { get; }

        internal long StartTicks { get; }

        internal static string Executable => Path.Combine(Environment.SystemDirectory, "PING.EXE");

        internal static BrowserStandIn Start()
        {
            var start = new ProcessStartInfo(Executable, "-n 120 127.0.0.1")
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
            };
            return new BrowserStandIn(Process.Start(start)!);
        }

        public void Dispose()
        {
            try
            {
                if (!Process.HasExited)
                    Process.Kill();
            }
            catch (InvalidOperationException)
            {
            }
            Process.Dispose();
        }
    }

    // The three endpoints a reattached session uses: /json/version, /json/list (the person's tab, then the ones
    // opened here) and PUT /json/new.
    private sealed class FakeCdpEndpoint : IDisposable
    {
        private readonly TcpListener _listener = new(IPAddress.Loopback, 0);
        private readonly CancellationTokenSource _stop = new();
        private readonly List<string> _opened = [];
        private int _disposed;

        internal FakeCdpEndpoint()
        {
            _listener.Start();
            Port = ((IPEndPoint)_listener.LocalEndpoint).Port;
            _ = Task.Run(ServeAsync);
        }

        internal int Port { get; }

        internal int NewTabs
        {
            get
            {
                lock (_opened)
                    return _opened.Count;
            }
        }

        private static string Page(string id) =>
            $$"""{"id":"{{id}}","type":"page","url":"about:blank","webSocketDebuggerUrl":"ws://127.0.0.1:1/devtools/page/{{id}}"}""";

        private async Task ServeAsync()
        {
            while (!_stop.IsCancellationRequested)
            {
                TcpClient client;
                try
                {
                    client = await _listener.AcceptTcpClientAsync(_stop.Token);
                }
                catch (Exception exception) when (exception is OperationCanceledException or SocketException
                    or ObjectDisposedException)
                {
                    return;
                }
                using (client)
                {
                    NetworkStream stream = client.GetStream();
                    var request = new StringBuilder();
                    var buffer = new byte[4096];
                    while (!request.ToString().Contains("\r\n\r\n", StringComparison.Ordinal))
                    {
                        int read = await stream.ReadAsync(buffer);
                        if (read == 0)
                            break;
                        request.Append(Encoding.ASCII.GetString(buffer, 0, read));
                    }
                    string line = request.ToString().Split("\r\n")[0];
                    string body;
                    if (line.StartsWith("GET /json/version", StringComparison.Ordinal))
                    {
                        body = """{"Browser":"stand-in"}""";
                    }
                    else if (line.StartsWith("GET /json/list", StringComparison.Ordinal))
                    {
                        lock (_opened)
                            body = "[" + string.Join(',', new[] { Page("PERSON") }.Concat(_opened.Select(Page))) + "]";
                    }
                    else if (line.StartsWith("PUT /json/new", StringComparison.Ordinal))
                    {
                        lock (_opened)
                        {
                            _opened.Add("BAXY-" + (_opened.Count + 1).ToString(System.Globalization.CultureInfo.InvariantCulture));
                            body = Page(_opened[^1]);
                        }
                    }
                    else
                    {
                        body = "{}";
                    }
                    byte[] payload = Encoding.UTF8.GetBytes(body);
                    byte[] head = Encoding.ASCII.GetBytes(
                        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                        + payload.Length.ToString(System.Globalization.CultureInfo.InvariantCulture)
                        + "\r\nConnection: close\r\n\r\n");
                    await stream.WriteAsync(head);
                    await stream.WriteAsync(payload);
                }
            }
        }

        public void Dispose()
        {
            if (Interlocked.Exchange(ref _disposed, 1) == 1)
                return;
            _stop.Cancel();
            _listener.Stop();
        }
    }
}
