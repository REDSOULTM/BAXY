using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// A monitor Windows has connected: on the desktop (Active) or connected and off. Key is its identity for this session
/// (the monitor's device path, else its adapter and target ids); X and Y are its desktop position, the primary one at 0,0.
/// </summary>
internal sealed record MonitorState(
    string Key,
    string Name,
    bool Active,
    bool Primary,
    int X,
    int Y,
    int Width,
    int Height,
    int RefreshHz);

/// <summary>
/// RUT2: the monitors of the display topology and turning one on or off (the seam WindowsMonitorAdapter's tests replace,
/// so no test changes the real screens).
/// </summary>
internal interface IMonitorPlatform
{
    /// <summary>The connected monitors, on and off, read from the display topology.</summary>
    IReadOnlyList<MonitorState> Monitors();

    /// <summary>Puts the monitor on the desktop or takes it off; 0 (ERROR_SUCCESS) or the Win32 error SetDisplayConfig gave.</summary>
    int SetActive(string key, bool active);

    /// <summary>The rectangles of the product's own visible windows (BAXY's chat), as left, top, width and height.</summary>
    IReadOnlyList<(int X, int Y, int Width, int Height)> ProductWindows();
}

/// <summary>
/// The Connecting and Configuring Displays (CCD) API of Windows 7 and later (Microsoft Learn, «CCD APIs» and
/// «SetDisplayConfig function»): QueryDisplayConfig reads every path between a display source and a monitor, and
/// SetDisplayConfig applies the set of active paths. A monitor is turned on or off as the DisplayConfig PowerShell module
/// (MartinGC94/DisplayConfig, DisplayConfig.EnableDisableDisplay) does: the topology wanted is supplied with every mode
/// index invalid and SDC_TOPOLOGY_SUPPLIED, so Windows takes positions and modes from its own database of that set of
/// monitors (the layout they had the last time they were on together); when that fails, the paths and the current modes
/// are supplied with SDC_ALLOW_CHANGES and saved (SDC_SAVE_TO_DATABASE), and Windows chooses what is missing.
/// </summary>
internal sealed partial class WindowsMonitorPlatform : IMonitorPlatform
{
    private const uint QdcAllPaths = 0x1;
    private const uint PathActive = 0x1;
    private const uint ModeIndexInvalid = 0xffffffff;
    private const uint ModeInfoTypeSource = 1;
    private const uint SdcTopologySupplied = 0x10;
    private const uint SdcUseSuppliedDisplayConfig = 0x20;
    private const uint SdcApply = 0x80;
    private const uint SdcSaveToDatabase = 0x200;
    private const uint SdcAllowChanges = 0x400;
    private const uint SdcAllowPathOrderChanges = 0x2000;
    private const int ErrorInsufficientBuffer = 122;
    private const uint DeviceInfoGetTargetName = 2;

    public IReadOnlyList<MonitorState> Monitors()
    {
        (PathInfo[] paths, ModeInfo[] modes) = Query();
        var monitors = new List<MonitorState>();
        foreach (IGrouping<(uint Low, int High, uint Id), PathInfo> target in paths
            .GroupBy(static path => (path.TargetAdapterLow, path.TargetAdapterHigh, path.TargetId)))
        {
            PathInfo path = target.FirstOrDefault(static path => (path.Flags & PathActive) != 0);
            bool active = (path.Flags & PathActive) != 0;
            if (!active)
            {
                // Off and not available: not connected, no monitor to list.
                if (!target.Any(static path => path.TargetAvailable != 0))
                {
                    continue;
                }

                path = target.First(static path => path.TargetAvailable != 0);
            }

            (string name, string devicePath) = TargetName(path);
            string key = devicePath.Length > 0
                ? devicePath
                : $"{path.TargetAdapterHigh:x8}{path.TargetAdapterLow:x8}:{path.TargetId}";
            int x = 0, y = 0, width = 0, height = 0, hertz = 0;
            if (active && path.SourceModeIndex < modes.Length && modes[path.SourceModeIndex].InfoType == ModeInfoTypeSource)
            {
                ModeInfo source = modes[path.SourceModeIndex];
                (x, y, width, height) = (source.PositionX, source.PositionY, (int)source.Width, (int)source.Height);
                hertz = path.RefreshDenominator == 0
                    ? 0
                    : (int)Math.Round((double)path.RefreshNumerator / path.RefreshDenominator);
            }

            monitors.Add(new MonitorState(key, name, active, active && x == 0 && y == 0 && width > 0, x, y, width, height, hertz));
        }

        return monitors;
    }

