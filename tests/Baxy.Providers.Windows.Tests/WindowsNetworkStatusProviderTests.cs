using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Network;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsNetworkStatusProviderTests
{
    [Test]
    public async Task ReadReturnsOnlyASecondReadVerifiedPrivacySafeProjection()
    {
        var probe = new FakeProbe(
            new NetworkStatusSnapshot(true, 2, ["ethernet", "wireless80211"], "internet"),
            new NetworkStatusSnapshot(true, 2, ["ethernet", "wireless80211"], "internet"));
        var provider = new WindowsNetworkStatusProvider(probe);
        NetworkStatusSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Not.Null);
            Assert.That(result!.ConnectedInterfaceCount, Is.EqualTo(2));
            Assert.That(result.InterfaceTypes, Is.EqualTo(new[] { "ethernet", "wireless80211" }));
            Assert.That(probe.Reads, Is.EqualTo(2));
        });
    }

    // Renew al máximo (w5): a network that changes on every read (six reads, 100 ms apart after the first pair) is no
    // answer; one that changed once and then held is answered with the two reads that agree.
    [Test]
    public async Task ANetworkStillChangingAfterEveryReadIsNoAnswer()
    {
        var up = new NetworkStatusSnapshot(true, 1, ["ethernet"], "internet");
        var down = new NetworkStatusSnapshot(false, 0, [], "none");
        var probe = new FakeProbe(up, down, up, down, up, down, up);
        var pauses = new List<TimeSpan>();
        var provider = new WindowsNetworkStatusProvider(probe, Pauses(pauses));

        NetworkStatusSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Null);
            Assert.That(probe.Reads, Is.EqualTo(6));
            Assert.That(pauses, Is.EqualTo(Enumerable.Repeat(TimeSpan.FromMilliseconds(100), 4)));
        });
    }

    [Test]
    public async Task ANetworkThatSettlesIsReadAgainAndAnswered()
    {
        var joining = new NetworkStatusSnapshot(false, 1, ["wireless80211"], "local");
        var joined = new NetworkStatusSnapshot(true, 1, ["wireless80211"], "internet");
        var probe = new FakeProbe(joining, joined, joined);
        var pauses = new List<TimeSpan>();
        var provider = new WindowsNetworkStatusProvider(probe, Pauses(pauses));

        NetworkStatusSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.EqualTo(joined));
            Assert.That(probe.Reads, Is.EqualTo(3));
            Assert.That(pauses, Has.Count.EqualTo(1));
        });
    }

    // An adapter that is up is not internet: online is what Windows' own connectivity check says.
    [Test]
    public async Task AnInterfaceUpWithoutInternetIsNotOnline()
    {
        var probe = new FakeProbe(
            new NetworkStatusSnapshot(false, 1, ["ethernet"], "local"),
            new NetworkStatusSnapshot(false, 1, ["ethernet"], "local"));
        var provider = new WindowsNetworkStatusProvider(probe);

        NetworkStatusSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Not.Null);
            Assert.That(result!.Online, Is.False);
            Assert.That(result.Connectivity, Is.EqualTo("local"));
        });
    }

    [Test]
    public async Task IpListReturnsOnlyAStableSortedUnicastProjection()
    {
        var probe = new FakeIpProbe(
            ["192.168.1.89", "100.64.10.27"],
            ["100.64.10.27", "192.168.1.89"]);
        var provider = new WindowsNetworkIpProvider(probe);

        NetworkIpSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Not.Null);
            Assert.That(result!.Addresses,
                Is.EqualTo(new[] { "100.64.10.27", "192.168.1.89" }));
            Assert.That(probe.Reads, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task IpListFailsClosedWhileEveryObservationChanges()
    {
        var probe = new FakeIpProbe(
            ["192.168.1.89"], ["192.168.1.90"], ["192.168.1.91"], ["192.168.1.92"], ["192.168.1.93"], ["192.168.1.94"],
            ["192.168.1.94"]);
        var provider = new WindowsNetworkIpProvider(probe, Pauses([]));

        NetworkIpSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Null);
            Assert.That(probe.Reads, Is.EqualTo(6));
        });
    }

    // Renew al máximo (w5): an address renewed between the first two reads is read again and answered once it holds.
    [Test]
    public async Task IpListAnswersAnAddressRenewedOnceItHolds()
    {
        var probe = new FakeIpProbe(["192.168.1.89"], ["192.168.1.90"]);
        var provider = new WindowsNetworkIpProvider(probe, Pauses([]));

        NetworkIpSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result?.Addresses, Is.EqualTo(new[] { "192.168.1.90" }));
            Assert.That(probe.Reads, Is.EqualTo(3));
        });
    }

    [Test]
    [Explicit("Physical read-only validation against the current Windows network interfaces.")]
    public async Task ActualIpListReturnsStableParseableAddressesWithoutInterfaceNames()
    {
        var provider = new WindowsNetworkIpProvider();

        NetworkIpSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Not.Null);
            Assert.That(result!.Addresses, Is.Not.Empty);
            Assert.That(result.Addresses.All(address =>
                System.Net.IPAddress.TryParse(address, out _)), Is.True);
        });
    }

    [Test]
    public async Task DnsStatusRequiresTwoIdenticalInterfaceSnapshots()
    {
        var dns = new FakeDnsProbe(
            new DnsStatusSnapshot(2, ["1.1.1.1", "8.8.8.8"]),
            new DnsStatusSnapshot(2, ["1.1.1.1", "8.8.8.8"]));
        var ping = new FakePingProbe(new NetworkPingSnapshot(
            "example.com", true, "success", 12, "203.0.113.10"));
        var provider = new WindowsNetworkDiagnosticProvider(dns, ping);

        DnsStatusSnapshot? result = await provider.ReadDnsStatusVerifiedAsync(
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Not.Null);
            Assert.That(result!.ServerAddresses, Is.EqualTo(new[] { "1.1.1.1", "8.8.8.8" }));
            Assert.That(dns.Reads, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task DnsStatusRejectsObservationsThatKeepChanging()
    {
        var a = new DnsStatusSnapshot(1, ["1.1.1.1"]);
        var b = new DnsStatusSnapshot(1, ["8.8.8.8"]);
        var dns = new FakeDnsProbe(a, b, a, b, a, b, b);
        var provider = new WindowsNetworkDiagnosticProvider(
            dns,
            new FakePingProbe(new NetworkPingSnapshot(
                "unused", false, "unused", null, null)),
            Pauses([]));

        DnsStatusSnapshot? result = await provider.ReadDnsStatusVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Null);
            Assert.That(dns.Reads, Is.EqualTo(6));
        });
    }

    // Renew al máximo (w5): servers that changed once (a VPN coming up) are answered once two reads agree.
    [Test]
    public async Task DnsStatusAnswersServersThatChangedOnceAndHeld()
    {
        var dns = new FakeDnsProbe(new DnsStatusSnapshot(1, ["1.1.1.1"]), new DnsStatusSnapshot(2, ["10.0.0.1", "1.1.1.1"]));
        var provider = new WindowsNetworkDiagnosticProvider(
            dns, new FakePingProbe(new NetworkPingSnapshot("unused", false, "unused", null, null)), Pauses([]));

        DnsStatusSnapshot? result = await provider.ReadDnsStatusVerifiedAsync(CancellationToken.None);

        Assert.That(result?.ServerAddresses, Is.EqualTo(new[] { "10.0.0.1", "1.1.1.1" }));
    }

    [Test]
    public async Task PingReturnsTheProbeReceiptWithoutInventingReachability()
    {
        var expected = new NetworkPingSnapshot(
            "nodo", false, "name_resolution_failed", null, null);
        var ping = new FakePingProbe(expected);
        var provider = new WindowsNetworkDiagnosticProvider(
            new FakeDnsProbe(new DnsStatusSnapshot(0, [])),
            ping);

        NetworkPingSnapshot result = await provider.PingAsync(
            "nodo", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.EqualTo(expected));
            Assert.That(ping.Host, Is.EqualTo("nodo"));
        });
    }

    // Renew al máximo (w5): one echo with no reply was answered «google no responde, está caído»; with the aid ping_scope
    // the result says what it does not tell and where internet is read; a reply needs no word; BAXY_AYUDAS=none, facts.
    // Encargo 34: the call that says it comes first, written as the model calls it.
    [TestCase("all", "timedout", "network_status {} says whether this PC has internet; example.com sent no reply to one "
        + "echo within 2 s (timedout); many hosts and firewalls never answer ping, so this alone does not say example.com "
        + "or the internet is down")]
    [TestCase("all", "name_resolution_failed", "network_status {} says whether this PC has internet; the name "
        + "example.com was not resolved to an address, so nothing was sent")]
    [TestCase("all", "success", null)]
    [TestCase("none", "timedout", null)]
    public async Task APingWithNoReplySaysWhatItDoesNotTell(string aids, string status, string? next)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        bool reachable = status == "success";
        var handler = new NetworkPingHandler(new WindowsNetworkDiagnosticProvider(
            new FakeDnsProbe(new DnsStatusSnapshot(0, [])),
            new FakePingProbe(new NetworkPingSnapshot("example.com", reachable, status, reachable ? 12 : null, null))));

        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation",
                JsonDocument.Parse("""{"host":"example.com"}""").RootElement.Clone()),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("reachable").GetBoolean(), Is.EqualTo(reachable));
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out JsonElement written) ? written.GetString() : null,
                Is.EqualTo(next));
        });
    }

    [Test]
    public async Task PortInventoryReturnsOnlyEndpointsPresentInBothObservations()
    {
        var stable = new NetworkPortEndpoint("tcp", "127.0.0.1", 8080);
        var transient = new NetworkPortEndpoint("udp", "0.0.0.0", 53000);
        var probe = new FakePortProbe([stable, transient], [stable]);
        var provider = new WindowsNetworkPortProvider(probe);

        NetworkPortSnapshot result = await provider.ReadVerifiedAsync(
            50, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Endpoints, Is.EqualTo(new[] { stable }));
            Assert.That(result.FirstObservationCount, Is.EqualTo(2));
            Assert.That(result.SecondObservationCount, Is.EqualTo(1));
            Assert.That(probe.Reads, Is.EqualTo(2));
        });
    }

    // The pauses taken between reads, none waited for.
    private static Func<TimeSpan, CancellationToken, Task> Pauses(List<TimeSpan> taken) => (pause, _) =>
    {
        taken.Add(pause);
        return Task.CompletedTask;
    };

    private sealed class FakeProbe(params NetworkStatusSnapshot[] snapshots) : INetworkStatusProbe
    {
        private readonly Queue<NetworkStatusSnapshot> _snapshots = new(snapshots);
        public int Reads { get; private set; }
        public NetworkStatusSnapshot Read() { Reads++; return _snapshots.Count > 1 ? _snapshots.Dequeue() : _snapshots.Peek(); }
    }

    private sealed class FakeIpProbe(params IReadOnlyList<string>[] snapshots) : INetworkIpProbe
    {
        private readonly Queue<IReadOnlyList<string>> _snapshots = new(snapshots);
        public int Reads { get; private set; }

        public IReadOnlyList<string> Read()
        {
            Reads++;
            return _snapshots.Count > 1 ? _snapshots.Dequeue() : _snapshots.Peek();
        }
    }

    private sealed class FakeDnsProbe(params DnsStatusSnapshot[] snapshots) : IDnsStatusProbe
    {
        private readonly Queue<DnsStatusSnapshot> _snapshots = new(snapshots);
        public int Reads { get; private set; }
        public DnsStatusSnapshot Read()
        {
            Reads++;
            return _snapshots.Count > 1 ? _snapshots.Dequeue() : _snapshots.Peek();
        }
    }

    private sealed class FakePingProbe(NetworkPingSnapshot snapshot) : INetworkPingProbe
    {
        public string? Host { get; private set; }

        public ValueTask<NetworkPingSnapshot> SendAsync(
            string host,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Host = host;
            return ValueTask.FromResult(snapshot);
        }
    }

    private sealed class FakePortProbe(
        params IReadOnlyList<NetworkPortEndpoint>[] snapshots) : INetworkPortProbe
    {
        private readonly Queue<IReadOnlyList<NetworkPortEndpoint>> _snapshots =
            new(snapshots);
        public int Reads { get; private set; }
        public IReadOnlyList<NetworkPortEndpoint> Read()
        {
            Reads++;
            return _snapshots.Dequeue();
        }
    }
}
