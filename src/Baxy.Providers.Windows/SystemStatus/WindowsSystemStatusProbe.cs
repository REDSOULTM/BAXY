using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security;
using System.Text;
using Microsoft.Win32;

namespace Baxy.Providers.Windows.SystemStatus;

internal readonly record struct CpuTimeSample(
    ulong Idle,
    ulong Kernel,
    ulong User);

internal readonly record struct MemoryReading(
    ulong TotalBytes,
    ulong AvailableBytes);

internal readonly record struct DiskReading(
    long TotalBytes,
    long AvailableBytes);

internal readonly record struct PowerReading(
    byte AcLineStatus,
    byte BatteryFlag,
    byte BatteryLifePercent);

internal readonly record struct OperatingSystemReading(
    int MajorVersion,
    int MinorVersion,
    int BuildNumber,
    string Architecture,
    bool IsWorkstation);

internal interface ISystemStatusProbe
{
    CpuTimeSample ReadCpuTimes();

    int ReadLogicalProcessorCount();

    string? ReadCpuModel();

    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);

    MemoryReading ReadMemory();

    DiskReading ReadSystemDisk();

    PowerReading ReadPowerStatus();

    OperatingSystemReading ReadOperatingSystem();

    ulong ReadUptimeMilliseconds();
}

internal sealed partial class WindowsSystemStatusProbe : ISystemStatusProbe
{
    private const ushort AllProcessorGroups = 0xFFFF;
    private const int OsVersionInformationSize = 284;
    private const int OsProductTypeOffset = 282;
    private const byte NtWorkstation = 1;
    private const byte NtDomainController = 2;
    private const byte NtServer = 3;
    private const int MaximumCpuModelUtf8Bytes = 512;
    private const string CpuRegistryPath = @"HARDWARE\DESCRIPTION\System\CentralProcessor\0";
    private const string CpuRegistryValue = "ProcessorNameString";

    public CpuTimeSample ReadCpuTimes()
    {
        if (GetSystemTimes(out NativeFileTime idle, out NativeFileTime kernel, out NativeFileTime user) == 0)
        {
            throw CreateLastWin32Exception("Windows did not return processor time counters.");
        }

        return new CpuTimeSample(idle.ToUInt64(), kernel.ToUInt64(), user.ToUInt64());
    }

    public int ReadLogicalProcessorCount()
    {
        uint count = GetActiveProcessorCount(AllProcessorGroups);
        if (count == 0 || count > int.MaxValue)
        {
            throw CreateLastWin32Exception("Windows did not return a valid processor count.");
        }

        return checked((int)count);
    }

    public string? ReadCpuModel()
    {
        try
        {
            using RegistryKey? key = Registry.LocalMachine.OpenSubKey(CpuRegistryPath, writable: false);
            object? raw = key?.GetValue(
                CpuRegistryValue,
                defaultValue: null,
                RegistryValueOptions.DoNotExpandEnvironmentNames);
            if (raw is not string value)
            {
                return null;
            }

            string model = value.Trim();
            if (model.Length == 0
                || Encoding.UTF8.GetByteCount(model) > MaximumCpuModelUtf8Bytes
                || model.Any(static character => char.IsControl(character)))
            {
                return null;
            }

            return model.Normalize(NormalizationForm.FormC);
        }
        catch (Exception exception) when (exception is IOException
            or ArgumentException
            or UnauthorizedAccessException
            or SecurityException)
        {
            return null;
        }
    }

    public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    public MemoryReading ReadMemory()
    {
        var status = new NativeMemoryStatus
        {
            Length = checked((uint)Marshal.SizeOf<NativeMemoryStatus>()),
        };
        if (GlobalMemoryStatusEx(ref status) == 0)
        {
            throw CreateLastWin32Exception("Windows did not return memory status.");
        }

        return new MemoryReading(status.TotalPhysical, status.AvailablePhysical);
    }

