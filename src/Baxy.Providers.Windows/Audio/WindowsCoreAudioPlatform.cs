using System.Runtime.InteropServices;
using System.Globalization;
using System.Diagnostics;
using System.Runtime.InteropServices.Marshalling;
using System.Security.Cryptography;
using System.Text;

namespace Baxy.Providers.Windows.Audio;

internal interface IWindowsAudioEndpoint : IDisposable
{
    string EndpointId { get; }

    string? ReadDisplayName();

    float ReadVolumeScalar();

    bool ReadMuted();

    void SetVolumeScalar(float scalar, Guid eventContext);

    void SetMuted(bool muted, Guid eventContext);
}

internal interface IWindowsAudioPlatform
{
    DateTimeOffset UtcNow { get; }

    IWindowsAudioEndpoint OpenDefaultOutput();
}

internal sealed class AudioPlatformException : Exception
{
    public AudioPlatformException(string errorCode)
        : base("The Windows audio endpoint operation failed.")
    {
        ErrorCode = errorCode;
    }

    public string ErrorCode { get; }
}

internal static class AudioEndpointIdentity
{
    private const int MaximumEndpointIdUtf8Bytes = 8 * 1024;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    public static string Hash(string endpointId)
    {
        if (string.IsNullOrWhiteSpace(endpointId)
            || endpointId.Any(static character => character == '\0')
            || StrictUtf8.GetByteCount(endpointId) > MaximumEndpointIdUtf8Bytes)
        {
            throw new AudioPlatformException(AudioControlErrorCodes.EndpointUnavailable);
        }

        return Convert.ToHexStringLower(SHA256.HashData(StrictUtf8.GetBytes(endpointId)));
    }
}

internal sealed partial class WindowsCoreAudioPlatform : IWindowsAudioPlatform
{
    private const uint ClsctxAll = 0x17;
    private const uint CoinitMultithreaded = 0;
    private const int SFalse = 1;
    private const int RpcEChangedMode = unchecked((int)0x80010106);
    private const int ENotFound = unchecked((int)0x80070490);
    private const int AudclntEDeviceInvalidated = unchecked((int)0x88890004);
    private const int AudclntEServiceNotRunning = unchecked((int)0x88890010);
    private const int EDataFlowRender = 0;
    private const int EDataFlowCapture = 1;
    private const int ERoleMultimedia = 1;

    private static readonly Guid ClsidMmDeviceEnumerator =
        new("bcde0395-e52f-467c-8e3d-c4579291692e");
    private static readonly Guid IidMmDeviceEnumerator =
        new("a95664d2-9614-4f35-a746-de8db63617e6");
    private static readonly Guid IidAudioEndpointVolume =
        new("5cdf2c82-841e-4546-9722-0cf74078229a");
    private static readonly StrategyBasedComWrappers ComWrappers = new();

    public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;

    public IWindowsAudioEndpoint OpenDefaultOutput() =>
        OpenDefaultEndpoint(EDataFlowRender, AudioControlErrorCodes.NoDefaultOutput);

    internal static IWindowsAudioEndpoint OpenDefaultInput() =>
        OpenDefaultEndpoint(EDataFlowCapture, AudioControlErrorCodes.NoDefaultInput);

