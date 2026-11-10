using System.Runtime.InteropServices;
using System.Security;

namespace Baxy.Providers.Windows.Audio;

/// <summary>
/// W3 (R6-1): the applications whose own audio session is muted on the default output, for the whole PC's unmute to
/// say which stay silent (<see cref="WindowsCoreAudioPlatform.MutedApplicationSessions"/>); a read only. A list that
/// could not be read is no list.
/// </summary>
public static class ApplicationAudioMutes
{
    public static IReadOnlyList<string> Read()
    {
        try
        {
            return WindowsCoreAudioPlatform.MutedApplicationSessions();
        }
        catch (Exception exception) when (exception is AudioPlatformException or COMException
            or InvalidComObjectException or UnauthorizedAccessException or SecurityException)
        {
            return [];
        }
    }
}
