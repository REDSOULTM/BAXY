using System.Diagnostics;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// I13 (R5's review of I12, R5-1), on the real desktop, opt-in only (Explicit and BAXY_FRONT_LIVE_CHECK=1): «abre la
/// calculadora», then «escribe 2+2», was held, as a window no result showed. The window of a packaged app is a frame of
/// ApplicationFrameHost, the host every such app shares; app_open, a look and a typing's sentTo name it by the app it
/// hosts (CalculatorApp), and the App read the window in front by the frame's own process. The Calculator of the test's
/// own (none may be running before) is named as the receipts name it; its process is closed by its id.
/// </summary>
[TestFixture]
[Explicit("Opens a Calculator window of its own on the person's desktop.")]
public sealed class PersonFrontFrameLiveCheck
{
    [Test]
    public async Task TheWindowOfAPackagedAppIsNamedByTheAppItHostsAsEveryReceiptNamesIt()
    {
        if (Environment.GetEnvironmentVariable("BAXY_FRONT_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_FRONT_LIVE_CHECK=1 is needed to touch the desktop.");
        if (Process.GetProcessesByName("CalculatorApp").Length > 0)
            Assert.Ignore("A Calculator is already open: it may be the person's.");
        HashSet<nint> before = [.. HeartbeatMoment.OtherWindowHandles()];
        try
        {
            using (Process.Start(new ProcessStartInfo("calc.exe") { UseShellExecute = true }))
            {
            }

            nint frame = 0;
            for (int attempt = 0; attempt < 40 && frame == 0; attempt++)
            {
                await Task.Delay(500);
                frame = HeartbeatMoment.OtherWindowHandles().FirstOrDefault(handle => !before.Contains(handle)
                    && HeartbeatMoment.ProcessOf(handle) == "ApplicationFrameHost"
                    && Process.GetProcessesByName("CalculatorApp").Length > 0);
            }

            Assert.That(frame, Is.Not.EqualTo((nint)0), "no frame of the Calculator appeared");
            await Task.Delay(1000);
            Assert.That(HeartbeatMoment.Named(frame).Process, Is.EqualTo("CalculatorApp"));
        }
        finally
        {
            foreach (Process opened in Process.GetProcessesByName("CalculatorApp"))
            {
                using (opened)
                {
                    opened.Kill();
                }
            }
        }
    }
}