    public int SetActive(string key, bool active)
    {
        (PathInfo[] paths, ModeInfo[] modes) = Query();
        var wanted = new List<PathInfo>();
        bool found = false;
        // Revisión ciega RUT2 (4): an active path stays whatever its availability says (Microsoft Learn: an active path
        // may read targetAvailable FALSE); availability counts only for the one turned on.
        foreach (IGrouping<(uint Low, int High, uint Id), PathInfo> target in paths
            .GroupBy(static path => (path.TargetAdapterLow, path.TargetAdapterHigh, path.TargetId)))
        {
            PathInfo first = target.FirstOrDefault(static path => (path.Flags & PathActive) != 0);
            if ((first.Flags & PathActive) == 0)
            {
                if (!target.Any(static path => path.TargetAvailable != 0))
                {
                    continue;
                }

                first = target.First(static path => path.TargetAvailable != 0);
            }

            (_, string devicePath) = TargetName(first);
            bool isKey = string.Equals(key, devicePath.Length > 0
                ? devicePath
                : $"{first.TargetAdapterHigh:x8}{first.TargetAdapterLow:x8}:{first.TargetId}", StringComparison.Ordinal);
            found |= isKey;
            PathInfo? on = target.Any(static path => (path.Flags & PathActive) != 0)
                ? target.First(static path => (path.Flags & PathActive) != 0)
                : null;
            if (isKey && !active)
            {
                continue;
            }

            if (on is { } kept)
            {
                wanted.Add(kept);
            }
            else if (isKey)
            {
                PathInfo added = first;
                added.Flags |= PathActive;
                added.SourceModeIndex = ModeIndexInvalid;
                added.TargetModeIndex = ModeIndexInvalid;
                wanted.Add(added);
            }
        }

        if (!found)
        {
            return 1168; // ERROR_NOT_FOUND
        }

        // The topology alone: every mode index invalid and the source ids renumbered on each adapter, monitors that
        // shared a source (duplicated screens, revisión ciega RUT2 2) still sharing one, the one turned on its own.
        PathInfo[] topology = [.. wanted];
        var nextSource = new Dictionary<(uint, int), uint>();
        var renumbered = new Dictionary<(uint, int, uint), uint>();
        for (int index = 0; index < topology.Length; index++)
        {
            (uint, int) adapter = (topology[index].SourceAdapterLow, topology[index].SourceAdapterHigh);
            bool kept = topology[index].SourceModeIndex != ModeIndexInvalid;
            (uint, int, uint) old = (adapter.Item1, adapter.Item2, topology[index].SourceId);
            if (!kept || !renumbered.TryGetValue(old, out uint id))
            {
                id = nextSource.GetValueOrDefault(adapter);
                nextSource[adapter] = id + 1;
                if (kept)
                {
                    renumbered[old] = id;
                }
            }

            topology[index].SourceId = id;
            topology[index].SourceModeIndex = ModeIndexInvalid;
            topology[index].TargetModeIndex = ModeIndexInvalid;
        }

        int result = SetDisplayConfig(
            (uint)topology.Length, topology, 0, null, SdcApply | SdcTopologySupplied | SdcAllowPathOrderChanges);
        if (result == 0)
        {
            return 0;
        }

        // Not in Windows' database: the current modes of the monitors kept, Windows choosing the rest, and saved.
        PathInfo[] supplied = [.. wanted];
        var used = supplied.Where(static path => path.SourceModeIndex != ModeIndexInvalid)
            .Select(static path => (path.SourceAdapterLow, path.SourceAdapterHigh, path.SourceId))
            .ToHashSet();
        for (int index = 0; index < supplied.Length; index++)
        {
            if (supplied[index].SourceModeIndex != ModeIndexInvalid)
            {
                continue;
            }

            uint id = 0;
            while (used.Contains((supplied[index].SourceAdapterLow, supplied[index].SourceAdapterHigh, id)))
            {
                id++;
            }

            supplied[index].SourceId = id;
            _ = used.Add((supplied[index].SourceAdapterLow, supplied[index].SourceAdapterHigh, id));
        }

        // With the primary one turned off no source left sits at 0,0: the ones left move together so the first does
        // (Microsoft Learn, «The Virtual Screen»: the primary monitor's upper-left corner is at 0,0).
        uint[] keptModes = supplied.Where(static path => path.SourceModeIndex != ModeIndexInvalid)
            .Select(static path => path.SourceModeIndex).Distinct().ToArray();
        if (keptModes.Length > 0 && !keptModes.Any(index => modes[index].PositionX == 0 && modes[index].PositionY == 0))
        {
            (int dx, int dy) = (modes[keptModes[0]].PositionX, modes[keptModes[0]].PositionY);
            foreach (uint index in keptModes)
            {
                modes[index].PositionX -= dx;
                modes[index].PositionY -= dy;
            }
        }

        return SetDisplayConfig(
            (uint)supplied.Length,
            supplied,
            (uint)modes.Length,
            modes,
            SdcApply | SdcUseSuppliedDisplayConfig | SdcAllowChanges | SdcSaveToDatabase);
    }

