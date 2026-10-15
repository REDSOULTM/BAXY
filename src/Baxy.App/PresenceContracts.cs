namespace Baxy.App;

internal static class PresenceLimits
{
    internal const string WindowClassName = "BAXY.Presence.Tray";
    internal const string WindowTitle = "BAXY.Presence";
    internal const string AutostartValueName = "BAXY";
    internal const string FromWindowsStartArgument = "--from-windows-start";
    internal const string TrayArgument = "--tray";
}

internal interface IWindowsRunKey
{
    string? Read(string name);

    void Write(string name, string value);

    void Delete(string name);
}
