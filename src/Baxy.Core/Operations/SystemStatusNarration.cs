using System.Globalization;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Core.Operations;

internal static class SystemStatusNarration
{
    internal static string BuildGpuMessage(GpuSystemStatusResult status)
    {
        if (string.Equals(status.Scope, "gpu_identity", StringComparison.Ordinal))
        {
            return string.Join(" ", status.Adapters.Select(DescribeGpuIdentity));
        }

        string message = string.Join(
            " ",
            status.Adapters
                .Where(static adapter => adapter.UsagePercent.HasValue)
                .Select(DescribeGpuUsage));
        string[] unavailable = status.Adapters
            .Where(static adapter => !adapter.UsagePercent.HasValue)
            .Select(static adapter =>
                $"GPU {adapter.AdapterIndex + 1} — {adapter.Name}")
            .ToArray();
        if (unavailable.Length > 0)
        {
            message += $" No pude medir el uso de {string.Join(", ", unavailable)}.";
        }

        return message.TrimStart();
    }

    private static string DescribeGpuIdentity(GpuSystemStatusAdapterResult adapter) =>
        $"GPU {adapter.AdapterIndex + 1} — {adapter.Name}: "
        + $"VRAM {FormatBytes(adapter.DedicatedVideoMemoryBytes)}; "
        + "RAM reservada para gráficos "
        + $"{FormatBytes(adapter.DedicatedSystemMemoryBytes)}; "
        + "límite de RAM compartida "
        + $"{FormatBytes(adapter.SharedSystemMemoryLimitBytes)}.";

    private static string DescribeGpuUsage(GpuSystemStatusAdapterResult adapter)
    {
        ulong dedicatedCapacity = checked(
            adapter.DedicatedVideoMemoryBytes + adapter.DedicatedSystemMemoryBytes);
        return $"GPU {adapter.AdapterIndex + 1} — {adapter.Name}: "
            + $"{FormatPercent(adapter.UsagePercent!.Value)} % de uso; "
            + "memoria gráfica dedicada: "
            + $"{FormatBytes(adapter.DedicatedMemoryUsageBytes!.Value)} en uso de "
            + $"{FormatBytes(dedicatedCapacity)} "
            + $"(VRAM {FormatBytes(adapter.DedicatedVideoMemoryBytes)} + "
            + $"RAM reservada {FormatBytes(adapter.DedicatedSystemMemoryBytes)}); "
            + "RAM compartida: "
            + $"{FormatBytes(adapter.SharedMemoryUsageBytes!.Value)} en uso de un límite de "
            + $"{FormatBytes(adapter.SharedSystemMemoryLimitBytes)}.";
    }

