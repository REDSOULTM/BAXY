using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

public sealed class VirtualDesktopsTests
{
    // Ronda final 12: the shell answers for a window on screen (the one in front, on the current desktop): it is not on
    // another desktop.
    [Test]
    [Explicit("Physical read-only validation against the shell's virtual desktop manager.")]
    public void TheWindowInFrontIsOnTheCurrentDesktop()
    {
        nint front = GetForegroundWindow();
        bool?[] answers = VirtualDesktops.OnAnotherDesktop([front]);

        TestContext.Out.WriteLine($"window in front answered: {answers[0]?.ToString() ?? "null"}");
        Assert.That(answers[0], Is.False, "the shell placed the window in front on this desktop");
    }

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();
}
