using System.Net;
using System.Net.NetworkInformation;

namespace Baxy.Providers.Windows.Network;

public sealed record NetworkPortEndpoint(string Protocol, string Address, int Port);

public sealed record NetworkPortSnapshot(
    IReadOnlyList<NetworkPortEndpoint> Endpoints,
    int FirstObservationCount,
    int SecondObservationCount);

public interface INetworkPortProvider
{
    ValueTask<NetworkPortSnapshot> ReadVerifiedAsync(
        int limit,
        CancellationToken cancellationToken);
}

public sealed class WindowsNetworkPortProvider : INetworkPortProvider
{
    private readonly INetworkPortProbe _probe;

    public WindowsNetworkPortProvider() : this(new NetworkInformationPortProbe()) { }

    internal WindowsNetworkPortProvider(INetworkPortProbe probe) =>
        _probe = probe ?? throw new ArgumentNullException(nameof(probe));

    public ValueTask<NetworkPortSnapshot> ReadVerifiedAsync(
        int limit,
        CancellationToken cancellationToken)
    {
        if (limit is < 1 or > 100) throw new ArgumentOutOfRangeException(nameof(limit));
        cancellationToken.ThrowIfCancellationRequested();
        IReadOnlyList<NetworkPortEndpoint> first = _probe.Read();
        cancellationToken.ThrowIfCancellationRequested();
        IReadOnlyList<NetworkPortEndpoint> second = _probe.Read();
        var firstSet = first.ToHashSet();
        NetworkPortEndpoint[] stable = second
            .Where(firstSet.Contains)
            .Distinct()
            .OrderBy(endpoint => endpoint.Port)
            .ThenBy(endpoint => endpoint.Protocol, StringComparer.Ordinal)
            .ThenBy(endpoint => endpoint.Address, StringComparer.Ordinal)
            .Take(limit)
            .ToArray();
        return ValueTask.FromResult(new NetworkPortSnapshot(
            stable, first.Count, second.Count));
    }
}

internal interface INetworkPortProbe
{
    IReadOnlyList<NetworkPortEndpoint> Read();
}

internal sealed class NetworkInformationPortProbe : INetworkPortProbe
{
    public IReadOnlyList<NetworkPortEndpoint> Read()
    {
        IPGlobalProperties properties = IPGlobalProperties.GetIPGlobalProperties();
        return properties.GetActiveTcpListeners()
            .Select(endpoint => ToEndpoint("tcp", endpoint))
            .Concat(properties.GetActiveUdpListeners().Select(endpoint => ToEndpoint("udp", endpoint)))
            .Distinct()
            .OrderBy(endpoint => endpoint.Port)
            .ThenBy(endpoint => endpoint.Protocol, StringComparer.Ordinal)
            .ThenBy(endpoint => endpoint.Address, StringComparer.Ordinal)
            .ToArray();
    }

    private static NetworkPortEndpoint ToEndpoint(string protocol, IPEndPoint endpoint) =>
        new(protocol, endpoint.Address.ToString(), endpoint.Port);
}
