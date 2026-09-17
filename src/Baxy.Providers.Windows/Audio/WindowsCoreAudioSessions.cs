using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.Marshalling;
using System.Text;

namespace Baxy.Providers.Windows.Audio;

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
    internal static ApplicationSessionAdjustment? AdjustApplicationSessions(
        string applicationName,
        int delta,
        Func<CancellationToken>? beforeEffect = null,
        CancellationToken cancellationToken = default)
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
                int requested = Math.Clamp(Percent(scalar) + delta, 0, 100);
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
