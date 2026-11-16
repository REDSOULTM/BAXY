using System.Globalization;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Installer;

/// <summary>INS2: the RAM of this PC, MiB, as BaxyRamNeed.Read gives it (installed, and free now); null where unread.</summary>
internal sealed record MachineRam(long? InstalledMib, long? AvailableMib)
{
    internal static MachineRam Read()
    {
        (long? installed, long? free) = BaxyRamNeed.Read();
        return new MachineRam(installed, free);
    }

    /// <summary>What the log says: «RAM 4096 MB, 454 free».</summary>
    public override string ToString() => string.Create(
        CultureInfo.InvariantCulture, $"RAM {InstalledMib?.ToString(CultureInfo.InvariantCulture) ?? "?"} MB, {AvailableMib?.ToString(CultureInfo.InvariantCulture) ?? "?"} free");
}
