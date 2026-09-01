using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;

namespace Baxy.App;

/// <summary>
/// Enumerates the BAXY process tree (shell, core, mind, llama-server) and
/// attributes CPU, RAM, handles and VRAM. Unowned processes are omitted.
/// </summary>
internal sealed class OwnedProcessReader : IPresenceProcessReader
{
    private readonly int _rootProcessId;
    private readonly IReadOnlyList<string> _ownedRoots;
    private readonly Func<IReadOnlyDictionary<int, long>> _vramByPid;

    internal OwnedProcessReader(
        int rootProcessId,
        IReadOnlyList<string> ownedRoots,
        Func<IReadOnlyDictionary<int, long>>? vramByPid = null)
    {
        _rootProcessId = rootProcessId;
        _ownedRoots = ownedRoots;
        _vramByPid = vramByPid ?? ReadNvidiaComputeApps;
    }

    internal static OwnedProcessReader CreateDefault()
    {
        string exe = WindowsAutostartRegistration.ResolveCurrentExecutable();
        string? exeDirectory = Path.GetDirectoryName(exe);
        var roots = new List<string>();
        if (!string.IsNullOrWhiteSpace(exeDirectory))
        {
            roots.Add(exeDirectory);
        }

        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (!string.IsNullOrWhiteSpace(local))
        {
            roots.Add(Path.Combine(local, "BAXYRuntime"));
            roots.Add(Path.Combine(local, "BAXY"));
        }

        roots.Add(@"D:\BAXYRuntime");
        return new OwnedProcessReader(Environment.ProcessId, roots);
    }

    public IReadOnlyList<PresenceProcessSample> ReadOwned()
    {
        Dictionary<int, int> parents = SnapshotParents();
        HashSet<int> ownedIds = ExpandOwnedIds(parents);
        IReadOnlyDictionary<int, long> vram = _vramByPid();
        var samples = new List<PresenceProcessSample>();
        foreach (int processId in ownedIds.OrderBy(static id => id))
        {
            if (!TryReadProcess(processId, vram, out PresenceProcessSample? sample)
                || sample is null)
            {
                continue;
            }

            samples.Add(sample);
        }

        return samples;
    }

    private HashSet<int> ExpandOwnedIds(IReadOnlyDictionary<int, int> parents)
    {
        DateTime rootStart = StartTimeUtc(_rootProcessId) ?? DateTime.MinValue;
        var owned = new HashSet<int> { _rootProcessId };
        bool grew = true;
        while (grew)
        {
            grew = false;
            foreach ((int child, int parent) in parents)
            {
                if (!owned.Contains(parent) || owned.Contains(child))
                {
                    continue;
                }

                if (!IsDescendantCandidate(child, rootStart))
                {
                    continue;
                }

                owned.Add(child);
                grew = true;
            }
        }

        foreach ((int processId, _) in parents)
        {
            if (owned.Contains(processId))
            {
                continue;
            }

            if (TryReadPath(processId, out string path)
                && IsOwnedPath(path)
                && (StartTimeUtc(processId) ?? DateTime.MaxValue) >= rootStart)
            {
                owned.Add(processId);
            }
        }

        return owned;
    }

