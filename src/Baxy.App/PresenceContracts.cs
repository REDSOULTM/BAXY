using System.Text.Json.Serialization;

namespace Baxy.App;

internal static class PresenceLimits
{
    internal const string WindowClassName = "BAXY.Presence.Tray";
    internal const string WindowTitle = "BAXY.Presence";
    internal const long VramCeilingBytes = 4L * 1024 * 1024 * 1024;
    internal const string AutostartValueName = "BAXY";
    internal const string FromWindowsStartArgument = "--from-windows-start";
    internal const string TrayArgument = "--tray";
    internal const string StatusSchema = "baxy-presence-status-v1";
    internal const string SampleSchema = "baxy-presence-sample-v1";
}

internal sealed record PresenceProcessSample(
    int ProcessId,
    string Name,
    string Path,
    long WorkingSetBytes,
    long HandleCount,
    double CpuSeconds,
    long VramBytes);

internal sealed record PresenceIdleSnapshot(
    DateTimeOffset Utc,
    bool Ready,
    bool InputEnabled,
    bool Listening,
    DateTimeOffset? FirstWakeUtc,
    string Terminal,
    IReadOnlyList<PresenceProcessSample> Processes);

internal sealed record PresenceStatusDocument(
    [property: JsonPropertyName("schema")] string Schema,
    [property: JsonPropertyName("utc")] string Utc,
    [property: JsonPropertyName("ready")] bool Ready,
    [property: JsonPropertyName("input_enabled")] bool InputEnabled,
    [property: JsonPropertyName("listening")] bool Listening,
    [property: JsonPropertyName("wake_listening")] bool WakeListening,
    [property: JsonPropertyName("mind_ready")] bool MindReady,
    [property: JsonPropertyName("mic_available")] bool MicAvailable,
    [property: JsonPropertyName("first_wake_utc")] string? FirstWakeUtc,
    [property: JsonPropertyName("terminal")] string Terminal,
    [property: JsonPropertyName("tray_hwnd")] long TrayHwnd,
    [property: JsonPropertyName("tray_registered")] bool TrayRegistered,
    [property: JsonPropertyName("autostart_registered")] bool AutostartRegistered,
    [property: JsonPropertyName("autostart_command")] string? AutostartCommand,
    [property: JsonPropertyName("processes")] IReadOnlyList<PresenceProcessSample> Processes);

internal interface IWindowsRunKey
{
    string? Read(string name);

    void Write(string name, string value);

    void Delete(string name);
}

internal interface ITrayIconShell
{
    bool Add(nint hwnd, uint callbackMessage, nint icon, string tip);

    bool Delete(nint hwnd);
}

internal interface IPresenceProcessReader
{
    IReadOnlyList<PresenceProcessSample> ReadOwned();
}

internal interface IPresenceClock
{
    DateTimeOffset UtcNow { get; }
}

internal sealed class SystemPresenceClock : IPresenceClock
{
    public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;
}