    internal static string GpuFailureMessage(GpuSystemStatusResult status)
    {
        if (string.Equals(status.Scope, "gpu_identity", StringComparison.Ordinal)
            || status.Adapters.Count == 0)
        {
            return "No pude obtener una identificación verificable de la GPU.";
        }

        return $"No pude medir el uso de {string.Join(", ", status.Adapters.Select(
            static adapter => $"GPU {adapter.AdapterIndex + 1} — {adapter.Name}"))}.";
    }

    internal static string BuildMessage(SystemStatusResult status)
    {
        var measurements = new List<string>();
        if (status.Cpu is not null)
        {
            string model = status.Cpu.Model is null ? string.Empty : $" {status.Cpu.Model}";
            measurements.Add(
                $"CPU{model}: {FormatPercent(status.Cpu.UsagePercent)} % de uso y "
                + $"{status.Cpu.LogicalProcessorCount} procesadores lógicos.");
        }

        if (status.Memory is not null)
        {
            measurements.Add(
                $"RAM: {FormatBytes(status.Memory.AvailableBytes)} disponibles de "
                + $"{FormatBytes(status.Memory.TotalBytes)}.");
        }

        if (status.Disk is not null)
        {
            measurements.Add(
                $"Disco del sistema: {FormatBytes((ulong)status.Disk.AvailableBytes)} libres de "
                + $"{FormatBytes((ulong)status.Disk.TotalBytes)}.");
        }

        if (status.Battery is not null)
        {
            measurements.Add(DescribeBattery(status.Battery));
        }

        if (status.Os is not null)
        {
            measurements.Add(DescribeOperatingSystem(status.Os));
        }

        if (status.UptimeSeconds.HasValue)
        {
            measurements.Add($"Tiempo activo: {FormatUptime(status.UptimeSeconds.Value)}.");
        }

        string message = string.Join(" ", measurements);
        if (status.Failures.Count > 0)
        {
            string unavailable = string.Join(
                ", ",
                status.Failures.Select(static failure => PublicScopeLabel(failure.Scope)));
            message += $" No pude medir: {unavailable}.";
        }

        return message;
    }

    private static string DescribeBattery(SystemStatusBatteryResult battery)
    {
        if (battery.IsPresent is false)
        {
            return battery.IsAcOnline is true
                ? "Este equipo no informa una batería instalada y está conectado a corriente."
                : "Este equipo no informa una batería instalada.";
        }

        if (battery.IsPresent is null)
        {
            return battery.IsAcOnline is true
                ? "Windows no confirmó si hay una batería; el equipo está conectado a corriente."
                : "Windows no confirmó si hay una batería; el equipo no está conectado a corriente.";
        }

        var details = new List<string>();
        if (battery.ChargePercent.HasValue)
        {
            details.Add($"{battery.ChargePercent.Value} %");
        }

        if (battery.IsCharging.HasValue)
        {
            details.Add(battery.IsCharging.Value ? "cargando" : "sin cargar");
        }

        if (battery.IsAcOnline.HasValue)
        {
            details.Add(battery.IsAcOnline.Value ? "con corriente" : "usando batería");
        }

        return details.Count == 0
            ? "El equipo informa una batería instalada."
            : $"Batería: {string.Join(", ", details)}.";
    }

    private static string DescribeOperatingSystem(SystemStatusOperatingSystemResult os)
    {
        if (!os.IsWorkstation)
        {
            return $"Windows Server (versión interna {os.MajorVersion}.{os.MinorVersion}), "
                + $"compilación {os.BuildNumber}, {os.Architecture}.";
        }

        if (os.MajorVersion == 10 && os.MinorVersion == 0 && os.BuildNumber >= 22000)
        {
            return $"Windows 11 (versión interna 10.0), compilación {os.BuildNumber}, "
                + $"{os.Architecture}.";
        }

        return $"Windows {os.MajorVersion}.{os.MinorVersion}, "
            + $"compilación {os.BuildNumber}, {os.Architecture}.";
    }

    internal static string FailureMessage(string scope) => scope switch
    {
        "cpu" => "No pude obtener una lectura verificable de la CPU.",
        "memory" => "No pude obtener una lectura verificable de la memoria.",
        "disk" => "No pude obtener una lectura verificable del disco del sistema.",
        "battery" => "No pude obtener una lectura verificable de la batería.",
        "os" => "No pude obtener una versión verificable de Windows.",
        _ => "No pude obtener ninguna medición verificable del estado del equipo.",
    };

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

    private static string PublicScopeLabel(string scope) => scope switch
    {
        "cpu" => "CPU",
        "memory" => "RAM",
        "disk" => "disco",
        "battery" => "batería",
        "os" => "Windows",
        "uptime" => "tiempo activo",
        _ => "estado",
    };

    private static string FormatPercent(double value) =>
        value.ToString("0.#", CultureInfo.InvariantCulture);

    private static string FormatBytes(ulong bytes)
    {
        const double gibibyte = 1024d * 1024d * 1024d;
        const double mebibyte = 1024d * 1024d;
        return bytes >= gibibyte
            ? $"{(bytes / gibibyte).ToString("0.#", CultureInfo.InvariantCulture)} GiB"
            : $"{(bytes / mebibyte).ToString("0.#", CultureInfo.InvariantCulture)} MiB";
    }

    private static string FormatUptime(long seconds)
    {
        long totalMinutes = seconds / 60;
        long totalHours = totalMinutes / 60;
        long totalDays = totalHours / 24;
        return totalDays >= 1
            ? $"{totalDays} d {totalHours % 24} h"
            : totalHours >= 1
                ? $"{totalHours} h {totalMinutes % 60} min"
                : $"{totalMinutes} min";
    }
}