    private bool IsDescendantCandidate(int processId, DateTime rootStart)
    {
        if ((StartTimeUtc(processId) ?? DateTime.MinValue) < rootStart)
        {
            return false;
        }

        if (!TryReadPath(processId, out string path))
        {
            return false;
        }

        if (IsOwnedPath(path))
        {
            return true;
        }

        string name = Path.GetFileNameWithoutExtension(path);
        if (name.Equals("msedgewebview2", StringComparison.OrdinalIgnoreCase)
            || name.Equals("conhost", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        // A venv launcher delegates to the base interpreter installed outside
        // BAXYRuntime. Parentage and start time already prove ownership here.
        return name.Equals("python", StringComparison.OrdinalIgnoreCase);
    }

    private static DateTime? StartTimeUtc(int processId)
    {
        try
        {
            using var process = Process.GetProcessById(processId);
            return process.StartTime.ToUniversalTime();
        }
        catch (Exception exception) when (
            exception is ArgumentException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception)
        {
            return null;
        }
    }

    private bool IsOwnedPath(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return false;
        }

        foreach (string root in _ownedRoots)
        {
            if (path.StartsWith(root, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        string name = Path.GetFileNameWithoutExtension(path);
        return name.Equals("Baxy", StringComparison.OrdinalIgnoreCase)
            || name.Equals("baxy-core", StringComparison.OrdinalIgnoreCase)
            || name.Equals("llama-server", StringComparison.OrdinalIgnoreCase);
    }

    private static bool TryReadProcess(
        int processId,
        IReadOnlyDictionary<int, long> vram,
        out PresenceProcessSample? sample)
    {
        sample = null;
        try
        {
            using var process = Process.GetProcessById(processId);
            process.Refresh();
            string path = TryReadPath(processId, out string observed) ? observed : process.ProcessName;
            sample = new PresenceProcessSample(
                process.Id,
                process.ProcessName,
                path,
                Math.Max(0, process.WorkingSet64),
                Math.Max(0, process.HandleCount),
                Math.Max(0, process.TotalProcessorTime.TotalSeconds),
                vram.GetValueOrDefault(process.Id));
            return true;
        }
        catch (Exception exception) when (
            exception is ArgumentException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception
                or NotSupportedException)
        {
            return false;
        }
    }

    private static bool TryReadPath(int processId, out string path)
    {
        path = string.Empty;
        try
        {
            using var process = Process.GetProcessById(processId);
            string? module = process.MainModule?.FileName;
            if (string.IsNullOrWhiteSpace(module))
            {
                return false;
            }

            path = Path.GetFullPath(module);
            return true;
        }
        catch (Exception exception) when (
            exception is ArgumentException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception
                or NotSupportedException)
        {
            return false;
        }
    }

    private static Dictionary<int, int> SnapshotParents()
    {
        var parents = new Dictionary<int, int>();
        nint snapshot = NativeMethods.CreateToolhelp32Snapshot(0x00000002, 0);
        if (snapshot == nint.Zero || snapshot == new nint(-1))
        {
            return parents;
        }

        try
        {
            var entry = new ProcessEntry32
            {
                DwSize = (uint)Marshal.SizeOf<ProcessEntry32>(),
            };
            if (!NativeMethods.Process32First(snapshot, ref entry))
            {
                return parents;
            }

            do
            {
                parents[unchecked((int)entry.Th32ProcessId)] =
                    unchecked((int)entry.Th32ParentProcessId);
            }
            while (NativeMethods.Process32Next(snapshot, ref entry));
        }
        finally
        {
            _ = NativeMethods.CloseHandle(snapshot);
        }

        return parents;
    }

    internal static IReadOnlyDictionary<int, long> ReadNvidiaComputeApps()
    {
        var result = new Dictionary<int, long>();
        try
        {
            using var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = "nvidia-smi",
                    ArgumentList =
                    {
                        "--query-compute-apps=pid,used_gpu_memory",
                        "--format=csv,noheader,nounits",
                    },
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                },
            };
            if (!process.Start())
            {
                return result;
            }

            string output = process.StandardOutput.ReadToEnd();
            if (!process.WaitForExit(2_000))
            {
                try
                {
                    process.Kill(entireProcessTree: true);
                }
                catch (InvalidOperationException)
                {
                }

                return result;
            }

            foreach (string raw in output.Split(
                ['\r', '\n'],
                StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
            {
                string[] parts = raw.Split(',', StringSplitOptions.TrimEntries);
                if (parts.Length < 2)
                {
                    continue;
                }

                if (!int.TryParse(parts[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out int pid))
                {
                    continue;
                }

                if (!long.TryParse(parts[^1], NumberStyles.Integer, CultureInfo.InvariantCulture, out long mebibytes))
                {
                    continue;
                }

                result[pid] = Math.Max(0, mebibytes) * 1024L * 1024L;
            }
        }
        catch (Exception exception) when (
            exception is System.ComponentModel.Win32Exception
                or InvalidOperationException
                or IOException)
        {
            return result;
        }

        return result;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ProcessEntry32
    {
        public uint DwSize;
        public uint CntUsage;
        public uint Th32ProcessId;
        public nuint Th32DefaultHeapId;
        public uint Th32ModuleId;
        public uint CntThreads;
        public uint Th32ParentProcessId;
        public int PcPriClassBase;
        public uint DwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string SzExeFile;
    }

    private static class NativeMethods
    {
        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern nint CreateToolhelp32Snapshot(uint flags, uint processId);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern bool Process32First(nint snapshot, ref ProcessEntry32 entry);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern bool Process32Next(nint snapshot, ref ProcessEntry32 entry);

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool CloseHandle(nint handle);
    }
}
