using System.Globalization;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Installer;

internal enum GpuSupport
{
    Measured,
    NotMeasured,
    TooLittleMemory,
    None,
    // VRAM5 (AUD1 F7): a card BAXY runs on, or Intel graphics, on a PC with less RAM installed than the least measured.
    TooLittleRam,
    TooLittleRamIntegrated,
}

internal sealed record GpuAdapter(string DeviceId, long? MemoryBytes);

/// <summary>
/// What the person is told before downloading gigabytes, by PCI vendor id, the way BAXY itself picks its server at every
/// start (MindRuntimeDiscovery). BAXY has been measured on NVIDIA and AMD; Intel graphics have not been; with none of the
/// three it does not start (no_supported_gpu).
/// </summary>
internal static class MachineGpu
{
    private const long MinimumMemoryBytes = 3_800_000_000;

    // VRAM5 (AUD1 F7): the RAM a PC needs installed, MiB, the same figures the mind starts an integrated GPU by
    // (llm_server.integrated_room): Windows 11's own minimum, «RAM: 4 gigabyte (GB) or greater» (Microsoft, Windows 11
    // specifications, https://www.microsoft.com/windows/windows-11-specifications, read 2026-11-13); all of BAXY but the
    // server's GPU memory, 3,748 MiB with its window and the voice loaded (measured on the PC, 2026-11-05, INFORME_AUD1
    // §2); and on integrated graphics, whose memory is that RAM, the server in its fewest cells on Vulkan with the mind's
    // margin, 3,379 + 200 MiB (llm_server.card_mib: AMD3 §3, an RX 7600, 2026-11-09).
    internal const long WindowsRamMib = 4096;
    internal const long BaxyRamMib = 3748;
    internal const long IntegratedServerMib = 3379 + 200;

    internal static long MinimumRamMib(bool integrated) => WindowsRamMib + BaxyRamMib + (integrated ? IntegratedServerMib : 0);

    /// <summary>VRAM5 (AUD1 F7): what is told of <paramref name="adapters"/> once the RAM installed is known
    /// (<paramref name="installedRamMib"/>, MachineRam; null when unread: as before): a card BAXY runs on, or Intel graphics
    /// only, on a PC with less than <see cref="MinimumRamMib"/>. Intel graphics with less dedicated memory than a card BAXY
    /// takes are integrated, and hold the model in that RAM; an Intel card with its own memory (an Arc) is not. Any other
    /// answer stays.</summary>
    internal static GpuSupport WithRam(IReadOnlyList<GpuAdapter> adapters, long? installedRamMib)
    {
        GpuSupport support = Choose(adapters);
        bool integrated = support == GpuSupport.NotMeasured
            && adapters.Where(static adapter => Vendor(adapter.DeviceId) == Intel).All(static adapter => !(adapter.MemoryBytes >= MinimumMemoryBytes));
        return support is GpuSupport.Measured or GpuSupport.NotMeasured && installedRamMib is { } ram && ram < MinimumRamMib(integrated)
            ? (integrated ? GpuSupport.TooLittleRamIntegrated : GpuSupport.TooLittleRam)
            : support;
    }
    private const string Nvidia = "10de";
    private const string Amd = "1002";
    private const string Intel = "8086";

    internal static GpuSupport Choose(IReadOnlyList<GpuAdapter> adapters)
    {
        GpuAdapter? nvidia = adapters.FirstOrDefault(adapter => Vendor(adapter.DeviceId) == Nvidia);
        GpuAdapter? amd = adapters.FirstOrDefault(adapter => Vendor(adapter.DeviceId) == Amd);
        if (nvidia is not null)
        {
            return Sized(nvidia);
        }

        if (amd is not null)
        {
            return Sized(amd);
        }

        return adapters.Any(adapter => Vendor(adapter.DeviceId) == Intel) ? GpuSupport.NotMeasured : GpuSupport.None;
    }

    /// <summary>
    /// The cards as BAXY reads them at every start (WindowsGpuVendors, DXGI), the same source compiled in here. Not the
    /// screens of this session (EnumDisplayDevices): a card with no screen plugged, as the NVIDIA one of a laptop whose
    /// panel hangs from the integrated graphics, is not among them, and its part was not downloaded (INS-2).
    /// </summary>
    internal static IReadOnlyList<GpuAdapter> Installed() => Installed(new WindowsGpuStatusProbe());

    internal static IReadOnlyList<GpuAdapter> Installed(IGpuStatusProbe probe) =>
        [.. WindowsGpuVendors.Adapters(probe).Select(static adapter => new GpuAdapter(
            HardwareId(adapter.VendorId, adapter.DeviceId),
            (long)Math.Min(adapter.DedicatedVideoMemoryBytes, long.MaxValue)))];

    /// <summary>What the log says of this machine: what is told, and every card with its dedicated memory.</summary>
    internal static string Describe(IReadOnlyList<GpuAdapter> adapters) =>
        string.Create(
            CultureInfo.InvariantCulture,
            $"{Choose(adapters)} [{string.Join(", ", adapters.Select(static adapter => string.Create(CultureInfo.InvariantCulture, $"{adapter.DeviceId} {(adapter.MemoryBytes ?? 0) / 1_000_000_000d:0.0} GB")))}]");

    // DXGI_ADAPTER_DESC1.VendorId: «If this value is less than or equal to 0xFFFF, it is a PCI ID; otherwise, it is an
    // ACPI ID». An ACPI one is written as such, so that Vendor() never takes four of its digits for a maker.
    private static string HardwareId(uint vendor, uint device) =>
        vendor <= 0xFFFF
            ? string.Create(CultureInfo.InvariantCulture, $@"PCI\VEN_{vendor:X4}&DEV_{device:X4}")
            : string.Create(CultureInfo.InvariantCulture, $@"ACPI\VEN_{vendor:X8}&DEV_{device:X8}");

    private static GpuSupport Sized(GpuAdapter adapter) =>
        adapter.MemoryBytes < MinimumMemoryBytes ? GpuSupport.TooLittleMemory : GpuSupport.Measured;

    internal static string? Vendor(string deviceId)
    {
        const string prefix = "pci\\ven_";
        string id = deviceId.Trim().ToLowerInvariant();
        return id.StartsWith(prefix, StringComparison.Ordinal) && id.Length >= prefix.Length + 4
            ? id.Substring(prefix.Length, 4)
            : null;
    }
}
