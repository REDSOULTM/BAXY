namespace Baxy.App;

/// <summary>
/// Whether a use of the microphone that Windows records as started and never stopped is still going on (the heartbeat's
/// «llamada», <see cref="HeartbeatMoment"/>).
/// </summary>
internal static class MicrophoneUse
{
    /// <summary>
    /// Uso real 2026-10-21: «estás en una llamada» with no call. A program that ends without closing the microphone (a
    /// crash, an update that replaced its folder) leaves Windows' record started and never stopped: three old Discord
    /// folders and a game, months old, held it for ever. A use started before this boot cannot be going on, and a
    /// desktop program's use only while that executable runs (a packaged app's record names no executable).
    /// </summary>
    internal static bool StillHeld(long startedFileTime, long bootFileTime, string? desktopExecutable, Func<string, bool> running) =>
        startedFileTime >= bootFileTime && (desktopExecutable is null || running(desktopExecutable));
}
