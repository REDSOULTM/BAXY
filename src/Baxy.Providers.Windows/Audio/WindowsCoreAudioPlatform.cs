using System.Runtime.InteropServices;
using System.Runtime.InteropServices.Marshalling;
using System.Security.Cryptography;
using System.Text;

namespace Baxy.Providers.Windows.Audio;

internal interface IWindowsAudioEndpoint : IDisposable
{
    string EndpointId { get; }

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
