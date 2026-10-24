using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace Baxy.Providers.Windows.Network;

public sealed record NetworkIpSnapshot(IReadOnlyList<string> Addresses);

public interface INetworkIpProvider
{
    ValueTask<NetworkIpSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken);
}

internal interface INetworkIpProbe
{
    IReadOnlyList<string> Read();
}

public sealed class WindowsNetworkIpProvider : INetworkIpProvider
{
    private readonly INetworkIpProbe _probe;
    private readonly Func<TimeSpan, CancellationToken, Task> _delay;

    public WindowsNetworkIpProvider() : this(new NetworkInformationIpProbe()) { }

    internal WindowsNetworkIpProvider(INetworkIpProbe probe, Func<TimeSpan, CancellationToken, Task>? delay = null)
    {
        _probe = probe ?? throw new ArgumentNullException(nameof(probe));
        _delay = delay ?? NetworkStableRead.Delay;
    }

    // Renew al máximo (w5): two reads in a row that agree, a change read again (NetworkStableRead).
    public async ValueTask<NetworkIpSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken)
    {
        string[]? stable = await NetworkStableRead.ReadAsync(
            () => Normalize(_probe.Read()),
            static (first, second) => first.SequenceEqual(second, StringComparer.Ordinal),
            _delay,
            cancellationToken).ConfigureAwait(false);
        return stable is null ? null : new NetworkIpSnapshot(stable);
    }

    private static string[] Normalize(IEnumerable<string> addresses) => addresses
        .Distinct(StringComparer.Ordinal)
        .Order(StringComparer.Ordinal)
        .ToArray();
}

internal sealed class NetworkInformationIpProbe : INetworkIpProbe
{
    public IReadOnlyList<string> Read() => NetworkInterface.GetAllNetworkInterfaces()
        .Where(static item => item.OperationalStatus == OperationalStatus.Up)
        .SelectMany(static item => item.GetIPProperties().UnicastAddresses)
        .Select(static item => item.Address)
        .Where(IsUsable)
        .Select(static address => address.ToString())
        .Distinct(StringComparer.Ordinal)
        .Order(StringComparer.Ordinal)
        .ToArray();

    private static bool IsUsable(IPAddress address)
    {
        if (IPAddress.IsLoopback(address)
            || address.Equals(IPAddress.Any)
            || address.Equals(IPAddress.IPv6Any)
            || address.Equals(IPAddress.None)
            || address.Equals(IPAddress.IPv6None)
            || address.IsIPv6Multicast
            || address.IsIPv6LinkLocal)
        {
            return false;
        }
        if (address.AddressFamily == AddressFamily.InterNetwork)
        {
            byte[] bytes = address.GetAddressBytes();
            if (bytes[0] == 169 && bytes[1] == 254) return false;
        }
        return address.AddressFamily is AddressFamily.InterNetwork or AddressFamily.InterNetworkV6;
    }
}
