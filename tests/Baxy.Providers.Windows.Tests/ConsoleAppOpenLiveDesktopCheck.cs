using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// FT/proveedores goal (E5) on the real desktop: app.open of the command prompt, which Windows 11 shows in Windows
/// Terminal. Before the fix every check spent its 30 s and said verification_failed with the window on screen; now the
/// Terminal window that owns the program's pseudo-console window verifies it. Never runs in a suite: Explicit and
/// BAXY_CONSOLE_OPEN_LIVE=1, only while no one uses the desktop; the program it opens is closed by its exact process id.
/// </summary>
[TestFixture]
[Explicit("Opens the command prompt on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class ConsoleAppOpenLiveDesktopCheck
{
    [Test]
    public async Task TheCommandPromptShownByTheTerminalIsVerified()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CONSOLE_OPEN_LIVE") != "1")
            Assert.Ignore("BAXY_CONSOLE_OPEN_LIVE=1 is needed to touch the desktop.");
        string application = Environment.GetEnvironmentVariable("BAXY_CONSOLE_OPEN_APP") ?? "Símbolo del sistema";
        var provider = new WindowsInstalledApplicationOpenProvider();
        var watch = Stopwatch.StartNew();
        ApplicationOpenResult result = await provider.OpenAsync(
            new ApplicationOpenRequest(application, "consola_" + Guid.NewGuid().ToString("N")), CancellationToken.None);
        try
        {
            string windowClass = result.WindowHandle is long window ? ClassOf((nint)window) : string.Empty;
            TestContext.Out.WriteLine($"{application}: verified={result.Verified} error={result.ErrorCode} "
                + $"pid={result.ProcessId} window={result.WindowHandle} class={windowClass} ms={watch.ElapsedMilliseconds}");
            Assert.Multiple(() =>
            {
                Assert.That(result.Verified, Is.True, result.ErrorCode);
                Assert.That(windowClass, Is.AnyOf("CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass"));
                Assert.That(watch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(15)));
            });
        }
        finally
        {
            if (result.ProcessId is int id and > 0)
            {
                try
                {
                    using Process process = Process.GetProcessById(id);
                    process.Kill();
                }
                catch (ArgumentException)
                {
                }
            }
        }
    }

    private static string ClassOf(nint window)
    {
        var name = new char[256];
        int length = GetClassName(window, name, name.Length);
        return length > 0 ? new string(name, 0, length) : string.Empty;
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(nint window, [Out] char[] name, int capacity);
}
