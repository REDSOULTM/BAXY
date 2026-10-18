using System.Runtime.InteropServices;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>A display mode as Windows lists it: resolution, refresh rate and color depth.</summary>
internal readonly record struct DisplayModeValue(uint Width, uint Height, uint RefreshHz, uint BitsPerPixel);

/// <summary>
/// The Win32 display settings of the primary monitor (EnumDisplayDevices, EnumDisplaySettings and
/// ChangeDisplaySettingsEx): the seam the adapter's tests replace, so no test changes the real screen.
/// </summary>
internal interface IDisplayModePlatform
{
    /// <summary>The device name of the primary monitor attached to the desktop, or null.</summary>
    string? PrimaryDevice();

    /// <summary>The mode the device shows now, read back from Windows, or null when it could not be read.</summary>
    DisplayModeValue? Current(string device);

    /// <summary>Every mode the driver lists for the device.</summary>
    IReadOnlyList<DisplayModeValue> Listed(string device);

    /// <summary>ChangeDisplaySettingsEx with CDS_TEST: 0 (DISP_CHANGE_SUCCESSFUL) when Windows would accept it.</summary>
    int Test(string device, DisplayModeValue mode);

    /// <summary>ChangeDisplaySettingsEx with CDS_UPDATEREGISTRY: the mode is applied and kept after a restart.</summary>
    int Apply(string device, DisplayModeValue mode);
}

internal sealed partial class WindowsDisplayModePlatform : IDisplayModePlatform
{
    private const uint AttachedToDesktop = 0x1;
    private const uint PrimaryDeviceFlag = 0x4;
    private const int CurrentSettings = -1;
    private const uint FieldBitsPerPel = 0x00040000;
    private const uint FieldPelsWidth = 0x00080000;
    private const uint FieldPelsHeight = 0x00100000;
    private const uint FieldDisplayFrequency = 0x00400000;
    private const uint ChangeUpdateRegistry = 0x1;
    private const uint ChangeTest = 0x2;

    public string? PrimaryDevice()
    {
        for (uint index = 0; index < 32; index++)
        {
            DisplayDevice device = default;
            device.Size = (uint)Marshal.SizeOf<DisplayDevice>();
            if (!EnumDisplayDevicesW(null, index, ref device, 0))
                return null;
            if ((device.StateFlags & AttachedToDesktop) != 0 && (device.StateFlags & PrimaryDeviceFlag) != 0)
            {
                unsafe
                {
                    return new string(device.DeviceName).TrimEnd('\0');
                }
            }
        }
        return null;
    }

    public DisplayModeValue? Current(string device)
    {
        DeviceMode mode = NewMode();
        return EnumDisplaySettingsW(device, CurrentSettings, ref mode) ? Value(mode) : null;
    }

    public IReadOnlyList<DisplayModeValue> Listed(string device)
    {
        var modes = new List<DisplayModeValue>();
        for (int index = 0; index < 4_096; index++)
        {
            DeviceMode mode = NewMode();
            if (!EnumDisplaySettingsW(device, index, ref mode))
                break;
            modes.Add(Value(mode));
        }
        return modes;
    }

    public int Test(string device, DisplayModeValue mode) => Change(device, mode, ChangeTest);

    public int Apply(string device, DisplayModeValue mode) => Change(device, mode, ChangeUpdateRegistry);

    private static int Change(string device, DisplayModeValue value, uint flags)
    {
        DeviceMode mode = NewMode();
        mode.PelsWidth = value.Width;
        mode.PelsHeight = value.Height;
        mode.DisplayFrequency = value.RefreshHz;
        mode.BitsPerPel = value.BitsPerPixel;
        mode.Fields = FieldPelsWidth | FieldPelsHeight | FieldDisplayFrequency | FieldBitsPerPel;
        return ChangeDisplaySettingsExW(device, ref mode, 0, flags, 0);
    }

    private static DeviceMode NewMode()
    {
        DeviceMode mode = default;
        mode.Size = (ushort)Marshal.SizeOf<DeviceMode>();
        return mode;
    }

    private static DisplayModeValue Value(DeviceMode mode) =>
        new(mode.PelsWidth, mode.PelsHeight, mode.DisplayFrequency, mode.BitsPerPel);

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    private unsafe struct DisplayDevice
    {
        public uint Size;
        public fixed char DeviceName[32];
        public fixed char DeviceString[128];
        public uint StateFlags;
        public fixed char DeviceId[128];
        public fixed char DeviceKey[128];
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    private unsafe struct DeviceMode
    {
        public fixed char DeviceName[32];
        public ushort SpecVersion;
        public ushort DriverVersion;
        public ushort Size;
        public ushort DriverExtra;
        public uint Fields;
        public int PositionX;
        public int PositionY;
        public uint DisplayOrientation;
        public uint DisplayFixedOutput;
        public short Color;
        public short Duplex;
        public short YResolution;
        public short TtOption;
        public short Collate;
        public fixed char FormName[32];
        public ushort LogPixels;
        public uint BitsPerPel;
        public uint PelsWidth;
        public uint PelsHeight;
        public uint DisplayFlags;
        public uint DisplayFrequency;
        public uint IcmMethod;
        public uint IcmIntent;
        public uint MediaType;
        public uint DitherType;
        public uint Reserved1;
        public uint Reserved2;
        public uint PanningWidth;
        public uint PanningHeight;
    }

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumDisplayDevicesW(string? device, uint deviceIndex, ref DisplayDevice displayDevice, uint flags);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumDisplaySettingsW(string deviceName, int modeIndex, ref DeviceMode deviceMode);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int ChangeDisplaySettingsExW(
        string deviceName, ref DeviceMode deviceMode, nint window, uint flags, nint parameter);
}

/// <summary>
/// display.mode.set (auditoría de los pedidos reales, 2026-10-17: the missing skill that weighed most was changing the
/// monitor's refresh rate or resolution, sometimes with going back when it fails): the primary monitor goes to a mode its
/// driver lists, never to one it does not. The mode is asked first with CDS_TEST, then applied and read back; when the
/// read-back is not the mode asked for, the previous mode is put back and read again, and the receipt says so. A width
/// without a height (or the reverse) is refused; with only a resolution the refresh rate is kept when that mode lists it,
/// otherwise the highest it lists is taken.
/// </summary>
internal sealed class WindowsDisplayModeAdapter : IExternalOperationAdapter
{
    private readonly IDisplayModePlatform _platform;

