using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Core.Operations;

internal static class SystemStatusNarration
{
    internal static string ToPublicGpuScope(GpuStatusScope scope) => scope switch
    {
        GpuStatusScope.Identity => "gpu_identity",
        GpuStatusScope.Usage => "gpu_usage",
        _ => throw new ArgumentOutOfRangeException(nameof(scope)),
    };

    internal static string ToPublicScope(SystemStatusScope scope) => scope switch
    {
        SystemStatusScope.Cpu => "cpu",
        SystemStatusScope.Memory => "memory",
        SystemStatusScope.SystemDisk => "disk",
        SystemStatusScope.Battery => "battery",
        SystemStatusScope.OperatingSystem => "os",
        SystemStatusScope.Uptime => "uptime",
        _ => throw new ArgumentOutOfRangeException(nameof(scope)),
    };
}
