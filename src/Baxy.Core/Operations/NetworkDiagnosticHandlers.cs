using System.Buffers;
using System.Net;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Network;

namespace Baxy.Core.Operations;

internal sealed class DnsStatusHandler(INetworkDiagnosticProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("network.dns.status");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        DnsStatusSnapshot? snapshot = await provider.ReadDnsStatusVerifiedAsync(
            cancellationToken).ConfigureAwait(false);
        if (snapshot is null)
        {
            return OperationOutcome.Failure(NetworkStableRead.ChangedDuringRead);
        }

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("activeInterfaceCount", snapshot.ActiveInterfaceCount);
            writer.WritePropertyName("serverAddresses");
            writer.WriteStartArray();
            foreach (string address in snapshot.ServerAddresses)
            {
                writer.WriteStringValue(address);
            }
            writer.WriteEndArray();
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}

internal sealed class NetworkPingHandler(INetworkDiagnosticProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("network.ping");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        if (!TryReadHost(invocation.Arguments, out string? host))
        {
            // P5.3: a URL or a name with spaces is no host to ping.
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments,
                new ArgumentProblem("host", "expected a host name or an IP address, not a URL"));
        }

        NetworkPingSnapshot snapshot = await provider.PingAsync(
            host!, cancellationToken).ConfigureAwait(false);
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("host", snapshot.Host);
            writer.WriteBoolean("reachable", snapshot.Reachable);
            writer.WriteString("status", snapshot.Status);
            if (snapshot.RoundtripMilliseconds is long roundtrip)
            {
                writer.WriteNumber("roundtripMilliseconds", roundtrip);
            }
            else
            {
                writer.WriteNull("roundtripMilliseconds");
            }
            if (snapshot.Address is string address)
            {
                writer.WriteString("address", address);
            }
            else
            {
                writer.WriteNull("address");
            }
            // Renew al máximo (w5): one echo with no reply was told as the host (or the internet) being down; many hosts
            // and firewalls never answer ping, and whether this PC has internet is network_status's to say.
            if (!snapshot.Reachable && ModelAids.On(ModelAids.PingScope))
                writer.WriteString("next", PingNext(snapshot));
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }

    internal static string PingNext(NetworkPingSnapshot snapshot) => snapshot.Status == "name_resolution_failed"
        ? $"the name {snapshot.Host} was not resolved to an address, so nothing was sent; network_status says whether this PC has internet"
        : $"{snapshot.Host} sent no reply to one echo within 2 s ({snapshot.Status}); many hosts and firewalls never answer ping, "
            + $"so this alone does not say {snapshot.Host} or the internet is down; network_status says whether this PC has internet";

    private static bool TryReadHost(JsonElement arguments, out string? host)
    {
        host = null;
        if (arguments.ValueKind != JsonValueKind.Object
            || !arguments.TryGetProperty("host", out JsonElement hostElement)
            || hostElement.ValueKind != JsonValueKind.String)
        {
            return false;
        }

        host = hostElement.GetString()?.Trim();
        return host is { Length: > 0 and <= 253 }
            && (IPAddress.TryParse(host, out _)
                || Uri.CheckHostName(host) == UriHostNameType.Dns);
    }
}