    private static WindowsCoreAudioEndpoint OpenDefaultEndpoint(
        int dataFlow,
        string missingEndpointError)
    {
        ComInitialization initialization = InitializeCom();
        IDisposable? enumeratorLease = null;
        IDisposable? deviceLease = null;
        IDisposable? volumeLease = null;
        try
        {
            int result = CoCreateInstance(
                in ClsidMmDeviceEnumerator,
                0,
                ClsctxAll,
                in IidMmDeviceEnumerator,
                out nint enumeratorPointer);
            ReleaseOnFailure(result, enumeratorPointer);
            ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
            IMmDeviceEnumerator enumerator = WrapUnique<IMmDeviceEnumerator>(
                enumeratorPointer,
                out enumeratorLease);

            result = enumerator.GetDefaultAudioEndpoint(
                dataFlow,
                ERoleMultimedia,
                out nint devicePointer);
            ReleaseOnFailure(result, devicePointer);
            ThrowForHResult(result, missingEndpointError);
            IMmDevice device = WrapUnique<IMmDevice>(devicePointer, out deviceLease);

            string endpointId = ReadEndpointId(device);
            result = device.Activate(
                in IidAudioEndpointVolume,
                ClsctxAll,
                0,
                out nint volumePointer);
            ReleaseOnFailure(result, volumePointer);
            ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
            IAudioEndpointVolume volume = WrapUnique<IAudioEndpointVolume>(
                volumePointer,
                out volumeLease);

            WindowsCoreAudioEndpoint endpoint = new(
                endpointId,
                device,
                volume,
                volumeLease,
                deviceLease,
                enumeratorLease,
                initialization);
            volumeLease = null;
            deviceLease = null;
            enumeratorLease = null;
            initialization = default;
            return endpoint;
        }
        catch
        {
            volumeLease?.Dispose();
            deviceLease?.Dispose();
            enumeratorLease?.Dispose();
            initialization.Dispose();
            throw;
        }
    }

    private static ComInitialization InitializeCom()
    {
        int result = CoInitializeEx(0, CoinitMultithreaded);
        if (result < 0 && result != RpcEChangedMode)
        {
            ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        }

        return new ComInitialization(result is 0 or SFalse);
    }

    private static unsafe string ReadEndpointId(IMmDevice device)
    {
        int result = device.GetId(out nint pointer);
        if (result < 0 && pointer != 0)
        {
            CoTaskMemFree(pointer);
        }

        ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        if (pointer == 0)
        {
            throw new AudioPlatformException(AudioControlErrorCodes.EndpointUnavailable);
        }

        try
        {
            string endpointId = new((char*)pointer);
            _ = AudioEndpointIdentity.Hash(endpointId);
            return endpointId;
        }
        finally
        {
            CoTaskMemFree(pointer);
        }
    }

    private static T WrapUnique<T>(nint pointer, out IDisposable lease)
        where T : class
    {
        if (pointer == 0)
        {
            throw new AudioPlatformException(AudioControlErrorCodes.EndpointUnavailable);
        }

        object wrapper;
        try
        {
            wrapper = ComWrappers.GetOrCreateObjectForComInstance(
                pointer,
                CreateObjectFlags.UniqueInstance);
        }
        finally
        {
            ReleaseIUnknown(pointer);
        }

        if (wrapper is not T typed || wrapper is not ComObject comObject)
        {
            (wrapper as ComObject)?.FinalRelease();
            throw new AudioPlatformException(AudioControlErrorCodes.EndpointUnavailable);
        }

        lease = new ComObjectLease(comObject);
        return typed;
    }

    private static unsafe string? ReadEndpointDisplayName(IMmDevice device)
    {
        // Core Audio exposes the endpoint label through a read-only property
        // store. It is display data, separate from the private endpoint ID.
        int result = device.OpenPropertyStore(0, out nint storePointer);
        ReleaseOnFailure(result, storePointer);
        ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        IAudioPropertyStore store = WrapUnique<IAudioPropertyStore>(storePointer, out IDisposable lease);
        using (lease)
        {
            AudioPropertyKey key = new(new Guid("a45c254e-df1c-4efd-8020-67d146a850e0"), 14);
            // PROPVARIANT occupies 24 bytes on 64-bit Windows (16 on 32-bit).
            // Allocate the larger size with native alignment; VT_LPWSTR's
            // pointer is at byte offset 8 on both architectures.
            ulong* value = stackalloc ulong[3];
            new Span<ulong>(value, 3).Clear();
            try
            {
                result = store.GetValue(in key, (nint)value);
                ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
                ushort variantType = *(ushort*)value;
                if (variantType == 0)
                {
                    return null; // S_OK + VT_EMPTY means the property is absent.
                }

                if (variantType != 31)
                {
                    throw new AudioPlatformException(AudioControlErrorCodes.EndpointUnavailable);
                }

                nint textPointer = *(nint*)((byte*)value + 8);
                string? name = textPointer == 0 ? null : Marshal.PtrToStringUni(textPointer);
                return string.IsNullOrWhiteSpace(name) || name.Length > 512 || name.Any(char.IsControl)
                    ? null
                    : name;
            }
            finally
            {
                _ = PropVariantClear((nint)value);
            }
        }
    }