    public IReadOnlyList<(int X, int Y, int Width, int Height)> ProductWindows()
    {
        var found = new List<(int, int, int, int)>();
        EnumWindowsProc callback = (handle, _) =>
        {
            if (IsWindowVisible(handle)
                && GetWindowThreadProcessId(handle, out uint processId) != 0
                && WindowsWindowControlProvider.ProductProcess((int)processId)
                && GetWindowRect(handle, out Rect rect)
                && rect.Right > rect.Left
                && rect.Bottom > rect.Top)
            {
                found.Add((rect.Left, rect.Top, rect.Right - rect.Left, rect.Bottom - rect.Top));
            }

            return true;
        };
        _ = EnumWindows(callback, 0);
        GC.KeepAlive(callback);
        return found;
    }

    private static (PathInfo[] Paths, ModeInfo[] Modes) Query()
    {
        for (int attempt = 0; attempt < 4; attempt++)
        {
            int result = GetDisplayConfigBufferSizes(QdcAllPaths, out uint pathCount, out uint modeCount);
            if (result != 0)
            {
                throw new System.ComponentModel.Win32Exception(result);
            }

            var paths = new PathInfo[pathCount];
            var modes = new ModeInfo[modeCount];
            result = QueryDisplayConfig(QdcAllPaths, ref pathCount, paths, ref modeCount, modes, 0);
            if (result == ErrorInsufficientBuffer)
            {
                continue;
            }

            if (result != 0)
            {
                throw new System.ComponentModel.Win32Exception(result);
            }

            return (paths[..(int)pathCount], modes[..(int)modeCount]);
        }

        throw new System.ComponentModel.Win32Exception(ErrorInsufficientBuffer);
    }

    private static unsafe (string Name, string DevicePath) TargetName(PathInfo path)
    {
        TargetDeviceName name = default;
        name.Type = DeviceInfoGetTargetName;
        name.Size = (uint)sizeof(TargetDeviceName);
        name.AdapterLow = path.TargetAdapterLow;
        name.AdapterHigh = path.TargetAdapterHigh;
        name.Id = path.TargetId;
        if (DisplayConfigGetDeviceInfo(ref name) != 0)
        {
            return (string.Empty, string.Empty);
        }

        return (new string(name.FriendlyName).TrimEnd('\0'), new string(name.DevicePath).TrimEnd('\0'));
    }

    // DISPLAYCONFIG_PATH_INFO (72 bytes): the source info, the target info and the path's flags.
    [StructLayout(LayoutKind.Explicit, Size = 72)]
    internal struct PathInfo
    {
        [FieldOffset(0)] public uint SourceAdapterLow;
        [FieldOffset(4)] public int SourceAdapterHigh;
        [FieldOffset(8)] public uint SourceId;
        [FieldOffset(12)] public uint SourceModeIndex;
        [FieldOffset(20)] public uint TargetAdapterLow;
        [FieldOffset(24)] public int TargetAdapterHigh;
        [FieldOffset(28)] public uint TargetId;
        [FieldOffset(32)] public uint TargetModeIndex;
        [FieldOffset(48)] public uint RefreshNumerator;
        [FieldOffset(52)] public uint RefreshDenominator;
        [FieldOffset(60)] public int TargetAvailable;
        [FieldOffset(68)] public uint Flags;
    }

    // DISPLAYCONFIG_MODE_INFO (64 bytes); for a source mode, DISPLAYCONFIG_SOURCE_MODE at offset 16.
    [StructLayout(LayoutKind.Explicit, Size = 64)]
    internal struct ModeInfo
    {
        [FieldOffset(0)] public uint InfoType;
        [FieldOffset(16)] public uint Width;
        [FieldOffset(20)] public uint Height;
        [FieldOffset(28)] public int PositionX;
        [FieldOffset(32)] public int PositionY;
    }

    // DISPLAYCONFIG_TARGET_DEVICE_NAME (420 bytes): the header, then the monitor's friendly name and device path.
    [StructLayout(LayoutKind.Explicit, Size = 420)]
    private unsafe struct TargetDeviceName
    {
        [FieldOffset(0)] public uint Type;
        [FieldOffset(4)] public uint Size;
        [FieldOffset(8)] public uint AdapterLow;
        [FieldOffset(12)] public int AdapterHigh;
        [FieldOffset(16)] public uint Id;
        [FieldOffset(36)] public fixed char FriendlyName[64];
        [FieldOffset(164)] public fixed char DevicePath[128];
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    private delegate bool EnumWindowsProc(nint window, nint parameter);

    [LibraryImport("user32.dll")]
    private static partial int GetDisplayConfigBufferSizes(uint flags, out uint pathCount, out uint modeCount);

    [LibraryImport("user32.dll")]
    private static partial int QueryDisplayConfig(
        uint flags,
        ref uint pathCount,
        [In, Out] PathInfo[] paths,
        ref uint modeCount,
        [In, Out] ModeInfo[] modes,
        nint topology);

    [LibraryImport("user32.dll")]
    private static partial int SetDisplayConfig(
        uint pathCount,
        [In] PathInfo[] paths,
        uint modeCount,
        [In] ModeInfo[]? modes,
        uint flags);

    [LibraryImport("user32.dll")]
    private static partial int DisplayConfigGetDeviceInfo(ref TargetDeviceName request);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint window, out Rect rect);
}
