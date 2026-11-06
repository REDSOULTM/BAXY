using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 65 (cosecha F2, uso real 03-11): a request for the newest mail of one sender in a webmail open in a tab of
/// the person's browser. The route the App's result now leads with (NetworkEgress.Elsewhere), measured with the generic
/// tools on a browser of the test's own (a temporary profile, two local pages with invented content: a webmail inbox in
/// a tab that is not the one shown, and a notes page in front): input.visible.controls of the window shows the tab, a
/// click on it shows the inbox, a second look shows the mail row and a click on it opens that mail, each click verified
/// by the page it showed. Nothing of the webmail is the product's: it is a page any browser shows. Never runs in a suite:
/// Explicit and BAXY_TAB_LIVE_CHECK=1. It acts only on the window it opened, checked by its process and title, and closes
/// every process of its own by id.
/// </summary>
[TestFixture]
[Explicit("Opens a browser window on the person's desktop and clicks in it.")]
[Category("LiveDesktop")]
public sealed class WebmailTabLiveDesktopCheck
{
    private const string Notes = "Proyecto Faro - Notas";
    private const string Inbox = "Recibidos (2) - ana@ejemplo.test - Gmail";
    private const string Subject = "[faro] Nuevo issue 12";

    [TestCase(@"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")]
    [TestCase(@"C:\Program Files\Google\Chrome\Application\chrome.exe")]
    public async Task TheMailInATabNotShownIsReachedByTheGenericLookAndClicks(string browser)
    {
        if (Environment.GetEnvironmentVariable("BAXY_TAB_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_TAB_LIVE_CHECK=1 is needed to touch the desktop.");
        if (!File.Exists(browser))
            Assert.Ignore("No browser at " + browser);
        string folder = Path.Combine(Path.GetTempPath(), "baxy-pestana-" + Guid.NewGuid().ToString("N")[..8]);
        string profile = Path.Combine(folder, "perfil");
        Directory.CreateDirectory(profile);
        string inbox = Path.Combine(folder, "bandeja.html");
        string notes = Path.Combine(folder, "notas.html");
        await File.WriteAllTextAsync(inbox, InboxPage());
        await File.WriteAllTextAsync(notes,
            $"<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>{Notes}</title></head>"
            + "<body><h1>Notas</h1><p>Comprar pan.</p></body></html>");
        var before = Process.GetProcesses().Select(static process =>
        {
            using (process)
                return process.Id;
        }).ToHashSet();
        var own = new List<int>();
        try
        {
            // Both pages in one window: the first given is the one shown, the inbox beside it.
            own.Add(Start(browser, profile, [notes, inbox]));
            (nint window, uint drawn) = await OwnWindowAsync(before, Notes);
            own.Add(unchecked((int)drawn));
            TestContext.Out.WriteLine($"{Path.GetFileName(browser)}: ventana {window} «{Title(window)}»");
            Assert.That(window, Is.Not.EqualTo((nint)0), "the test's own browser window, the notes page in front");
            await Task.Delay(1500);

            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using var visible = new WindowsVisibleControlAdapter(uia) { PersonTouchOf = (_, _) => PersonTouch.None };
            // A browser names a page by one whole « - » segment of its title (VisibleControlSurface.PageNamesApplication).
            ExternalCapabilityReceipt look = await LookAsync(visible, window, "Proyecto Faro", Inbox);
            string? tab = visible.NamesSeen(window).FirstOrDefault(static name => name.StartsWith("Recibidos (2)", StringComparison.Ordinal));
            TestContext.Out.WriteLine($"{Path.GetFileName(browser)} mirada 1: error={look.ErrorCode} pestaña={tab} nombres="
                + string.Join(" | ", visible.NamesSeen(window).Take(40)));
            // Measured 03-11 on the development PC: Chrome showed UI Automation only its frame («Chrome Legacy Window»), no tab strip
            // nor page; what the look cannot read is not measured here.
            if (tab is null && visible.NamesSeen(window).Count <= 5)
                Assert.Inconclusive(Path.GetFileName(browser) + " shows UI Automation only its frame on this PC");
            Assert.That(tab, Is.Not.Null, "the look shows the inbox's tab");

            ExternalCapabilityReceipt toTab = await ClickAsync(visible, window, tab!);
            TestContext.Out.WriteLine($"clic pestaña: verified={toTab.Verified} error={toTab.ErrorCode} título={Title(window)}");
            Assert.That(await TitleAsync(window, "Recibidos (2) - "), Is.True, "the inbox is the tab shown");

            look = await LookAsync(visible, window, "Recibidos (2)", "Codeberg");
            string? row = visible.NamesSeen(window).FirstOrDefault(static name =>
                name.Contains("Codeberg", StringComparison.Ordinal) && name.Contains(Subject, StringComparison.Ordinal));
            TestContext.Out.WriteLine($"mirada 2: error={look.ErrorCode} fila={row}");
            Assert.That(row, Is.Not.Null, "the look shows the mail's row");

            ExternalCapabilityReceipt opened = await ClickAsync(visible, window, row!);
            bool shown = await TitleAsync(window, Subject + " - ");
            TestContext.Out.WriteLine($"clic correo: verified={opened.Verified} error={opened.ErrorCode} título={Title(window)}");
            Assert.Multiple(() =>
            {
                Assert.That(toTab.ErrorCode, Is.Null, "the click on the tab");
                Assert.That(toTab.Verified, Is.True);
                Assert.That(opened.ErrorCode, Is.Null, "the click on the mail");
                Assert.That(opened.Verified, Is.True);
                Assert.That(shown, Is.True, "the mail is open: " + Title(window));
            });
        }
        finally
        {
            foreach (int id in own.Where(id => id > 0 && !before.Contains(id)).Distinct())
            {
                try
                {
                    using Process process = Process.GetProcessById(id);
                    process.Kill(entireProcessTree: true);
                }
                catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
                    or System.ComponentModel.Win32Exception)
                {
                }
            }

            for (int attempt = 0; attempt < 10 && Directory.Exists(folder); attempt++)
            {
                try
                {
                    Directory.Delete(folder, recursive: true);
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    await Task.Delay(500);
                }
            }
        }
    }