    private static unsafe void ReleaseIUnknown(nint pointer)
    {
        nint vtable = *(nint*)pointer;
        nint releasePointer = *((nint*)vtable + 2);
        delegate* unmanaged[Stdcall]<nint, uint> release =
            (delegate* unmanaged[Stdcall]<nint, uint>)releasePointer;
        _ = release(pointer);
    }

    private static void ReleaseOnFailure(int result, nint pointer)
    {
        if (result < 0 && pointer != 0)
        {
            ReleaseIUnknown(pointer);
        }
    }

    private sealed class ComObjectLease(ComObject comObject) : IDisposable
    {
        private ComObject? _comObject = comObject;

        public void Dispose()
        {
            ComObject? current = Interlocked.Exchange(ref _comObject, null);
            current?.FinalRelease();
        }
    }

    private static void ThrowForHResult(int result, string fallbackErrorCode)
    {
        if (result >= 0)
        {
            return;
        }

        string errorCode = result switch
        {
            ENotFound => fallbackErrorCode,
            AudclntEServiceNotRunning => AudioControlErrorCodes.AudioServiceUnavailable,
            AudclntEDeviceInvalidated => AudioControlErrorCodes.EndpointUnavailable,
            _ => fallbackErrorCode,
        };
        throw new AudioPlatformException(errorCode);
    }

    [LibraryImport("ole32.dll")]
    private static partial int CoInitializeEx(nint reserved, uint coInit);

    [LibraryImport("ole32.dll")]
    private static partial int PropVariantClear(nint value);

    [LibraryImport("ole32.dll")]
    private static partial void CoUninitialize();

    [LibraryImport("ole32.dll")]
    private static partial int CoCreateInstance(
        in Guid classId,
        nint outer,
        uint classContext,
        in Guid interfaceId,
        out nint instance);

    [LibraryImport("ole32.dll")]
    private static partial void CoTaskMemFree(nint pointer);

    private struct ComInitialization(bool uninitialize) : IDisposable
    {
        private bool _uninitialize = uninitialize;

        public void Dispose()
        {
            if (_uninitialize)
            {
                _uninitialize = false;
                CoUninitialize();
            }
        }
    }

    private sealed class WindowsCoreAudioEndpoint(
        string endpointId,
        IMmDevice device,
        IAudioEndpointVolume volume,
        IDisposable volumeLease,
        IDisposable deviceLease,
        IDisposable enumeratorLease,
        ComInitialization initialization) : IWindowsAudioEndpoint
    {
        private IDisposable? _volumeLease = volumeLease;
        private IDisposable? _deviceLease = deviceLease;
        private IDisposable? _enumeratorLease = enumeratorLease;
        private ComInitialization _initialization = initialization;

        public string EndpointId { get; } = endpointId;

        public string? ReadDisplayName()
        {
            ObjectDisposedException.ThrowIf(_deviceLease is null, this);
            return ReadEndpointDisplayName(device);
        }

        public float ReadVolumeScalar()
        {
            ObjectDisposedException.ThrowIf(_volumeLease is null, this);
            int result = volume.GetMasterVolumeLevelScalar(out float scalar);
            ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
            if (!float.IsFinite(scalar) || scalar is < 0f or > 1f)
            {
                throw new AudioPlatformException(AudioControlErrorCodes.EndpointUnavailable);
            }

            return scalar;
        }

        public bool ReadMuted()
        {
            ObjectDisposedException.ThrowIf(_volumeLease is null, this);
            int result = volume.GetMute(out int muted);
            ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
            if (muted is not (0 or 1))
            {
                throw new AudioPlatformException(AudioControlErrorCodes.EndpointUnavailable);
            }

            return muted != 0;
        }

        public void SetVolumeScalar(float scalar, Guid eventContext)
        {
            ObjectDisposedException.ThrowIf(_volumeLease is null, this);
            if (!float.IsFinite(scalar) || scalar is < 0f or > 1f)
            {
                throw new ArgumentOutOfRangeException(nameof(scalar));
            }

            int result = volume.SetMasterVolumeLevelScalar(scalar, in eventContext);
            ThrowForHResult(result, AudioControlErrorCodes.OperationFailed);
        }

        public void SetMuted(bool muted, Guid eventContext)
        {
            ObjectDisposedException.ThrowIf(_volumeLease is null, this);
            int result = volume.SetMute(muted ? 1 : 0, in eventContext);
            ThrowForHResult(result, AudioControlErrorCodes.OperationFailed);
        }

        public void Dispose()
        {
            IDisposable? currentVolume = Interlocked.Exchange(ref _volumeLease, null);
            IDisposable? currentDevice = Interlocked.Exchange(ref _deviceLease, null);
            IDisposable? currentEnumerator = Interlocked.Exchange(ref _enumeratorLease, null);
            currentVolume?.Dispose();
            currentDevice?.Dispose();
            currentEnumerator?.Dispose();
            _initialization.Dispose();
        }
    }
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("a95664d2-9614-4f35-a746-de8db63617e6")]
internal partial interface IMmDeviceEnumerator
{
    [PreserveSig]
    int EnumAudioEndpoints(int dataFlow, uint stateMask, out nint devices);