    public DiskReading ReadSystemDisk()
    {
        string systemDirectory = Environment.GetFolderPath(Environment.SpecialFolder.System);
        string? root = Path.GetPathRoot(systemDirectory);
        if (string.IsNullOrWhiteSpace(root))
        {
            throw new IOException("The Windows system volume could not be resolved.");
        }

        var drive = new DriveInfo(root);
        if (!drive.IsReady)
        {
            throw new IOException("The Windows system volume is not ready.");
        }

        return new DiskReading(drive.TotalSize, drive.AvailableFreeSpace);
    }

    public PowerReading ReadPowerStatus()
    {
        if (GetSystemPowerStatus(out NativePowerStatus status) == 0)
        {
            throw CreateLastWin32Exception("Windows did not return power status.");
        }

        return new PowerReading(
            status.AcLineStatus,
            status.BatteryFlag,
            status.BatteryLifePercent);
    }

    public OperatingSystemReading ReadOperatingSystem()
    {
        nint buffer = Marshal.AllocHGlobal(OsVersionInformationSize);
        try
        {
            byte[] zeros = new byte[OsVersionInformationSize];
            Marshal.Copy(zeros, 0, buffer, zeros.Length);
            Marshal.WriteInt32(buffer, OsVersionInformationSize);
            int result = RtlGetVersion(buffer);
            if (result != 0)
            {
                throw new Win32Exception(result, "Windows did not return its version.");
            }

            byte productType = Marshal.ReadByte(buffer, OsProductTypeOffset);
            bool isWorkstation = productType switch
            {
                NtWorkstation => true,
                NtDomainController or NtServer => false,
                _ => throw new InvalidOperationException(
                    "Windows returned an unknown operating-system product type."),
            };
            return new OperatingSystemReading(
                Marshal.ReadInt32(buffer, sizeof(int)),
                Marshal.ReadInt32(buffer, sizeof(int) * 2),
                Marshal.ReadInt32(buffer, sizeof(int) * 3),
                GetArchitectureName(RuntimeInformation.OSArchitecture),
                isWorkstation);
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    public ulong ReadUptimeMilliseconds() => GetTickCount64();

    private static string GetArchitectureName(Architecture architecture) => architecture switch
    {
        Architecture.X64 => "x64",
        Architecture.X86 => "x86",
        Architecture.Arm64 => "arm64",
        Architecture.Arm => "arm",
        _ => "unknown",
    };

    private static Win32Exception CreateLastWin32Exception(string message) =>
        new(Marshal.GetLastPInvokeError(), message);

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct NativeFileTime
    {
        public readonly uint LowDateTime;
        public readonly uint HighDateTime;

        public ulong ToUInt64() => ((ulong)HighDateTime << 32) | LowDateTime;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeMemoryStatus
    {
        public uint Length;
        public uint MemoryLoad;
        public ulong TotalPhysical;
        public ulong AvailablePhysical;
        public ulong TotalPageFile;
        public ulong AvailablePageFile;
        public ulong TotalVirtual;
        public ulong AvailableVirtual;
        public ulong AvailableExtendedVirtual;
    }

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct NativePowerStatus
    {
        public readonly byte AcLineStatus;
        public readonly byte BatteryFlag;
        public readonly byte BatteryLifePercent;
        public readonly byte SystemStatusFlag;
        public readonly uint BatteryLifeTime;
        public readonly uint BatteryFullLifeTime;
    }

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial int GetSystemTimes(
        out NativeFileTime idleTime,
        out NativeFileTime kernelTime,
        out NativeFileTime userTime);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial uint GetActiveProcessorCount(ushort groupNumber);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial int GlobalMemoryStatusEx(ref NativeMemoryStatus buffer);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial int GetSystemPowerStatus(out NativePowerStatus systemPowerStatus);

    [LibraryImport("kernel32.dll")]
    private static partial ulong GetTickCount64();

    [LibraryImport("ntdll.dll", EntryPoint = "RtlGetVersion")]
    private static partial int RtlGetVersion(nint versionInformation);
}
