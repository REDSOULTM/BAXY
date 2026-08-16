using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace Baxy.Providers.Windows.Network;

public sealed record DnsStatusSnapshot(
    int ActiveInterfaceCount,
    IReadOnlyList<string> ServerAddresses);

public sealed record NetworkPingSnapshot(
    string Host,
    bool Reachable,
    string Status,
    long? RoundtripMilliseconds,
    string? Address);

public interface INetworkDiagnosticProvider
{
    ValueTask<DnsStatusSnapshot?> ReadDnsStatusVerifiedAsync(
        CancellationToken cancellationToken);

    ValueTask<NetworkPingSnapshot> PingAsync(
        string host,
        CancellationToken cancellationToken);
}

public sealed class WindowsNetworkDiagnosticProvider : INetworkDiagnosticProvider
{
    private readonly IDnsStatusProbe _dnsProbe;
    private readonly INetworkPingProbe _pingProbe;

    public WindowsNetworkDiagnosticProvider()
        : this(new NetworkInterfaceDnsStatusProbe(), new IcmpNetworkPingProbe())
    {
    }

    internal WindowsNetworkDiagnosticProvider(
        IDnsStatusProbe dnsProbe,
        INetworkPingProbe pingProbe)
    {
        _dnsProbe = dnsProbe ?? throw new ArgumentNullException(nameof(dnsProbe));
        _pingProbe = pingProbe ?? throw new ArgumentNullException(nameof(pingProbe));
    }

    public ValueTask<DnsStatusSnapshot?> ReadDnsStatusVerifiedAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        DnsStatusSnapshot first = _dnsProbe.Read();
        cancellationToken.ThrowIfCancellationRequested();
        DnsStatusSnapshot second = _dnsProbe.Read();
        bool verified = first.ActiveInterfaceCount == second.ActiveInterfaceCount
            && first.ServerAddresses.SequenceEqual(
                second.ServerAddresses,
                StringComparer.Ordinal);
        return ValueTask.FromResult<DnsStatusSnapshot?>(verified ? second : null);
    }

    public ValueTask<NetworkPingSnapshot> PingAsync(
        string host,
        CancellationToken cancellationToken) =>
        _pingProbe.SendAsync(host, cancellationToken);
}

internal interface IDnsStatusProbe
{
    DnsStatusSnapshot Read();
}

internal interface INetworkPingProbe
{
    ValueTask<NetworkPingSnapshot> SendAsync(
        string host,
        CancellationToken cancellationToken);
}

internal sealed class NetworkInterfaceDnsStatusProbe : IDnsStatusProbe
{
    public DnsStatusSnapshot Read()
    {
        NetworkInterface[] active = NetworkInterface.GetAllNetworkInterfaces()
            .Where(static item => item.OperationalStatus == OperationalStatus.Up
                && item.NetworkInterfaceType is not NetworkInterfaceType.Loopback
                && item.NetworkInterfaceType is not NetworkInterfaceType.Tunnel)
            .ToArray();
        string[] servers = active
            .SelectMany(static item => item.GetIPProperties().DnsAddresses)
            .Select(static address => address.ToString())
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        return new DnsStatusSnapshot(active.Length, servers);
    }
}

internal sealed class IcmpNetworkPingProbe : INetworkPingProbe
{
    private const int TimeoutMilliseconds = 2_000;

    public async ValueTask<NetworkPingSnapshot> SendAsync(
        string host,
        CancellationToken cancellationToken)
    {
        using var ping = new Ping();
        try
        {
            PingReply reply = await ping.SendPingAsync(
                host,
                TimeoutMilliseconds).WaitAsync(cancellationToken).ConfigureAwait(false);
            bool reachable = reply.Status == IPStatus.Success;
            return new NetworkPingSnapshot(
                host,
                reachable,
                reply.Status.ToString().ToLowerInvariant(),
                reachable ? reply.RoundtripTime : null,
                reply.Address?.ToString());
        }
        catch (PingException exception) when (
            exception.InnerException is SocketException or ArgumentException)
        {
            return new NetworkPingSnapshot(
                host,
                false,
                "name_resolution_failed",
                null,
                null);
        }
    }
}
