namespace Baxy.Providers.Windows.External;

/// <summary>
/// The mark every synthetic key and mouse event of BAXY carries in its <c>dwExtraInfo</c> («BAXY» in ASCII). Windows
/// hands that value to whoever watches the input (Raw Input, low-level hooks), so the pause detector tells BAXY's own
/// input from the person's, and the live harness counts what BAXY did to the simulated user's window. Every
/// <c>SendInput</c>, <c>mouse_event</c> and <c>keybd_event</c> under <c>src/</c> sends it; the PowerShell helpers
/// cannot reference this class and write the same literal (a census test keeps them in step).
/// </summary>
internal static class BaxyInputMark
{
    internal const uint Value = 0x42415859;

    /// <summary>Whether an event's extra information is BAXY's mark.</summary>
    internal static bool Carries(nuint extraInformation) => extraInformation == Value;
}
