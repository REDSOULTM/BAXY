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

    [Test]
    public async Task ChangedSecondReadFailsVerification()
    {
        var probe = new FakeProbe(
            new NetworkStatusSnapshot(true, 1, ["ethernet"], "internet"),
            new NetworkStatusSnapshot(false, 0, [], "none"));
        var provider = new WindowsNetworkStatusProvider(probe);
        Assert.That(await provider.ReadVerifiedAsync(CancellationToken.None), Is.Null);
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
            ["192.168.1.89", "100.64.0.12"],
            ["100.64.0.12", "192.168.1.89"]);
        var provider = new WindowsNetworkIpProvider(probe);

        NetworkIpSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Not.Null);
            Assert.That(result!.Addresses,
                Is.EqualTo(new[] { "100.64.0.12", "192.168.1.89" }));
            Assert.That(probe.Reads, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task IpListFailsClosedWhenTheSecondObservationChanges()
    {
        var probe = new FakeIpProbe(["192.168.1.89"], ["192.168.1.90"]);
        var provider = new WindowsNetworkIpProvider(probe);

        Assert.That(await provider.ReadVerifiedAsync(CancellationToken.None), Is.Null);
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
    public async Task DnsStatusRejectsAChangedSecondObservation()
    {
        var dns = new FakeDnsProbe(
            new DnsStatusSnapshot(1, ["1.1.1.1"]),
            new DnsStatusSnapshot(1, ["8.8.8.8"]));
        var provider = new WindowsNetworkDiagnosticProvider(
            dns,
            new FakePingProbe(new NetworkPingSnapshot(
                "unused", false, "unused", null, null)));

        Assert.That(
            await provider.ReadDnsStatusVerifiedAsync(CancellationToken.None),
            Is.Null);
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

    private sealed class FakeProbe(params NetworkStatusSnapshot[] snapshots) : INetworkStatusProbe
    {
        private readonly Queue<NetworkStatusSnapshot> _snapshots = new(snapshots);
        public int Reads { get; private set; }
        public NetworkStatusSnapshot Read() { Reads++; return _snapshots.Dequeue(); }
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
