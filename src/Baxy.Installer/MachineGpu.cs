using System.Globalization;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Installer;

internal enum GpuSupport
{
    Measured,
    NotMeasured,
    TooLittleMemory,
    None,
    // VRAM5 (AUD1 F7): a card BAXY runs on, or integrated graphics, on a PC with less RAM installed than the least measured
    // for the model on this machine, and enough for BAXY with a model by API (INS2).
    TooLittleRam,
    TooLittleRamIntegrated,
    // INS2 (MIN1): integrated graphics, by what Windows declares, with the RAM the model takes from: not measured there.
    Integrated,
    // INS2 (MIN1): less RAM installed than Windows and BAXY with no model of its own take: not even a model by API helps.
    TooLittleRamEvenByApi,
}

/// <param name="Integrated">INS2: as Windows declares it (IntegratedGraphics); null where it cannot say.</param>
internal sealed record GpuAdapter(string DeviceId, long? MemoryBytes, bool? Integrated = null);

/// <summary>
/// What the person is told before downloading gigabytes, by PCI vendor id, the way BAXY itself picks its server at every
/// start (MindRuntimeDiscovery). BAXY has been measured on NVIDIA and AMD; Intel graphics have not been; with none of the
/// three it does not start (no_supported_gpu).
/// </summary>
internal static class MachineGpu
{
    private const long MinimumMemoryBytes = 3_800_000_000;

    // VRAM5 (AUD1 F7), INS2: the RAM a PC needs installed, MiB, the same figures the mind starts an integrated GPU by
    // (llm_server.integrated_room) and the App tells at start; their sources are in BaxyRamNeed.
    internal const long WindowsRamMib = BaxyRamNeed.WindowsMib;
    internal const long BaxyRamMib = BaxyRamNeed.TreeMib;
    internal const long IntegratedServerMib = BaxyRamNeed.IntegratedServerMib;

    internal static long MinimumRamMib(bool integrated) => WindowsRamMib + BaxyRamMib + (integrated ? IntegratedServerMib : 0);

    internal static long MinimumApiRamMib => BaxyRamNeed.ByApiMib;

    /// <summary>VRAM5 (AUD1 F7), INS2: what is told of <paramref name="adapters"/> once the RAM installed is known
    /// (<paramref name="installedRamMib"/>, MachineRam; null when unread: as before). Below <see cref="MinimumApiRamMib"/>
    /// BAXY does not fit even with a model by API; below <see cref="MinimumRamMib"/> a card BAXY runs on, or integrated
    /// graphics, only fit that way. Integrated is what Windows declares of the adapter chosen (<see cref="GpuAdapter.Integrated"/>),
    /// whatever its maker: its dedicated memory is a slice of that RAM. Any other answer stays.</summary>
    internal static GpuSupport WithRam(IReadOnlyList<GpuAdapter> adapters, long? installedRamMib)
    {
        GpuSupport support = Choose(adapters);
        bool integrated = Integrated(adapters);
        if (support == GpuSupport.None || installedRamMib is not { } ram)
        {
            return support == GpuSupport.None || !integrated ? support : GpuSupport.Integrated;
        }

        return ram < MinimumApiRamMib ? GpuSupport.TooLittleRamEvenByApi
            : integrated ? (ram < MinimumRamMib(integrated: true) ? GpuSupport.TooLittleRamIntegrated : GpuSupport.Integrated)
            : support is GpuSupport.Measured or GpuSupport.NotMeasured && ram < MinimumRamMib(integrated: false) ? GpuSupport.TooLittleRam
            : support;
    }

    private const string Nvidia = "10de";
    private const string Amd = "1002";
    private const string Intel = "8086";

    internal static GpuSupport Choose(IReadOnlyList<GpuAdapter> adapters) =>
        Chosen(adapters) is not { } chosen ? GpuSupport.None
        : Vendor(chosen.DeviceId) == Intel ? GpuSupport.NotMeasured
        : Sized(chosen);