    // A webmail inbox as such pages are: a grid of mails, each row the sender, the subject and the hour; a row pressed
    // shows its mail and the page's title becomes its subject.
    private static string InboxPage() => $$"""
        <!doctype html>
        <html lang="es"><head><meta charset="utf-8"><title>{{Inbox}}</title>
        <style>tr{cursor:pointer}td{padding:4px 12px}</style></head>
        <body>
        <main id="vista">
        <table role="grid" aria-label="Recibidos"><tbody>
        <tr role="row" tabindex="0" onclick="abrir(0)"><td>Banco Austral</td><td>Estado de cuenta de octubre</td><td>11:02</td></tr>
        <tr role="row" tabindex="0" onclick="abrir(1)"><td>Codeberg</td><td>{{Subject}}</td><td>10:31</td></tr>
        </tbody></table>
        </main>
        <script>
        var correos=[['Banco Austral','Estado de cuenta de octubre'],['Codeberg','{{Subject}}']];
        function abrir(i){
          document.title=correos[i][1]+' - ana@ejemplo.test - Gmail';
          document.getElementById('vista').innerHTML='<h1>'+correos[i][1]+'</h1><p>De: '+correos[i][0]+'</p><p>Hola.</p>';
        }
        </script>
        </body></html>
        """;

    private static int Start(string browser, string profile, string[] pages)
    {
        var start = new ProcessStartInfo(browser)
        {
            // Without extensions: one installed for every profile opens a welcome tab of its own in front.
            ArgumentList =
            {
                "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                "--new-window",
            },
            UseShellExecute = false,
        };
        // Edge asks a new profile to sync in a dialog of its own; an InPrivate window does not.
        if (string.Equals(Path.GetFileName(browser), "msedge.exe", StringComparison.OrdinalIgnoreCase))
            start.ArgumentList.Add("--inprivate");
        if (Environment.GetEnvironmentVariable("BAXY_TAB_LIVE_ACCESSIBILITY") == "1")
            start.ArgumentList.Add("--force-renderer-accessibility");
        foreach (string page in pages)
            start.ArgumentList.Add(new Uri(page).AbsoluteUri);
        using Process? started = Process.Start(start);
        return started?.Id ?? 0;
    }

    private static async Task<ExternalCapabilityReceipt> LookAsync(
        WindowsVisibleControlAdapter visible, nint window, string application, string expected)
    {
        ExternalCapabilityReceipt look = default!;
        for (int attempt = 0; attempt < 10; attempt++)
        {
            // The first look of a just opened Chromium window may see no page yet (accessibility turns on with it).
            look = await visible.InvokeAsync(
                "input.visible.controls",
                JsonDocument.Parse(JsonSerializer.Serialize(new { application, includeText = false })).RootElement,
                CancellationToken.None);
            if (look.ErrorCode is null && visible.NamesSeen(window).Any(name => name.Contains(expected, StringComparison.Ordinal)))
                break;
            await Task.Delay(1000);
        }

        return look;
    }

    private static async Task<ExternalCapabilityReceipt> ClickAsync(WindowsVisibleControlAdapter visible, nint window, string label) =>
        await visible.InvokeAsync(
            "input.visible.click",
            JsonDocument.Parse(JsonSerializer.Serialize(new { label, window = (long)window })).RootElement,
            CancellationToken.None);

    private static string Title(nint window) => VisibleControlSurface.WindowTitle(window);

    private static async Task<bool> TitleAsync(nint window, string start)
    {
        for (int attempt = 0; attempt < 20; attempt++)
        {
            if (Title(window).StartsWith(start, StringComparison.Ordinal))
                return true;
            await Task.Delay(300);
        }

        return false;
    }

    private static async Task<(nint Window, uint Process)> OwnWindowAsync(HashSet<int> before, string start)
    {
        for (int attempt = 0; attempt < 60; attempt++)
        {
            nint chosen = 0;
            uint owner = 0;
            EnumWindows((window, ignored) =>
            {
                if (!IsWindowVisible(window) || !Title(window).StartsWith(start, StringComparison.Ordinal))
                    return true;
                _ = GetWindowThreadProcessId(window, out uint process);
                if (before.Contains(unchecked((int)process)))
                    return true;
                owner = process;
                chosen = window;
                return false;
            }, 0);
            if (chosen != 0)
                return (chosen, owner);
            await Task.Delay(500);
        }

        return (0, 0);
    }

    private delegate bool EnumWindowsProc(nint window, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumWindowsProc callback, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(nint window);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint process);
}
