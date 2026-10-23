using System.Net.NetworkInformation;
using Windows.Networking.Connectivity;

namespace Baxy.Providers.Windows.Network;

/// <summary>
/// «Online» is Windows' own check of internet access on the profile it uses for the internet (connectivity
/// «internet»; «constrained» is a portal or limited access, «local» a network without internet, «none» no network).
/// BAXY Renew audit 2026-10-15: it was «some interface other than loopback is up», which a virtual or VPN adapter
/// is without any internet, and «¿tengo internet?» was answered by it.
/// </summary>
public sealed record NetworkStatusSnapshot(
    bool Online, int ConnectedInterfaceCount, IReadOnlyList<string> InterfaceTypes, string Connectivity);

public interface INetworkStatusProvider
{
    ValueTask<NetworkStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken);
}

public sealed class WindowsNetworkStatusProvider : INetworkStatusProvider
{
    private readonly INetworkStatusProbe _probe;
    private readonly Func<TimeSpan, CancellationToken, Task> _delay;

    public WindowsNetworkStatusProvider() : this(new NetworkInformationStatusProbe()) { }

    internal WindowsNetworkStatusProvider(
        INetworkStatusProbe probe, Func<TimeSpan, CancellationToken, Task>? delay = null)
    {
        _probe = probe ?? throw new ArgumentNullException(nameof(probe));
        _delay = delay ?? NetworkStableRead.Delay;
    }

    // Renew al máximo (w5): two reads in a row that agree, a change read again (NetworkStableRead).
    public ValueTask<NetworkStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken) =>
        NetworkStableRead.ReadAsync(_probe.Read, WindowsNetworkStatusVerifier.Same, _delay, cancellationToken);
}

internal static class WindowsNetworkStatusVerifier
{
    public static bool Same(NetworkStatusSnapshot supplied, NetworkStatusSnapshot observed)
    {
        return supplied.Online == observed.Online
            && string.Equals(supplied.Connectivity, observed.Connectivity, StringComparison.Ordinal)
            && supplied.ConnectedInterfaceCount == observed.ConnectedInterfaceCount
            && supplied.InterfaceTypes.SequenceEqual(observed.InterfaceTypes, StringComparer.Ordinal)
            && supplied.Online == (supplied.Connectivity == "internet");
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
        string connectivity = NetworkInformation.GetInternetConnectionProfile()?.GetNetworkConnectivityLevel() switch
        {
            NetworkConnectivityLevel.InternetAccess => "internet",
            NetworkConnectivityLevel.ConstrainedInternetAccess => "constrained",
            NetworkConnectivityLevel.LocalAccess => "local",
            _ => "none",
        };
        return new NetworkStatusSnapshot(connectivity == "internet", types.Length, types, connectivity);
    }
}
