using System.Net.NetworkInformation;

namespace Baxy.Providers.Windows.Network;

public sealed record NetworkStatusSnapshot(bool Online, int ConnectedInterfaceCount, IReadOnlyList<string> InterfaceTypes);

public interface INetworkStatusProvider
{
    ValueTask<NetworkStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken);
}

public sealed class WindowsNetworkStatusProvider : INetworkStatusProvider
{
    private readonly INetworkStatusProbe _probe;
    private readonly WindowsNetworkStatusVerifier _verifier;

    public WindowsNetworkStatusProvider() : this(new NetworkInformationStatusProbe()) { }

    internal WindowsNetworkStatusProvider(INetworkStatusProbe probe)
    {
        _probe = probe ?? throw new ArgumentNullException(nameof(probe));
        _verifier = new WindowsNetworkStatusVerifier(probe);
    }

    public ValueTask<NetworkStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        NetworkStatusSnapshot snapshot = _probe.Read();
        cancellationToken.ThrowIfCancellationRequested();
        return ValueTask.FromResult(_verifier.Verify(snapshot) ? snapshot : null);
    }
}

internal sealed class WindowsNetworkStatusVerifier(INetworkStatusProbe probe)
{
    public bool Verify(NetworkStatusSnapshot supplied)
    {
        NetworkStatusSnapshot observed = probe.Read();
        return supplied.Online == observed.Online
            && supplied.ConnectedInterfaceCount == observed.ConnectedInterfaceCount
            && supplied.InterfaceTypes.SequenceEqual(observed.InterfaceTypes, StringComparer.Ordinal)
            && supplied.Online == (supplied.ConnectedInterfaceCount > 0);
    }
}

internal interface INetworkStatusProbe { NetworkStatusSnapshot Read(); }

internal sealed class NetworkInformationStatusProbe : INetworkStatusProbe
{
    public NetworkStatusSnapshot Read()
    {
        string[] types = NetworkInterface.GetAllNetworkInterfaces()
            .Where(static item => item.OperationalStatus == OperationalStatus.Up
                && item.NetworkInterfaceType is not NetworkInterfaceType.Loopback
                && item.NetworkInterfaceType is not NetworkInterfaceType.Tunnel)
            .Select(static item => item.NetworkInterfaceType.ToString().ToLowerInvariant())
            .Order(StringComparer.Ordinal)
            .ToArray();
        return new NetworkStatusSnapshot(types.Length > 0, types.Length, types);
    }
}
