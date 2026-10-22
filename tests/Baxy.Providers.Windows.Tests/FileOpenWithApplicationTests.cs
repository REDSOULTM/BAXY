using System.Text.Json;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// cu-v3-abrir-archivo (r9 v3-15, v3-17, v3-18): «abrí paisaje.jpg en Fotos» is file.open with the application, opened
/// by the shell (the package's activation for files, or its executable with the path), never by the application's
/// window already running nor by keys; the file is never copied or moved, and nothing opens what file.open would not.
/// </summary>
[TestFixture]
public sealed class FileOpenWithApplicationTests
{
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-openwith-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(_root, "baxy-prueba-v3"));
        File.WriteAllBytes(Path.Combine(_root, "baxy-prueba-v3", "paisaje.jpg"), [1, 2, 3]);
        File.WriteAllBytes(Path.Combine(_root, "baxy-prueba-v3", "run.exe"), [1]);
    }

    [TearDown]
    public void TearDown()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    private static readonly InstalledApplicationEntry Photos = new("Fotos", "Microsoft.Windows.Photos_8wekyb3d8bbwe!App");

    private sealed class PhotosPlatform(bool takesFiles, bool handOverFails = false) : IInstalledApplicationPlatform
    {
        internal int Activations;
        internal string? FileActivated;

        public ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(CancellationToken cancellationToken) =>
            ValueTask.FromResult<IReadOnlyList<InstalledApplicationEntry>>([Photos]);

        // The gallery runs already (r9 v3-15/v3-17); after the file is handed over its own window shows.
        public IReadOnlyList<InstalledApplicationObservation> Inventory(InstalledApplicationEntry entry) =>
            FileActivated is null
                ? [new(40, 4, @"C:\Program Files\WindowsApps\Photos.exe", 100, true, false, "Photos")]
                : [new(40, 4, @"C:\Program Files\WindowsApps\Photos.exe", 100, true, false, "Photos"),
                   new(40, 4, @"C:\Program Files\WindowsApps\Photos.exe", 200, true, false, "Photos")];

        public bool Activate(InstalledApplicationEntry entry)
        {
            Activations++;
            return true;
        }

        public FileActivation.Outcome ActivateForFile(InstalledApplicationEntry entry, string filePath)
        {
            if (!takesFiles)
                return FileActivation.Outcome.NotListed;
            if (handOverFails)
                return FileActivation.Outcome.Refused;
            FileActivated = filePath;
            return FileActivation.Outcome.Issued;
        }

        public void RequestForeground(long windowHandle)
        {
        }

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }

    [Test]
    public async Task TheFileIsHandedToTheApplicationNotToItsRunningWindow()
    {
        string path = Path.Combine(_root, "baxy-prueba-v3", "paisaje.jpg");
        var platform = new PhotosPlatform(takesFiles: true);
        ApplicationOpenResult opened = await new WindowsInstalledApplicationOpenProvider(platform).OpenAsync(
            new ApplicationOpenRequest("Fotos", "fileopen_test", ForControl: true, FilePath: path), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(opened.Verified, Is.True);
            Assert.That(platform.FileActivated, Is.EqualTo(path));
            Assert.That(platform.Activations, Is.Zero, "no plain launch: the file goes with the activation");
            Assert.That(opened.WindowHandle, Is.EqualTo(200), "the window that appeared, never the gallery's");
            Assert.That(opened.AlreadyRunning, Is.False);
        });
    }

    [Test]
    public async Task AnApplicationThatTakesNoFileOrAFileThatIsNotThereLaunchesNothing()
    {
        string path = Path.Combine(_root, "baxy-prueba-v3", "paisaje.jpg");
        var refusing = new PhotosPlatform(takesFiles: false);
        ApplicationOpenResult refused = await new WindowsInstalledApplicationOpenProvider(refusing).OpenAsync(
            new ApplicationOpenRequest("Fotos", "fileopen_test", FilePath: path), CancellationToken.None);
        var failing = new PhotosPlatform(takesFiles: true, handOverFails: true);
        ApplicationOpenResult failed = await new WindowsInstalledApplicationOpenProvider(failing).OpenAsync(
            new ApplicationOpenRequest("Fotos", "fileopen_test", FilePath: path), CancellationToken.None);
        var platform = new PhotosPlatform(takesFiles: true);
        ApplicationOpenResult missing = await new WindowsInstalledApplicationOpenProvider(platform).OpenAsync(
            new ApplicationOpenRequest("Fotos", "fileopen_test", FilePath: Path.Combine(_root, "nada.jpg")), CancellationToken.None);
        ApplicationOpenResult relative = await new WindowsInstalledApplicationOpenProvider(platform).OpenAsync(
            new ApplicationOpenRequest("Fotos", "fileopen_test", FilePath: "paisaje.jpg"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.Verified, Is.False);
            Assert.That(refused.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.FileNotAccepted));
            Assert.That(refused.Receipt.LaunchIssued, Is.False);
            Assert.That(refusing.Activations, Is.Zero);
            // cu-v3-archivo-empaquetado (live v3-15/v3-17): listed and not handed over is its own cause, never «Windows
            // does not list it».
            Assert.That(failed.Verified, Is.False);
            Assert.That(failed.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.FileActivationFailed));
            Assert.That(failed.Receipt.LaunchIssued, Is.False);
            Assert.That(failing.Activations, Is.Zero, "no plain launch in its place");
            Assert.That(missing.Verified || relative.Verified, Is.False);
            Assert.That(platform.FileActivated, Is.Null);
        });
    }

    [Test]
    public async Task FileOpenWithAnApplicationAsksTheOpenerForThatFileInTheKnownFolder()
    {
        ApplicationOpenRequest? asked = null;
        var adapter = new WindowsFileToolsAdapter(
            folder => folder == "documents" ? _root : null,
            fetch: null,
            openWith: (request, _) =>
            {
                asked = request;
                return ValueTask.FromResult(new ApplicationOpenResult(false, false, "Fotos", false, null, null,
                    ApplicationOpenErrorCodes.ApplicationNotFound,
                    new ApplicationLaunchReceipt(request.InvocationId, request.ApplicationId, false, false, null, null,
                        null, null, null, null, ApplicationOpenErrorCodes.ApplicationNotFound)));
            });
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("file.open", JsonSerializer.SerializeToElement(
            new { folder = "documents", name = "baxy-prueba-v3\\paisaje.jpg", application = "Fotos" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.Not.Null);
            Assert.That(asked!.ApplicationId, Is.EqualTo("Fotos"));
            Assert.That(asked.FilePath, Is.EqualTo(Path.Combine(_root, "baxy-prueba-v3", "paisaje.jpg")));
            Assert.That(asked.ForControl, Is.True);
            Assert.That(asked.Foreground, Is.False, "opened behind the person's window, as app.open");
            Assert.That(receipt.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.ApplicationNotFound));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(Directory.GetFiles(Path.Combine(_root, "baxy-prueba-v3")), Has.Length.EqualTo(2), "nothing copied or moved");
        });
    }

    // Renew al máximo (lote 4, a; R6.6): an application not installed under that name (or two of it) fails file.open
    // with the closest installed names the opener read, as app.open says them; none of them was opened.
    [TestCase(ApplicationOpenErrorCodes.ApplicationNotFound)]
    [TestCase(ApplicationOpenErrorCodes.ApplicationAmbiguous)]
    public async Task AnApplicationNotFoundCarriesTheOpenersCandidates(string code)
    {
        var adapter = new WindowsFileToolsAdapter(
            folder => folder == "documents" ? _root : null,
            fetch: null,
            openWith: (request, _) => ValueTask.FromResult(new ApplicationOpenResult(false, false, "Fotis", false, null,
                null, code,
                new ApplicationLaunchReceipt(request.InvocationId, request.ApplicationId, false, false, null, null,
                    null, null, null, null, code),
                Candidates: ["Fotos", "Fotos heredado"])));
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("file.open", JsonSerializer.SerializeToElement(
            new { folder = "documents", name = "baxy-prueba-v3\\paisaje.jpg", application = "Fotis" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.False, "nothing was launched");
            Assert.That(receipt.Result, Is.Not.Null, "the candidates travel with the failure");
            Assert.That(receipt.Result!.Value.GetProperty("candidates").EnumerateArray().Select(item => item.GetString()),
                Is.EqualTo(new[] { "Fotos", "Fotos heredado" }));
        });
    }

    // molestia-ayudantes (riesgos-fusion 5): a file the person asked to see («foreground», set by the App outside a
    // mission) is opened in front; the test above is the contracase (a mission's file.open, behind).
    [Test]
    public async Task AFileThePersonAskedToSeeIsOpenedInFront()
    {
        ApplicationOpenRequest? asked = null;
        var adapter = new WindowsFileToolsAdapter(
            folder => folder == "documents" ? _root : null,
            fetch: null,
            openWith: (request, _) =>
            {
                asked = request;
                return ValueTask.FromResult(new ApplicationOpenResult(false, false, "Fotos", false, null, null,
                    ApplicationOpenErrorCodes.ApplicationNotFound,
                    new ApplicationLaunchReceipt(request.InvocationId, request.ApplicationId, false, false, null, null,
                        null, null, null, null, ApplicationOpenErrorCodes.ApplicationNotFound)));
            });
        _ = await adapter.InvokeAsync("file.open", JsonSerializer.SerializeToElement(
            new { folder = "documents", name = "baxy-prueba-v3\\paisaje.jpg", application = "Fotos", foreground = true }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.Not.Null);
            Assert.That(asked!.Foreground, Is.True);
            Assert.That(asked.ForControl, Is.True);
        });
    }

    // The «Abrir con» handlers SHAssocEnumHandlers listed on the owner's PC (2026-10-08), frozen: .txt and .png.
    private static readonly FileActivation.Handler[] TextHandlers =
    [
        new(@"C:\Program Files\WindowsApps\Microsoft.WindowsNotepad_11.2607.14.0_x64__8wekyb3d8bbwe\Notepad\Notepad.exe", "Bloc de notas"),
        new(@"C:\Users\usuario\AppData\Local\Programs\Microsoft VS Code\Code.exe", "Visual Studio Code"),
        new(@"C:\Users\usuario\AppData\Local\Programs\Opera GX\opera.exe", "Opera GX Internet Browser"),
        new(@"C:\Program Files\Microsoft Office\root\Office16\Winword.exe", "Word"),
    ];

    private static readonly FileActivation.Handler[] ImageHandlers =
    [
        new(@"C:\Program Files\WindowsApps\Microsoft.Paint_11.2605.81.0_x64__8wekyb3d8bbwe\PaintApp\mspaint.exe", "Paint"),
        new("Fotos", "Fotos"),
        new(@"C:\Program Files\WindowsApps\Microsoft.WindowsNotepad_11.2607.14.0_x64__8wekyb3d8bbwe\Notepad\Notepad.exe", "Bloc de notas"),
    ];

    [Test]
    public void OnlyAnApplicationWindowsListsToOpenThatTypeGetsTheFile()
    {
        // Review, finding 1 (abre notas.txt en python): Python and Node.js are Start entries whose executable the shell
        // gives, and «.txt» would run as code; an uninstaller and a launcher that drops its shortcut's arguments too.
        var python = new InstalledApplicationEntry("Python 3.12 (64-bit)", "python-312",
            TargetPath: @"C:\Users\usuario\AppData\Local\Programs\Python\Python312\python.exe");
        var node = new InstalledApplicationEntry("Node.js", "node", TargetPath: @"C:\Program Files\nodejs\node.exe");
        var uninstaller = new InstalledApplicationEntry("Desinstalar X", "unins", TargetPath: @"C:\Program Files\X\unins000.exe");
        var launcher = new InstalledApplicationEntry("Discord", "discord",
            TargetPath: @"C:\Users\usuario\AppData\Local\Discord\Update.exe", TargetArguments: "--processStart Discord.exe");
        var word = new InstalledApplicationEntry("Word", "word", TargetPath: @"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE");
        var notepad = new InstalledApplicationEntry("Bloc de notas", "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App");
        var paint = new InstalledApplicationEntry("Paint", "Microsoft.Paint_8wekyb3d8bbwe!App");
        var pythonStore = new InstalledApplicationEntry("Python 3.12", "PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0!Python");

        FileActivation.HandOff For(InstalledApplicationEntry entry, FileActivation.Handler[] handlers) =>
            FileActivation.Match(entry, WindowsInstalledApplicationPlatform.StrongExecutablePath(entry), handlers).HandOff;

        Assert.Multiple(() =>
        {
            Assert.That(For(python, TextHandlers), Is.EqualTo(FileActivation.HandOff.None));
            Assert.That(For(node, TextHandlers), Is.EqualTo(FileActivation.HandOff.None));
            Assert.That(For(uninstaller, TextHandlers), Is.EqualTo(FileActivation.HandOff.None));
            Assert.That(For(launcher, ImageHandlers), Is.EqualTo(FileActivation.HandOff.None));
            Assert.That(For(pythonStore, TextHandlers), Is.EqualTo(FileActivation.HandOff.None));
            Assert.That(For(paint, TextHandlers), Is.EqualTo(FileActivation.HandOff.None), "Paint opens no .txt");
            Assert.That(For(Photos, TextHandlers), Is.EqualTo(FileActivation.HandOff.None));
            Assert.That(For(python, []), Is.EqualTo(FileActivation.HandOff.None), "no handlers read: nothing handed");
            // The contracases: the applications Windows does list get the file.
            Assert.That(For(word, TextHandlers), Is.EqualTo(FileActivation.HandOff.Executable));
            Assert.That(For(notepad, TextHandlers), Is.EqualTo(FileActivation.HandOff.Package));
            Assert.That(For(paint, ImageHandlers), Is.EqualTo(FileActivation.HandOff.Package));
            Assert.That(For(Photos, ImageHandlers), Is.EqualTo(FileActivation.HandOff.Package));
        });
    }

    // cu-v3-archivo-empaquetado: the same .png handlers read again with the identity each packaged one reports
    // (IObjectWithAppUserModelID, measured 2026-10-08); a desktop one reports none, or one that is no package's.
    private static readonly FileActivation.Handler[] ImageHandlersWithIds =
    [
        new(@"C:\Program Files\WindowsApps\Microsoft.Paint_11.2605.81.0_x64__8wekyb3d8bbwe\PaintApp\mspaint.exe", "Paint",
            "Microsoft.Paint_8wekyb3d8bbwe!App"),
        new("Fotos", "Fotos", "Microsoft.Windows.Photos_8wekyb3d8bbwe!App"),
        new(@"C:\Users\usuario\AppData\Local\Programs\Microsoft VS Code\Code.exe", "Visual Studio Code", "Microsoft.VisualStudioCode"),
    ];

    [Test]
    public void APackagedHandlerIsKnownByTheIdentityItReportsWhateverItsName()
    {
        // Live v3-15/v3-17: Fotos is listed for .png and .jpg by its name alone; a catalog that names it otherwise
        // («Photos» in English) still finds it by the identity its handler reports.
        var english = new InstalledApplicationEntry("Photos", "Microsoft.Windows.Photos_8wekyb3d8bbwe!App");
        var snipping = new InstalledApplicationEntry("Recortes", "Microsoft.ScreenSketch_8wekyb3d8bbwe!App");
        var pythonStore = new InstalledApplicationEntry("Python 3.12", "PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0!Python");
        var code = new InstalledApplicationEntry("Visual Studio Code", "Microsoft.VisualStudioCode",
            TargetPath: @"C:\Users\usuario\AppData\Local\Programs\Microsoft VS Code\Code.exe");

        FileActivation.HandOff For(InstalledApplicationEntry entry) =>
            FileActivation.Match(entry, WindowsInstalledApplicationPlatform.StrongExecutablePath(entry), ImageHandlersWithIds).HandOff;

        Assert.Multiple(() =>
        {
            Assert.That(For(english), Is.EqualTo(FileActivation.HandOff.Package));
            Assert.That(For(Photos), Is.EqualTo(FileActivation.HandOff.Package));
            // The counter-cases: a package Windows does not list for the type, and an identity without a package.
            Assert.That(For(snipping), Is.EqualTo(FileActivation.HandOff.None), "not in this list");
            Assert.That(For(pythonStore), Is.EqualTo(FileActivation.HandOff.None));
            Assert.That(For(code), Is.EqualTo(FileActivation.HandOff.Executable), "a desktop one by its executable");
            Assert.That(FileActivation.Match(english, null, TextHandlers).HandOff, Is.EqualTo(FileActivation.HandOff.None));
        });
    }

    [Test]
    public void AWindowNamesTheFileOutsideTheApplicationsOwnName()
    {
        // Review, finding 2: the application's window shows another file, or its own name holds the file's.
        Assert.Multiple(() =>
        {
            Assert.That(WindowsFileToolsAdapter.TitleNamesFile("lista.txt - Bloc de notas", "notas", "notas.txt", "Bloc de notas"), Is.False);
            Assert.That(WindowsFileToolsAdapter.TitleNamesFile("Fotos", "foto", "foto.png", "Fotos"), Is.False);
            Assert.That(WindowsFileToolsAdapter.TitleNamesFile("fotografia - Paint", "foto", "foto.png", "Paint"), Is.False);
            Assert.That(WindowsFileToolsAdapter.TitleNamesFile("Captura de pantalla 2026-10-07 042618.png", "paisaje", "paisaje.jpg", "Fotos"), Is.False);
            Assert.That(WindowsFileToolsAdapter.TitleNamesFile("notas.txt - Bloc de notas", "notas", "notas.txt", "Bloc de notas"), Is.True);
            Assert.That(WindowsFileToolsAdapter.TitleNamesFile("foto.png ‎- Fotos", "foto", "foto.png", "Fotos"), Is.True);
            Assert.That(WindowsFileToolsAdapter.TitleNamesFile("foto - Paint", "foto", "foto.png", "Paint"), Is.True);
        });
    }

    [Test]
    public async Task NothingFileOpenWouldRefuseIsHandedToAnApplication()
    {
        int asked = 0;
        var adapter = new WindowsFileToolsAdapter(
            folder => folder == "documents" ? _root : null,
            fetch: null,
            openWith: (_, _) =>
            {
                asked++;
                throw new InvalidOperationException("never asked");
            });
        ExternalCapabilityReceipt program = await adapter.InvokeAsync("file.open", JsonSerializer.SerializeToElement(
            new { folder = "documents", name = "baxy-prueba-v3\\run.exe", application = "Fotos" }), CancellationToken.None);
        ExternalCapabilityReceipt escape = await adapter.InvokeAsync("file.open", JsonSerializer.SerializeToElement(
            new { folder = "documents", name = "..\\secreto.jpg", application = "Fotos" }), CancellationToken.None);
        ExternalCapabilityReceipt missing = await adapter.InvokeAsync("file.open", JsonSerializer.SerializeToElement(
            new { folder = "documents", name = "nada.jpg", application = "Fotos" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.Zero);
            Assert.That(program.ErrorCode, Is.EqualTo("file_extension_not_openable"));
            Assert.That(escape.ErrorCode, Is.EqualTo("file_name_invalid"));
            Assert.That(missing.ErrorCode, Is.EqualTo("file_not_found"));
            Assert.That(program.EffectMayHaveOccurred | escape.EffectMayHaveOccurred | missing.EffectMayHaveOccurred, Is.False);
        });
    }
}
