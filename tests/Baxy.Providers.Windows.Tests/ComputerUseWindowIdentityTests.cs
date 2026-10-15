using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Which window a computer-use mission takes for its application while the application's process is unknown
/// (safety review 2026-10-07): the executable first, else the application named in the title's last segment as
/// whole words; never an editor, a terminal, a console or BAXY that the request did not name. Pure rules; the last
/// test only reads the list of windows, nothing on the desktop is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseWindowIdentityTests
{
    [TestCase("SteamLocalAdapter.cs - BAXY Definitivo - Visual Studio Code", "Steam", false)]
    [TestCase("Steam - Bloc de notas", "Steam", false)]
    [TestCase("Steamworks", "Steam", false)]
    [TestCase("Steam", "Steam", true)]
    [TestCase("Ron92 - Discord", "Discord", true)]
    [TestCase("#general | BAXY - Discord", "Discord", true)]
    [TestCase("Nueva pestaña - Google Chrome", "Google Chrome", true)]
    [TestCase("Inicio - Personal - Microsoft​ Edge", "Microsoft Edge", true)]
    [TestCase("Calculadora", "Calculadora", true)]
    [TestCase("notas.txt - Bloc de notas", "Bloc de notas", true)]
    // r15b v3-47: a window that shares one word of the name («sistema») is another application's.
    [TestCase("Sistema y seguridad", "Información del sistema", false)]
    [TestCase("Información del sistema", "Información del sistema", true)]
    [TestCase("Sistema y seguridad", "Seguridad de Windows", false)]
    [TestCase("Documento1 - Word", "Microsoft Word", true)]
    // Revisión destino del pedido: titles that name the application in part, in another language or with a state.
    [TestCase("Reproductor de Windows Media", "Windows Media Player Legacy", true)]
    [TestCase("Riot Client", "Cliente de Riot", true)]
    [TestCase("Zoom Meeting", "Zoom Workplace", true)]
    [TestCase("Documento1 - Word (No responde)", "Microsoft Word", true)]
    [TestCase("Sin título - Bloc de notas (Not Responding)", "Bloc de notas", true)]
    [TestCase("Seguridad de Windows", "Windows Media Player Legacy", false)]
    [TestCase("Reproductor de Windows Media", "Seguridad de Windows", false)]
    [TestCase("Notas rápidas", "Bloc de notas", false)]
    public void TheTitleNamesTheApplicationOnlyInItsLastSegmentAsWholeWords(string title, string application, bool names)
    {
        Assert.That(VisibleControlSurface.TitleNamesApplication(title, application), Is.EqualTo(names));
    }

    [TestCase("Spotify", "Spotify", true)]
    [TestCase("chrome", "Google Chrome", true)]
    [TestCase("EpicGamesLauncher", "Epic Games Launcher", true)]
    [TestCase("steamwebhelper", "Steam", false)]
    [TestCase("Code", "Steam", false)]
    public void TheExecutableIsTheApplicationByItsNameOrADistinctiveWord(string process, string application, bool matches)
    {
        Assert.That(VisibleControlSurface.ProcessIsApplication(process, application), Is.EqualTo(matches));
    }

    // Goal v3, analysis r3a M5 (v3-49): a file manager whose title is the folder it shows is found by its executable's
    // own description, the whole name or the name followed by more words; a description that only shares a word with
    // the name never names it («panel de miniaturas» is no control panel), nor a generic word alone.
    [TestCase("7-Zip File Manager", "7-Zip File Manager", true)]
    [TestCase("7-Zip File Manager", "7-zip", true)]
    [TestCase("Mapa de caracteres", "mapa de caracteres", true)]
    [TestCase("Bloc de notas", "Bloc de notas", true)]
    [TestCase("Panel de control", "panel de miniaturas", false)]
    [TestCase("7-Zip File Manager", "7", false)]
    [TestCase("7-Zip File Manager", "zip", false)]
    [TestCase("Microsoft Edge", "Microsoft", false)]
    [TestCase("Steamworks Helper", "Steam", false)]
    [TestCase("", "Steam", false)]
    public void TheExecutablesDescriptionNamesTheApplicationWholeOrFollowedByMoreWords(
        string description, string application, bool names)
    {
        Assert.That(VisibleControlSurface.DescriptionNamesApplication(description, application), Is.EqualTo(names));
    }

    // Safety review 2026-10-07, measured on the owner's PC: a packaged chat application (WhatsApp.Root.exe, started by
    // a service host with no top-level window) draws its visible window «(5) WhatsApp» through msedgewebview2.exe,
    // whose description «Microsoft Edge WebView2» names «Microsoft Edge» as a string; Steam's titled window «Steam»
    // and its friends list belong to steamwebhelper.exe («Steam Client WebHelper», helpers nested under helpers),
    // started by steam.exe, which owns only hidden top-level windows. Process ids are the measured ones.
    private const uint Shell = 9000;
    private const uint Self = 9100;
    private static readonly Dictionary<uint, uint> MeasuredParents = new()
    {
        [1880] = 1724,   // svchost.exe <- services.exe
        [13884] = 1880,  // WhatsApp.Root.exe <- svchost.exe
        [11216] = 13884, // msedgewebview2.exe <- WhatsApp.Root.exe (owns «(5) WhatsApp»)
        [10448] = 11216, // msedgewebview2.exe <- msedgewebview2.exe
        [16488] = 13704, // steam.exe <- (a process that exited)
        [21792] = 16488, // steamwebhelper.exe <- steam.exe (owns «Steam» and the friends list)
        [13748] = 21792, // steamwebhelper.exe <- steamwebhelper.exe
        [7000] = Shell,  // 7zFM.exe <- the shell
        [7100] = Self,   // an application this product started
        [7200] = 7300,   // a process whose parent id now belongs to a newer process
        [7300] = Shell,
    };

    private static readonly Dictionary<uint, string> MeasuredExecutables = new()
    {
        [1724] = "services",
        [1880] = "svchost",
        [13884] = "WhatsApp.Root",
        [11216] = "msedgewebview2",
        [10448] = "msedgewebview2",
        [16488] = "steam",
        [21792] = "steamwebhelper",
        [13748] = "steamwebhelper",
        [7000] = "7zFM",
        [7100] = "notepad",
        [7200] = "mspaint",
        [7300] = "WhatsApp.Root",
        [Shell] = "explorer",
        [Self] = "Baxy",
    };

    private static readonly HashSet<uint> MeasuredWindowOwners = [13884, 11216, 16488, 21792, 7000, 7300, Shell, Self];

    private static bool Launched(uint process) =>
        VisibleControlSurface.LaunchedByAnotherApplication(
            process,
            MeasuredParents,
            id => MeasuredExecutables.TryGetValue(id, out string? name) ? name : string.Empty,
            (first, second) => !(first == 7300 && second == 7200),
            MeasuredWindowOwners.Contains,
            Shell,
            Self);

    [TestCase(11216u, true)]
    [TestCase(10448u, true)]
    [TestCase(21792u, true)]
    [TestCase(13748u, true)]
    [TestCase(13884u, false)]
    [TestCase(16488u, false)]
    [TestCase(7000u, false)]
    [TestCase(7100u, false)]
    [TestCase(7200u, false)]
    [TestCase(0u, false)]
    public void ARuntimeAnApplicationStartedIsLaunchedByAnotherApplication(uint process, bool launched)
    {
        Assert.That(Launched(process), Is.EqualTo(launched));
    }

    // The embedded browser's window never resolves for the browser by its description, nor wins over the browser's
    // own window titled «… - Microsoft Edge» whose description also names it.
    [Test]
    public void AnEmbeddedBrowsersWindowIsNeverTheBrowser()
    {
        bool runtimeNamed = VisibleControlSurface.DescriptionNamesApplication("Microsoft Edge WebView2", "Microsoft Edge")
            && !Launched(11216);
        nint chat = 0x1111;
        nint browser = 0x2222;
        Assert.Multiple(() =>
        {
            Assert.That(runtimeNamed, Is.False);
            Assert.That(VisibleControlSurface.ProcessIsApplication("msedgewebview2", "Microsoft Edge"), Is.False);
            Assert.That(VisibleControlSurface.TitleNamesApplication("(5) WhatsApp", "Microsoft Edge"), Is.False);
            // Browser closed: only the chat window is there, and nothing names the browser.
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, runtimeNamed ? chat : 0, 0), Is.EqualTo((nint)0));
            // Chat window above the browser: the browser's window, named by its description and its title.
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, browser, runtimeNamed ? chat : browser, browser),
                Is.EqualTo(browser));
        });
    }

    // Review of cu-v3-elevacion (finding 1), twins of r9 v3-65 and v3-20..22/72. A raised window (topmost first in each
    // list) whose program opens again with the person's rights gives way to a readable copy of that same executable;
    // never to another program's window that only names the application (a folder «Administrador de tareas» or
    // «Servicios»), and never when the program raises itself (the Task Manager): the elevated limit stands.
    private sealed record FakeWindow(nint Handle, int ProcessId, string Executable, bool Raised, bool ReopensUnraised);

    private static nint Prefer(nint chosen, params FakeWindow[] windows)
    {
        FakeWindow Of(int processId) => windows.First(window => window.ProcessId == processId);
        return VisibleControlSurface.PreferReadableCopy(
            chosen,
            handle => windows.First(window => window.Handle == handle).ProcessId,
            processId => Of(processId).Raised,
            processId => Of(processId).ReopensUnraised,
            processId => Of(processId).Executable,
            accept => windows.FirstOrDefault(window => accept(window.ProcessId))?.Handle ?? 0);
    }

    [Test]
    public void ARaisedConsoleGivesWayOnlyToAReadableCopyOfItsOwnProgram()
    {
        const string console = @"C:\Windows\System32\mmc.exe";
        const string explorer = @"C:\Windows\explorer.exe";
        var raisedServices = new FakeWindow(0x101, 41, console, Raised: true, ReopensUnraised: true);
        var folderServices = new FakeWindow(0x102, 42, explorer, Raised: false, ReopensUnraised: false);
        var readableServices = new FakeWindow(0x103, 43, console, Raised: false, ReopensUnraised: false);
        var raisedTaskManager = new FakeWindow(0x201, 51, @"C:\Windows\System32\Taskmgr.exe", Raised: true, ReopensUnraised: false);
        var folderTaskManager = new FakeWindow(0x202, 52, explorer, Raised: false, ReopensUnraised: false);
        var unreadable = new FakeWindow(0x301, 61, string.Empty, Raised: true, ReopensUnraised: true);
        var readableUnknown = new FakeWindow(0x302, 62, string.Empty, Raised: false, ReopensUnraised: false);
        var plain = new FakeWindow(0x401, 71, console, Raised: false, ReopensUnraised: true);

        Assert.Multiple(() =>
        {
            Assert.That(Prefer(raisedServices.Handle, raisedServices, folderServices, readableServices),
                Is.EqualTo(readableServices.Handle), "v3-65: the copy BAXY opened with the person's rights");
            Assert.That(Prefer(raisedServices.Handle, raisedServices, folderServices),
                Is.EqualTo(raisedServices.Handle), "a folder named like the console is another program");
            Assert.That(Prefer(raisedTaskManager.Handle, raisedTaskManager, folderTaskManager),
                Is.EqualTo(raisedTaskManager.Handle), "the Task Manager raises itself: the limit stands");
            Assert.That(Prefer(unreadable.Handle, unreadable, readableUnknown),
                Is.EqualTo(unreadable.Handle), "an executable that cannot be read is no copy of anything");
            Assert.That(Prefer(plain.Handle, plain, readableServices), Is.EqualTo(plain.Handle), "not raised: kept");
            Assert.That(Prefer(0, readableServices), Is.EqualTo((nint)0));
        });
    }

    // Among the windows of a process whose description names the application, the one its title also names wins
    // over a secondary window above it; with no titled one, the topmost described window; then the title alone.
    [Test]
    public void TheTitledWindowOfADescribedProcessWinsOverItsSecondaryWindows()
    {
        nint friends = 0x3333;
        nint titled = 0x4444;
        nint folder = 0x5555;
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, titled, friends, titled), Is.EqualTo(titled));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, friends, folder), Is.EqualTo(friends));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, 0, folder), Is.EqualTo(folder));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0x6666, titled, friends, folder), Is.EqualTo((nint)0x6666));
            // The helper's description is not even read as Steam's: its launcher is Steam's own process.
            Assert.That(Launched(21792), Is.True);
        });
    }

    // Goal v3 r7 (v3-16): a photo opened from its folder shows in a window of the viewer's package titled only by the
    // file («paisaje.jpg»), above the viewer's gallery titled by the application's name («Fotos»); the view read the
    // gallery and the open image was never seen. A window found by its title alone gives way to the topmost window of
    // its own packaged application. Counter-cases: a window that is not packaged (a browser page, a classic program)
    // stays itself; the executable or its description still decide first; nothing titled is still nothing.
    [Test]
    public void ATitledWindowGivesWayToTheTopmostWindowOfItsOwnPackage()
    {
        nint gallery = 0x7001;
        nint openedImage = 0x7002;
        nint byProcess = 0x7003;
        nint described = 0x7004;
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, 0, gallery, openedImage), Is.EqualTo(openedImage));
            // The titled window is itself the topmost of its package.
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, 0, gallery, gallery), Is.EqualTo(gallery));
            // Not packaged: no package window is passed, the titled window stays.
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, 0, gallery, 0), Is.EqualTo(gallery));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(byProcess, 0, 0, gallery, openedImage), Is.EqualTo(byProcess));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, described, described, gallery, openedImage), Is.EqualTo(described));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, described, gallery, openedImage), Is.EqualTo(described));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, 0, 0, openedImage), Is.EqualTo((nint)0));
        });
    }

    // Ronda 24 (pasada r23 v3-05, v3-06): the first window of the application's process in Z order was a secondary
    // «86 aviso(s)» above the main window; the look read it and took 0 steps. Revision 4 (B1): that topmost window, a
    // secondary by itself (a dialog box, a window that cannot be maximized), gives way to the process's next window
    // that is no secondary. Counter-cases: a topmost that is no secondary is kept whatever its title says; without a
    // window of the process, description and title decide as before.
    [Test]
    public void BelowASecondaryTopmostWindowTheProcesssNextWindowComesFirst()
    {
        nint reminders = 0x8001;
        nint main = 0x8002;
        nint described = 0x8003;
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseNamedWindow(reminders, 0, 0, 0, 0, main, byProcessSecondary: true), Is.EqualTo(main));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(reminders, described, described, main, 0, main, byProcessSecondary: true),
                Is.EqualTo(main));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(reminders, 0, 0, 0, 0, 0, byProcessSecondary: true), Is.EqualTo(reminders));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, described, described, main, 0, 0), Is.EqualTo(described));
            // A window below without any window of the process is never taken from this list alone.
            Assert.That(VisibleControlSurface.ChooseNamedWindow(0, 0, 0, 0, 0, main, byProcessSecondary: true), Is.EqualTo((nint)0));
            // A dialog box (the system's dialog class) and a window that cannot be maximized are secondaries; a window
            // with a maximize box of any other class is not.
            Assert.That(VisibleControlSurface.IsSecondaryWindow(0x94C80000L, "#32770"), Is.True);
            Assert.That(VisibleControlSurface.IsSecondaryWindow(0x16CF0000L, "#32770"), Is.True);
            Assert.That(VisibleControlSurface.IsSecondaryWindow(0x14C80000L, "Ventana"), Is.True);
            Assert.That(VisibleControlSurface.IsSecondaryWindow(0x16CF0000L, "Ventana"), Is.False);
        });
    }

    // Revision 4 of ronda 24 (B1): probes over the bridge on e2486a699. «En Outlook, escribí “Gracias” en el mensaje»
    // with an open message «RE: Presupuesto - Mensaje (HTML)» above the main window «Bandeja de entrada - … - Outlook»,
    // and «in Photos, rotate the image I have open» with the viewer «paisaje.jpg» above the gallery «Photos»: the window
    // whose title named the application was chosen over the one the person works in, titled by its content. A topmost
    // window that can be maximized and is no dialog box is the person's and is kept, as before the round.
    [Test]
    public void AnOpenMessageOrPhotoAboveTheApplicationsMainWindowIsKept()
    {
        nint message = 0x8201;
        nint main = 0x8202;
        nint viewer = 0x8203;
        nint gallery = 0x8204;
        const long Maximizable = 0x16CF0000L;
        bool messageSecondary = VisibleControlSurface.IsSecondaryWindow(Maximizable, "Ventana");
        bool viewerSecondary = VisibleControlSurface.IsSecondaryWindow(Maximizable, "WinUIDesktopWin32WindowClass");
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.TitleNamesApplication("RE: Presupuesto - Mensaje (HTML)", "Outlook (classic)"), Is.False);
            Assert.That(VisibleControlSurface.TitleNamesApplication("paisaje.jpg", "Photos"), Is.False);
            Assert.That(messageSecondary, Is.False);
            Assert.That(viewerSecondary, Is.False);
            Assert.That(VisibleControlSurface.ChooseNamedWindow(message, 0, 0, main, 0, main, true, messageSecondary), Is.EqualTo(message));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(message, 0, 0, main, 0, main, true), Is.EqualTo(message));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(viewer, 0, 0, gallery, 0, gallery, true, viewerSecondary), Is.EqualTo(viewer));
        });
    }

    // Revision 1 of ronda 24 (B2): two windows of one browser and a «Guardar como» open over the one in front. The
    // owned dialog never enters the enumeration; its owner, disabled, is the process's topmost window and is kept: the
    // dialog is reached through it, the second enabled window carrying the application's name (the person's other
    // tabs) is never read nor acted in instead. Counter-case: the topmost enabled secondary («86 aviso(s)») still gives
    // way to the main window (v3-05, v3-06).
    [Test]
    public void ADisabledTopmostWindowUnderAModalIsKeptOverAnotherWindowOfTheSameApplication()
    {
        nint front = 0x8101;
        nint other = 0x8102;
        nint reminders = 0x8103;
        nint main = 0x8104;
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseNamedWindow(front, 0, 0, other, 0, other, byProcessEnabled: false), Is.EqualTo(front));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(front, 0, 0, 0, 0, 0, byProcessEnabled: false), Is.EqualTo(front));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(front, 0, 0, other, 0, other, byProcessEnabled: false, byProcessSecondary: true),
                Is.EqualTo(front));
            Assert.That(VisibleControlSurface.ChooseNamedWindow(reminders, 0, 0, 0, 0, main, byProcessEnabled: true, byProcessSecondary: true),
                Is.EqualTo(main));
        });
    }

    // A classic desktop process (this test host) runs as no packaged application; nor does a process that is not there.
    [Test]
    public void AClassicProcessIsNoPackagedApplication()
    {
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.PackagedApplication(unchecked((uint)Environment.ProcessId)), Is.Empty);
            Assert.That(VisibleControlSurface.PackagedApplication(0), Is.Empty);
        });
    }

    // The description is read from the process's own executable: this test process's is the test host's.
    [Test]
    public void TheDescriptionIsReadFromTheProcesssExecutable()
    {
        string expected = System.Diagnostics.FileVersionInfo.GetVersionInfo(Environment.ProcessPath!).FileDescription ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ProcessDescription(unchecked((uint)Environment.ProcessId)), Is.EqualTo(expected.Trim()));
            Assert.That(VisibleControlSurface.ProcessDescription(0), Is.Empty);
        });
    }

    [TestCase("Code", "Steam", true)]
    [TestCase("Code.exe", "Steam", true)]
    [TestCase("devenv", "Steam", true)]
    [TestCase("WindowsTerminal", "Steam", true)]
    [TestCase("powershell", "Steam", true)]
    [TestCase("cmd", "Steam", true)]
    [TestCase("Baxy", "Steam", true)]
    [TestCase("baxy-core", "Steam", true)]
    [TestCase("Code", "Visual Studio Code", false)]
    [TestCase("WindowsTerminal", "Terminal", false)]
    [TestCase("steamwebhelper", "Steam", false)]
    // Estabilización U (revisión H2): BAXY's own window stays protected even when the request names BAXY.
    [TestCase("Baxy", "BAXY", true)]
    [TestCase("baxy-core", "baxy", true)]
    public void AnEditorATerminalOrBaxyIsTheApplicationOnlyWhenNamed(string process, string application, bool protectedFrom)
    {
        Assert.That(VisibleControlSurface.ProtectedFrom(process, application), Is.EqualTo(protectedFrom));
    }

    // Estabilización D2 (banco h1, s11 and u1: Discord and Spotify already running and minimized, rect -32000; the view
    // read the person's editor in their place): a process whose only window is minimized has that one (shown behind the
    // person's window by the look, restored by the act that brings it up). Contracases: a usable window wins over a
    // minimized one, and another process's minimized window is never this one's.
    [Test]
    public void AProcessWhoseOnlyWindowIsMinimizedHasThatOne()
    {
        VisibleControlSurface.TopLevelWindow[] onlyMinimized =
        [
            new(20, 5, Usable: false, Area: 0, Minimized: true),
            new(21, 5, Usable: false, Area: 0),
        ];
        VisibleControlSurface.TopLevelWindow[] withUsable =
        [
            new(20, 5, Usable: false, Area: 0, Minimized: true),
            new(22, 5, Usable: true, Area: 500_000),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseProcessWindow(onlyMinimized, 5, front: 0), Is.EqualTo((nint)20));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(withUsable, 5, front: 0), Is.EqualTo((nint)22));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(onlyMinimized, 6, front: 0), Is.EqualTo((nint)0));
        });
    }

    // A process's window is one a person can see: never a cloaked or untitled frame it also holds (the shell's
    // explorer.exe holds one larger than its folder windows; taking it made every look bound to the process wait out
    // its retries, ≈1.8 s each). Pure rule over synthetic window records.
    [Test]
    public void AProcessWindowIsNeverALargerFrameWithoutAUsableSurface()
    {
        VisibleControlSurface.TopLevelWindow[] windows =
        [
            new(10, 7, Usable: false, Area: 3_000_000),
            new(11, 7, Usable: true, Area: 800_000),
            new(12, 9, Usable: true, Area: 5_000_000),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 7, front: 0), Is.EqualTo((nint)11));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 7, front: 10), Is.EqualTo((nint)11),
                "a front window without a surface gives way to the usable one");
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 8, front: 0), Is.EqualTo((nint)0));
        });
    }

    // Review 2026-10-07: two packaged apps (Settings, the Store) drawn in two frames of the same ApplicationFrameHost.
    // Bound to the shared host's pid, a look took whichever frame was in front; bound to the hosted app, its frame
    // stays the mission's whatever is in front. The shared host itself is never a process to bind to.
    [Test]
    public void TwoFramesOfTheSameHostKeepTheMissionOnItsOwn()
    {
        VisibleControlSurface.TopLevelWindow[] hostWindows =
        [
            new(30, 3, Usable: true, Area: 900_000),
            new(31, 3, Usable: true, Area: 1_200_000),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseProcessWindow(hostWindows, 3, front: 31), Is.EqualTo((nint)31),
                "the shared host's pid follows the front: the reason it is never recorded");
            Assert.That(VisibleControlSurface.ChooseProcessWindow([], 40, front: 31, frame: 30), Is.EqualTo((nint)30));
            Assert.That(VisibleControlSurface.IsSharedFrameHost("ApplicationFrameHost"), Is.True);
            Assert.That(VisibleControlSurface.IsSharedFrameHost("applicationframehost"), Is.True);
            Assert.That(VisibleControlSurface.IsSharedFrameHost("SystemSettings"), Is.False);
        });
    }

    // File Explorer with two folder windows open: the one the person brought to the front is the one, even when the
    // other is larger; another process's window in front does not count.
    [Test]
    public void TheProcessWindowInFrontIsTakenOverALargerOne()
    {
        VisibleControlSurface.TopLevelWindow[] windows =
        [
            new(20, 4, Usable: true, Area: 2_000_000),
            new(21, 4, Usable: true, Area: 600_000),
            new(22, 5, Usable: true, Area: 900_000),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 4, front: 21), Is.EqualTo((nint)21));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 4, front: 22), Is.EqualTo((nint)20));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 4, front: 0), Is.EqualTo((nint)20));
        });
    }

    // A packaged app drawn inside an ApplicationFrameHost frame (measured live on a store's search): the click on its
    // search field opened the history flyout, a titled top-level window of the app's own process, and the view moved
    // to it and lost the field. The frame hosting the process is its window, even with the flyout in front; a process
    // without a frame keeps the rules above.
    [Test]
    public void AFrameHostedProcessIsItsFrameNeverItsPopup()
    {
        VisibleControlSurface.TopLevelWindow[] windows =
        [
            new(30, 6, Usable: true, Area: 260_000),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 6, front: 0, frame: 31), Is.EqualTo((nint)31));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 6, front: 30, frame: 31), Is.EqualTo((nint)31),
                "the flyout in front is still a pop-up of the framed app");
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 6, front: 31, frame: 31), Is.EqualTo((nint)31));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 6, front: 0), Is.EqualTo((nint)30),
                "without a frame the process's own window stands");
        });
    }
}
