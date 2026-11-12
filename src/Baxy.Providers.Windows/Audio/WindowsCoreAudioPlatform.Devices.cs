namespace Baxy.Providers.Windows.Audio;

/// <summary>
/// An active audio endpoint as Windows shows it: its private id, its name, whether it is the default for multimedia (what
/// plays) and whether it is the default for the console role too (the Sound panel's «Set Default» sets both).
/// </summary>
internal sealed record AudioDevice(string Id, string Name, bool Default, bool ConsoleDefault);

/// <summary>
/// RUT2: the active endpoints of one direction and the default one, and setting the default (the seam the tests of
/// WindowsAudioDeviceAdapter replace, so no test changes the PC's sound).
/// </summary>
internal interface IAudioDevicePlatform
{
    /// <summary>The active endpoints (DEVICE_STATE_ACTIVE) of the output, or of the input when capture is true.</summary>
    IReadOnlyList<AudioDevice> Active(bool capture);

    /// <summary>Makes the endpoint the default for the console and multimedia roles, as the Sound panel's «Set Default».</summary>
    void SetDefault(string endpointId);
}

internal sealed class WindowsAudioDevicePlatform : IAudioDevicePlatform
{
    public IReadOnlyList<AudioDevice> Active(bool capture) => WindowsCoreAudioPlatform.ActiveDevices(capture);

    public void SetDefault(string endpointId) => WindowsCoreAudioPlatform.SetDefaultDevice(endpointId);
}

internal sealed partial class WindowsCoreAudioPlatform
{
    private const uint DeviceStateActive = 0x1;
    private const int ERoleConsole = 0;

    // RUT2: Windows has no documented call that sets the default endpoint. The Sound panel (mmsys.cpl) uses the
    // PolicyConfig client, an undocumented COM class whose IPolicyConfig interface has kept this id and vtable from
    // Windows 7 to Windows 11; EarTrumpet (Interop/MMDeviceAPI/IPolicyConfig.cs: «Win7-Win8, W10_RS1-Present»),
    // SoundSwitch and AudioDeviceCmdlets call SetDefaultEndpoint through it. A failure is a failed receipt, never «done».
    private static readonly Guid ClsidPolicyConfigClient = new("870af99c-171d-4f9e-af0d-e63df40c2bc9");
    private static readonly Guid IidPolicyConfig = new("f8679f50-850a-41cf-9c72-430f290290c8");

    // IUnknown's three, eight unused (formats, periods, share mode), GetPropertyValue, SetPropertyValue, then this one.
    private const int SetDefaultEndpointSlot = 13;
    private const int CollectionGetCountSlot = 3;
    private const int CollectionItemSlot = 4;

    internal static IReadOnlyList<AudioDevice> ActiveDevices(bool capture)
    {
        int flow = capture ? EDataFlowCapture : EDataFlowRender;
        using ComInitialization initialization = InitializeCom();
        int result = CoCreateInstance(
            in ClsidMmDeviceEnumerator,
            0,
            ClsctxAll,
            in IidMmDeviceEnumerator,
            out nint enumeratorPointer);
        ReleaseOnFailure(result, enumeratorPointer);
        ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        IMmDeviceEnumerator enumerator = WrapUnique<IMmDeviceEnumerator>(enumeratorPointer, out IDisposable enumeratorLease);
        using (enumeratorLease)
        {
            string? defaultId = DefaultId(enumerator, flow, ERoleMultimedia);
            string? consoleId = DefaultId(enumerator, flow, ERoleConsole);
            int result2 = enumerator.EnumAudioEndpoints(flow, DeviceStateActive, out nint collection);
            ReleaseOnFailure(result2, collection);
            ThrowForHResult(result2, AudioControlErrorCodes.EndpointUnavailable);
            try
            {
                var devices = new List<AudioDevice>();
                uint count = CollectionCount(collection);
                for (uint index = 0; index < count && index < 64; index++)
                {
                    // Revisión ciega RUT2 (7): a device that goes away between the list and its read is left out, not
                    // the whole list.
                    try
                    {
                        nint item = CollectionItem(collection, index);
                        IMmDevice device = WrapUnique<IMmDevice>(item, out IDisposable itemLease);
                        using (itemLease)
                        {
                            string id = ReadEndpointId(device);
                            string name = ReadEndpointDisplayName(device) ?? string.Empty;
                            devices.Add(new AudioDevice(
                                id,
                                name,
                                string.Equals(id, defaultId, StringComparison.Ordinal),
                                string.Equals(id, consoleId, StringComparison.Ordinal)));
                        }
                    }
                    catch (AudioPlatformException)
                    {
                    }
                }

                return devices;
            }
            finally
            {
                ReleaseIUnknown(collection);
            }
        }
    }

    private static string? DefaultId(IMmDeviceEnumerator enumerator, int flow, int role)
    {
        int result = enumerator.GetDefaultAudioEndpoint(flow, role, out nint pointer);
        ReleaseOnFailure(result, pointer);
        if (result == ENotFound)
        {
            return null;
        }

        ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        IMmDevice device = WrapUnique<IMmDevice>(pointer, out IDisposable lease);
        using (lease)
        {
            return ReadEndpointId(device);
        }
    }

    internal static unsafe void SetDefaultDevice(string endpointId)
    {
        using ComInitialization initialization = InitializeCom();
        int result = CoCreateInstance(in ClsidPolicyConfigClient, 0, ClsctxAll, in IidPolicyConfig, out nint policy);
        ReleaseOnFailure(result, policy);
        ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        try
        {
            nint slot = *((nint*)*(nint*)policy + SetDefaultEndpointSlot);
            var setDefault = (delegate* unmanaged[Stdcall]<nint, char*, int, int>)slot;
            fixed (char* id = endpointId)
            {
                ThrowForHResult(setDefault(policy, id, ERoleConsole), AudioControlErrorCodes.EndpointUnavailable);
                ThrowForHResult(setDefault(policy, id, ERoleMultimedia), AudioControlErrorCodes.EndpointUnavailable);
            }
        }
        finally
        {
            ReleaseIUnknown(policy);
        }
    }

    private static unsafe uint CollectionCount(nint collection)
    {
        var getCount = (delegate* unmanaged[Stdcall]<nint, uint*, int>)*((nint*)*(nint*)collection + CollectionGetCountSlot);
        uint count;
        ThrowForHResult(getCount(collection, &count), AudioControlErrorCodes.EndpointUnavailable);
        return count;
    }

    private static unsafe nint CollectionItem(nint collection, uint index)
    {
        var item = (delegate* unmanaged[Stdcall]<nint, uint, nint*, int>)*((nint*)*(nint*)collection + CollectionItemSlot);
        nint device;
        int result = item(collection, index, &device);
        ReleaseOnFailure(result, device);
        ThrowForHResult(result, AudioControlErrorCodes.EndpointUnavailable);
        return device;
    }
}
