using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// cu-v3-archivo-empaquetado (live v3-15, v3-17, v3-18) on the real desktop, by the product's own way (file.open with
/// an application, WindowsFileToolsAdapter): prueba.png opens in Fotos and notas.txt in Bloc de notas, both packaged,
/// the window that shows each names its file, and the window in front before is in front after. The counter-case: a
/// .txt never goes to an interpreter of the Start catalog. Never runs in a suite: Explicit and
/// BAXY_CU_ARCHIVO_EMPAQUETADO_LIVE=1, only with the desktop turn (scripts/cu_live/turno.sh); the windows it opens close
/// by their exact process id. The files are those of D:\Perfil\Documentos\baxy-prueba-v3 (the live batch's).
/// Measured 2026-10-08: all pass one by one; run together, Bloc de notas after Fotos kept the front (Windows refused the
/// hand-back of a second opening in one process) until the right was won by a bid (ForegroundRight,
/// cu-v3-foco-segunda): both pass run together.
/// </summary>
[TestFixture]
[Explicit("Opens Fotos and Bloc de notas on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class FileOpenPackagedLiveDesktopCheck
{
    [TestCase("Fotos", "prueba.png")]
    [TestCase("Bloc de notas", "notas.txt")]
    public async Task APackagedApplicationOpensTheFileBehindThePerson(string application, string file)
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_ARCHIVO_EMPAQUETADO_LIVE") != "1")
            Assert.Ignore("BAXY_CU_ARCHIVO_EMPAQUETADO_LIVE=1 is needed to touch the desktop.");
        nint front = GetForegroundWindow();
        var watch = Stopwatch.StartNew();
        ExternalCapabilityReceipt receipt = await new WindowsFileToolsAdapter().InvokeAsync("file.open",
            JsonSerializer.SerializeToElement(new { folder = "documents", name = "baxy-prueba-v3\\" + file, application }),
            CancellationToken.None);
        long elapsed = watch.ElapsedMilliseconds;
        int processId = receipt.Result is { } result && result.TryGetProperty("processId", out JsonElement id) ? id.GetInt32() : 0;
        // The front, read every 100 ms for 4 s (past the provider's front guard), said as it changes.
        var fronts = new List<string>();
        nint after = 0;
        for (int look = 0; look < 40; look++)
        {
            nint now = GetForegroundWindow();
            if (now != after)
            {
                _ = GetWindowThreadProcessId(now, out uint owner);
                fronts.Add($"{watch.ElapsedMilliseconds}ms:{now}/{owner}");
                after = now;
            }
            await Task.Delay(100);
        }
        TestContext.Out.WriteLine($"{application} {file}: verified={receipt.Verified} error={receipt.ErrorCode} pid={processId} ms={elapsed} front {front} then {string.Join(" ", fronts)}");
        try
        {
            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.Null);
                Assert.That(receipt.Verified, Is.True);
                Assert.That(processId, Is.Positive);
                Assert.That(after, Is.EqualTo(front), "the person's window keeps the front");
                // cu-v3-foco-segunda: a Windows activation is said with whether its hand-back held.
                if (receipt.Result is { } said && said.TryGetProperty("windowsActivation", out _))
                    Assert.That(said.GetProperty("frontRestored").GetBoolean(), Is.True, "the receipt says the front went back");
            });
        }
        finally
        {
            if (processId > 0)
            {
                try
                {
                    using Process opened = Process.GetProcessById(processId);
                    opened.Kill();
                }
                catch (ArgumentException)
                {
                }
            }
        }
    }

    // The interpreters of this PC's Start catalog, a desktop one and a packaged one: Windows lists neither for .txt.
    [TestCase("Python 3.12 (64-bit)")]
    [TestCase("Python 3.13")]
    public async Task AnInterpreterNeverGetsTheTextFile(string interpreter)
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_ARCHIVO_EMPAQUETADO_LIVE") != "1")
            Assert.Ignore("BAXY_CU_ARCHIVO_EMPAQUETADO_LIVE=1 is needed to touch the desktop.");
        ExternalCapabilityReceipt receipt = await new WindowsFileToolsAdapter().InvokeAsync("file.open",
            JsonSerializer.SerializeToElement(new { folder = "documents", name = "baxy-prueba-v3\\notas.txt", application = interpreter }),
            CancellationToken.None);
        TestContext.Out.WriteLine($"{interpreter} notas.txt: verified={receipt.Verified} error={receipt.ErrorCode}");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("app_file_not_accepted"), "not listed for .txt: never handed");
        });
    }

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint processId);
}