    [PreserveSig]
    int GetDefaultAudioEndpoint(int dataFlow, int role, out nint endpoint);

    [PreserveSig]
    int GetDevice(nint endpointId, out nint device);

    [PreserveSig]
    int RegisterEndpointNotificationCallback(nint callback);

    [PreserveSig]
    int UnregisterEndpointNotificationCallback(nint callback);
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("d666063f-1587-4e43-81f1-b948e807363f")]
internal partial interface IMmDevice
{
    [PreserveSig]
    int Activate(
        in Guid interfaceId,
        uint classContext,
        nint activationParameters,
        out nint instance);

    [PreserveSig]
    int OpenPropertyStore(uint accessMode, out nint propertyStore);

    [PreserveSig]
    int GetId(out nint endpointId);

    [PreserveSig]
    int GetState(out uint state);
}

[StructLayout(LayoutKind.Sequential)]
internal readonly struct AudioPropertyKey(Guid formatId, uint propertyId)
{
    public readonly Guid FormatId = formatId;
    public readonly uint PropertyId = propertyId;
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")]
internal partial interface IAudioPropertyStore
{
    [PreserveSig]
    int GetCount(out uint count);

    [PreserveSig]
    int GetAt(uint index, out AudioPropertyKey key);

    [PreserveSig]
    int GetValue(in AudioPropertyKey key, nint value);

    [PreserveSig]
    int SetValue(in AudioPropertyKey key, nint value);

    [PreserveSig]
    int Commit();
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("5cdf2c82-841e-4546-9722-0cf74078229a")]
internal partial interface IAudioEndpointVolume
{
    [PreserveSig]
    int RegisterControlChangeNotify(nint callback);

    [PreserveSig]
    int UnregisterControlChangeNotify(nint callback);

    [PreserveSig]
    int GetChannelCount(out uint channelCount);

    [PreserveSig]
    int SetMasterVolumeLevel(float levelDb, in Guid eventContext);

    [PreserveSig]
    int SetMasterVolumeLevelScalar(float scalar, in Guid eventContext);

    [PreserveSig]
    int GetMasterVolumeLevel(out float levelDb);

    [PreserveSig]
    int GetMasterVolumeLevelScalar(out float scalar);

    [PreserveSig]
    int SetChannelVolumeLevel(uint channel, float levelDb, in Guid eventContext);

    [PreserveSig]
    int SetChannelVolumeLevelScalar(uint channel, float scalar, in Guid eventContext);

    [PreserveSig]
    int GetChannelVolumeLevel(uint channel, out float levelDb);

    [PreserveSig]
    int GetChannelVolumeLevelScalar(uint channel, out float scalar);

    [PreserveSig]
    int SetMute(int muted, in Guid eventContext);

    [PreserveSig]
    int GetMute(out int muted);

    [PreserveSig]
    int GetVolumeStepInfo(out uint step, out uint stepCount);

    [PreserveSig]
    int VolumeStepUp(in Guid eventContext);

    [PreserveSig]
    int VolumeStepDown(in Guid eventContext);

    [PreserveSig]
    int QueryHardwareSupport(out uint hardwareSupportMask);

    [PreserveSig]
    int GetVolumeRange(out float minimumDb, out float maximumDb, out float incrementDb);
}

/// <summary>
/// AUDIO1787 «subí el volumen de spotify»: one application's audio sessions on the
/// default output endpoint, adjusted together and re-read (Core Audio session
/// volumes, the per-app sliders of the Windows volume mixer).
/// </summary>
internal sealed record ApplicationSessionAdjustment(
    string ProcessName,
    int SessionCount,
    int BaselineLevel,
    int Level,
    bool Muted,
    string EndpointId);

internal sealed partial class WindowsCoreAudioPlatform
{
    private static readonly Guid IidAudioSessionManager2 =
        new("77aa99a0-1bd6-484f-8bc7-2c654c9a9b6f");
    private static readonly Guid IidAudioSessionControl2 =
        new("bfb7ff88-7239-4fc9-8fa2-07c950be9c6d");
    private static readonly Guid IidSimpleAudioVolume =
        new("87ce5498-68d6-44e5-9215-6da47ef883d8");

    /// <summary>
    /// Adjust every audio session that belongs to the named application by a
    /// signed percentage delta from its own current level; null when the
    /// application has no audio session on the default output.
    /// </summary>
    /// <summary>
    /// Fase 8 (D18) audio.app.volume.set: every session of the application is set to
    /// one absolute level (0–100), paused sessions included; same post-read as the
    /// relative adjustment.
    /// </summary>
    internal static ApplicationSessionAdjustment? SetApplicationSessions(
        string applicationName,
        int level,
        Func<CancellationToken>? beforeEffect = null,
        CancellationToken cancellationToken = default) =>
        AdjustApplicationSessions(applicationName, 0, beforeEffect, Math.Clamp(level, 0, 100), cancellationToken);

    internal static ApplicationSessionAdjustment? AdjustApplicationSessions(
        string applicationName,
        int delta,
        Func<CancellationToken>? beforeEffect = null,
        CancellationToken cancellationToken = default) =>
        AdjustApplicationSessions(applicationName, delta, beforeEffect, null, cancellationToken);

    private static ApplicationSessionAdjustment? AdjustApplicationSessions(
        string applicationName,
        int delta,
        Func<CancellationToken>? beforeEffect,
        int? absoluteLevel,
        CancellationToken cancellationToken)
    {
        using ComInitialization initialization = InitializeCom();
        int result = CoCreateInstance(
            in ClsidMmDeviceEnumerator,
            0,
            ClsctxAll,
            in IidMmDeviceEnumerator,
            out nint enumeratorPointer);
        ReleaseOnFailure(result, enumeratorPointer);
        ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        IMmDeviceEnumerator enumerator = WrapUnique<IMmDeviceEnumerator>(
            enumeratorPointer,
            out IDisposable enumeratorLease);
        using (enumeratorLease)
        {
            result = enumerator.GetDefaultAudioEndpoint(
                EDataFlowRender,
                ERoleMultimedia,
                out nint devicePointer);
            ReleaseOnFailure(result, devicePointer);
            ThrowForHResult(result, AudioControlErrorCodes.NoDefaultOutput);
            IMmDevice device = WrapUnique<IMmDevice>(devicePointer, out IDisposable deviceLease);
            using (deviceLease)
            {
                string endpointId = ReadEndpointId(device);
                result = device.Activate(
                    in IidAudioSessionManager2,
                    ClsctxAll,
                    0,
                    out nint managerPointer);
                ReleaseOnFailure(result, managerPointer);
                ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
                IAudioSessionManager2 manager = WrapUnique<IAudioSessionManager2>(
                    managerPointer,
                    out IDisposable managerLease);
                using (managerLease)
                {
                    result = manager.GetSessionEnumerator(out nint sessionsPointer);
                    ReleaseOnFailure(result, sessionsPointer);
                    ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
                    IAudioSessionEnumerator sessions = WrapUnique<IAudioSessionEnumerator>(
                        sessionsPointer,
                        out IDisposable sessionsLease);
                    using (sessionsLease)
                    {
                        return AdjustMatchingSessions(
                            sessions,
                            applicationName,
                            delta,
                            endpointId,
                            beforeEffect,
                            absoluteLevel,
                            cancellationToken);
                    }
                }
            }
        }
    }

    private static ApplicationSessionAdjustment? AdjustMatchingSessions(
        IAudioSessionEnumerator sessions,
        string applicationName,
        int delta,
        string endpointId,
        Func<CancellationToken>? beforeEffect,
        int? absoluteLevel,
        CancellationToken cancellationToken)
    {
        int result = sessions.GetCount(out int count);
        ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        var volumes = new List<(ISimpleAudioVolume Volume, IDisposable Lease, string ProcessName)>();
        try
        {
            for (int index = 0; index < count; index++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                result = sessions.GetSession(index, out nint sessionPointer);
                ReleaseOnFailure(result, sessionPointer);
                if (result < 0 || sessionPointer == 0)
                {
                    continue;
                }

                nint controlPointer = 0;
                nint volumePointer = 0;
                try
                {
                    if (Marshal.QueryInterface(sessionPointer, in IidAudioSessionControl2, out controlPointer) < 0
                        || Marshal.QueryInterface(sessionPointer, in IidSimpleAudioVolume, out volumePointer) < 0)
                    {
                        continue;
                    }
                }
                finally
                {
                    ReleaseIUnknown(sessionPointer);
                }

                string? processName = null;
                IAudioSessionControl2 control = WrapUnique<IAudioSessionControl2>(
                    controlPointer,
                    out IDisposable controlLease);
                controlPointer = 0;
                using (controlLease)
                {
                    if (control.IsSystemSoundsSession() == 0)
                    {
                        // S_OK: the system sounds session belongs to no application.
                        ReleaseIUnknown(volumePointer);
                        continue;
                    }
                    if (control.GetProcessId(out uint processId) >= 0 && processId != 0)
                    {
                        processName = ProcessNameOf(processId);
                    }
                }

                if (processName is null || !ApplicationSessionMatches(processName, applicationName))
                {
                    ReleaseIUnknown(volumePointer);
                    continue;
                }

                ISimpleAudioVolume volume = WrapUnique<ISimpleAudioVolume>(
                    volumePointer,
                    out IDisposable volumeLease);
                volumes.Add((volume, volumeLease, processName));
            }

            if (volumes.Count == 0)
            {
                return null;
            }

            // The application's level is the level of its loudest session; every
            // session moves by the same delta so their relation is preserved.
            int baseline = 0;
            bool muted = true;
            foreach ((ISimpleAudioVolume volume, _, _) in volumes)
            {
                ThrowForHResult(volume.GetMasterVolume(out float scalar), AudioControlErrorCodes.EndpointUnavailable);
                ThrowForHResult(volume.GetMute(out int sessionMuted), AudioControlErrorCodes.EndpointUnavailable);
                baseline = Math.Max(baseline, Percent(scalar));
                muted &= sessionMuted != 0;
            }

            beforeEffect?.Invoke().ThrowIfCancellationRequested();
            foreach ((ISimpleAudioVolume volume, _, _) in volumes)
            {
                ThrowForHResult(volume.GetMasterVolume(out float scalar), AudioControlErrorCodes.EndpointUnavailable);
                int requested = absoluteLevel ?? Math.Clamp(Percent(scalar) + delta, 0, 100);
                Guid context = Guid.NewGuid();
                ThrowForHResult(volume.SetMasterVolume(requested / 100f, in context), AudioControlErrorCodes.EndpointUnavailable);
            }

            int level = 0;
            bool mutedAfter = true;
            foreach ((ISimpleAudioVolume volume, _, _) in volumes)
            {
                ThrowForHResult(volume.GetMasterVolume(out float scalar), AudioControlErrorCodes.EndpointUnavailable);
                ThrowForHResult(volume.GetMute(out int sessionMuted), AudioControlErrorCodes.EndpointUnavailable);
                level = Math.Max(level, Percent(scalar));
                mutedAfter &= sessionMuted != 0;
            }

            return new ApplicationSessionAdjustment(
                volumes[0].ProcessName,
                volumes.Count,
                baseline,
                level,
                mutedAfter && muted,
                endpointId);
        }
        finally
        {
            foreach ((_, IDisposable lease, _) in volumes)
            {
                lease.Dispose();
            }
        }
    }

    private static string? ProcessNameOf(uint processId)
    {
        try
        {
            using Process process = Process.GetProcessById(checked((int)processId));
            return process.ProcessName;
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// «Spotify» ↔ spotify.exe, «Google Chrome» ↔ chrome.exe, «Opera GX» ↔ opera.exe:
    /// a folded token of the application's display name (three letters or more)
    /// equals the process name or one starts with the other.
    /// </summary>
    internal static bool ApplicationSessionMatches(string processName, string applicationName)
    {
        string process = FoldToken(processName);
        if (process.Length == 0)
        {
            return false;
        }
        foreach (string raw in applicationName.Split(
            [' ', '-', '_', '.', ',', '(', ')'],
            StringSplitOptions.RemoveEmptyEntries))
        {
            string token = FoldToken(raw);
            if (token.Length < 3)
            {
                continue;
            }
            if (token == process
                || process.StartsWith(token, StringComparison.Ordinal)
                || token.StartsWith(process, StringComparison.Ordinal))
            {
                return true;
            }
        }
        return false;
    }

    private static string FoldToken(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }
            if (char.IsLetterOrDigit(character))
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }
        return builder.ToString();
    }

    private static int Percent(float scalar) =>
        Math.Clamp((int)Math.Round(scalar * 100f, MidpointRounding.AwayFromZero), 0, 100);
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("77aa99a0-1bd6-484f-8bc7-2c654c9a9b6f")]
internal partial interface IAudioSessionManager2
{
    [PreserveSig]
    int GetAudioSessionControl(nint sessionGuid, uint streamFlags, out nint sessionControl);

    [PreserveSig]
    int GetSimpleAudioVolume(nint sessionGuid, uint streamFlags, out nint audioVolume);

    [PreserveSig]
    int GetSessionEnumerator(out nint sessionEnumerator);

    [PreserveSig]
    int RegisterSessionNotification(nint sessionNotification);

    [PreserveSig]
    int UnregisterSessionNotification(nint sessionNotification);

    [PreserveSig]
    int RegisterDuckNotification(nint sessionId, nint duckNotification);

    [PreserveSig]
    int UnregisterDuckNotification(nint duckNotification);
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("e2f5bb11-0570-40ca-acdd-3aa01277dee8")]
internal partial interface IAudioSessionEnumerator
{
    [PreserveSig]
    int GetCount(out int sessionCount);

    [PreserveSig]
    int GetSession(int sessionIndex, out nint session);
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("bfb7ff88-7239-4fc9-8fa2-07c950be9c6d")]
internal partial interface IAudioSessionControl2
{
    [PreserveSig]
    int GetState(out int state);

    [PreserveSig]
    int GetDisplayName(out nint displayName);

    [PreserveSig]
    int SetDisplayName(nint displayName, nint eventContext);

    [PreserveSig]
    int GetIconPath(out nint iconPath);

    [PreserveSig]
    int SetIconPath(nint iconPath, nint eventContext);

    [PreserveSig]
    int GetGroupingParam(out Guid groupingParam);

    [PreserveSig]
    int SetGroupingParam(nint groupingParam, nint eventContext);

    [PreserveSig]
    int RegisterAudioSessionNotification(nint notification);

    [PreserveSig]
    int UnregisterAudioSessionNotification(nint notification);

    [PreserveSig]
    int GetSessionIdentifier(out nint sessionIdentifier);

    [PreserveSig]
    int GetSessionInstanceIdentifier(out nint sessionInstanceIdentifier);

    [PreserveSig]
    int GetProcessId(out uint processId);

    [PreserveSig]
    int IsSystemSoundsSession();

    [PreserveSig]
    int SetDuckingPreference(int optOut);
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("87ce5498-68d6-44e5-9215-6da47ef883d8")]
internal partial interface ISimpleAudioVolume
{
    [PreserveSig]
    int SetMasterVolume(float level, in Guid eventContext);

    [PreserveSig]
    int GetMasterVolume(out float level);

    [PreserveSig]
    int SetMute(int muted, in Guid eventContext);

    [PreserveSig]
    int GetMute(out int muted);
}