    internal WindowsDisplayModeAdapter()
        : this(new WindowsDisplayModePlatform())
    {
    }

    internal WindowsDisplayModeAdapter(IDisplayModePlatform platform) =>
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));

    public bool CanHandle(string operation) => operation == "display.mode.set";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(Set(operation, arguments, effectBoundary, cancellationToken));
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, "display_mode_failed"));
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or NotSupportedException or System.ComponentModel.Win32Exception or EntryPointNotFoundException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, "display_mode_failed"));
        }
    }

    private ExternalCapabilityReceipt Set(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        uint? width = Optional(arguments, "width");
        uint? height = Optional(arguments, "height");
        uint? refresh = Optional(arguments, "refreshHz");
        if (width is null && height is null && refresh is null)
            return ExternalJson.FailureBeforeEffect(operation, "display_mode_not_given");
        if ((width is null) != (height is null))
            return ExternalJson.FailureBeforeEffect(operation, "display_resolution_needs_width_and_height");

        string? device = _platform.PrimaryDevice();
        if (device is null)
            return ExternalJson.FailureBeforeEffect(operation, "display_devices_not_found");
        if (_platform.Current(device) is not { } previous)
            return ExternalJson.FailureBeforeEffect(operation, "display_settings_not_read");

        uint wantWidth = width ?? previous.Width;
        uint wantHeight = height ?? previous.Height;
        // Only modes of the color depth shown now: a listed mode at another depth is not what was asked.
        List<DisplayModeValue> listed = _platform.Listed(device)
            .Where(mode => mode.BitsPerPixel == previous.BitsPerPixel && mode.Width == wantWidth
                && mode.Height == wantHeight)
            .Distinct()
            .ToList();
        string refreshChosen = "asked";
        DisplayModeValue target;
        if (refresh is { } hertz)
        {
            if (!listed.Any(mode => mode.RefreshHz == hertz))
                return ExternalJson.FailureBeforeEffect(operation, "display_mode_not_listed");
            target = new(wantWidth, wantHeight, hertz, previous.BitsPerPixel);
        }
        else if (listed.Any(mode => mode.RefreshHz == previous.RefreshHz))
        {
            target = new(wantWidth, wantHeight, previous.RefreshHz, previous.BitsPerPixel);
            refreshChosen = "kept";
        }
        else if (listed.Count > 0)
        {
            target = new(wantWidth, wantHeight, listed.Max(mode => mode.RefreshHz), previous.BitsPerPixel);
            refreshChosen = "highest_listed";
        }
        else
        {
            return ExternalJson.FailureBeforeEffect(operation, "display_mode_not_listed");
        }

        if (Same(previous, target))
            return ExternalJson.Switched(operation, Result(previous, previous, refreshChosen, changed: false), false);
        if (_platform.Test(device, target) != 0)
            return ExternalJson.FailureBeforeEffect(operation, "display_mode_test_failed");

        effectBoundary.Cross(cancellationToken);
        int applied = _platform.Apply(device, target);
        DisplayModeValue? after = _platform.Current(device);
        if (after is { } shown && Same(shown, target))
            return ExternalJson.Success(operation, Result(previous, shown, refreshChosen, changed: true));
        if (after is { } unchanged && Same(unchanged, previous))
        {
            // Windows did not apply it (or applied nothing): the screen reads as before, nothing changed.
            return ExternalJson.FailureBeforeEffect(
                operation, applied != 0 ? "display_mode_not_applied" : "display_mode_not_verified");
        }

        // Something else is shown (or nothing could be read): the previous mode goes back and is read again.
        _platform.Apply(device, previous);
        return _platform.Current(device) is { } restored && Same(restored, previous)
            ? ExternalJson.FailureAfterEffect(operation, "display_mode_not_verified_reverted")
            : ExternalJson.FailureAfterEffect(operation, "display_mode_revert_not_verified", effectObserved: true);
    }

    private static bool Same(DisplayModeValue a, DisplayModeValue b) =>
        a.Width == b.Width && a.Height == b.Height && a.RefreshHz == b.RefreshHz;

    private static uint? Optional(JsonElement arguments, string name) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty(name, out JsonElement value)
        && value.ValueKind == JsonValueKind.Number
        && value.TryGetUInt32(out uint number)
            ? number
            : null;

    private static JsonElement Result(DisplayModeValue previous, DisplayModeValue final, string refreshChosen, bool changed) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("changed", changed);
            Write(writer, "previous", previous);
            Write(writer, "final", final);
            writer.WriteString("refreshChosen", refreshChosen);
            writer.WriteString("authority", "windows_display_settings_readback");
            writer.WriteEndObject();
        });

    private static void Write(Utf8JsonWriter writer, string name, DisplayModeValue mode)
    {
        writer.WriteStartObject(name);
        writer.WriteNumber("width", mode.Width);
        writer.WriteNumber("height", mode.Height);
        writer.WriteNumber("refreshHz", mode.RefreshHz);
        writer.WriteEndObject();
    }
}