    /// <summary>INS2: whether Windows declares integrated the adapter BAXY is told by.</summary>
    internal static bool Integrated(IReadOnlyList<GpuAdapter> adapters) => Chosen(adapters)?.Integrated == true;

    /// <summary>The adapter BAXY is told by: NVIDIA, else AMD, else Intel, as BAXY picks its server at every start; of one
    /// maker, a card Windows does not declare integrated before integrated graphics (INS2: a Ryzen's Radeon beside a
    /// Radeon card).</summary>
    private static GpuAdapter? Chosen(IReadOnlyList<GpuAdapter> adapters) =>
        new[] { Nvidia, Amd, Intel }
            .Select(maker => adapters.Where(adapter => Vendor(adapter.DeviceId) == maker).OrderBy(static adapter => adapter.Integrated == true).FirstOrDefault())
            .FirstOrDefault(static adapter => adapter is not null);

    /// <summary>
    /// The cards as BAXY reads them at every start (WindowsGpuVendors, DXGI), the same source compiled in here. Not the
    /// screens of this session (EnumDisplayDevices): a card with no screen plugged, as the NVIDIA one of a laptop whose
    /// panel hangs from the integrated graphics, is not among them, and its part was not downloaded (INS-2).
    /// </summary>
    internal static IReadOnlyList<GpuAdapter> Installed() =>
        Environment.GetEnvironmentVariable(TestVariable) is { Length: > 0 } faked
            ? Faked(faked)
            : Installed(new WindowsGpuStatusProbe(), static key => IntegratedGraphics.Declared(key.LowPart, key.HighPart));

    internal static IReadOnlyList<GpuAdapter> Installed(IGpuStatusProbe probe, Func<GpuAdapterKey, bool?>? integrated = null) =>
        [.. WindowsGpuVendors.Adapters(probe).Select(adapter => new GpuAdapter(
            HardwareId(adapter.VendorId, adapter.DeviceId),
            (long)Math.Min(adapter.DedicatedVideoMemoryBytes, long.MaxValue),
            integrated?.Invoke(adapter.Key)))];

    /// <summary>INS2: the cards faked for a test of the real executable, as the App's BAXY_TEST_VRAM_* fake its card:
    /// «vendor:device:MiB[:integrated]» in hexadecimal ids, separated by «,» (MIN1's HP 15: «1002:1636:512:integrated»).
    /// With BaxyRamNeed.TestVariable for its RAM.</summary>
    internal const string TestVariable = "BAXY_TEST_GPUS";

    internal static IReadOnlyList<GpuAdapter> Faked(string faked) =>
        [.. faked.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Select(static card =>
        {
            string[] parts = card.Split(':');
            return new GpuAdapter(
                HardwareId(uint.Parse(parts[0], NumberStyles.HexNumber, CultureInfo.InvariantCulture), uint.Parse(parts[1], NumberStyles.HexNumber, CultureInfo.InvariantCulture)),
                long.Parse(parts[2], CultureInfo.InvariantCulture) * 1024 * 1024,
                parts.Length > 3 ? parts[3] == "integrated" : null);
        })];

    /// <summary>What the log says of this machine: what is told, every card with its dedicated memory and whether Windows
    /// declares it integrated, and the RAM installed and free (INS2).</summary>
    internal static string Describe(IReadOnlyList<GpuAdapter> adapters, MachineRam ram) =>
        string.Create(
            CultureInfo.InvariantCulture,
            $"{WithRam(adapters, ram.InstalledMib)} [{string.Join(", ", adapters.Select(static adapter => string.Create(CultureInfo.InvariantCulture, $"{adapter.DeviceId} {(adapter.MemoryBytes ?? 0) / 1_000_000_000d:0.0} GB{(adapter.Integrated == true ? " integrated" : string.Empty)}")))}]; {ram}");

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
