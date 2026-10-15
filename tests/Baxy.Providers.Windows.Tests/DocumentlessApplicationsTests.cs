using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// v3 r6 lectores (t2-r4 c04-5 «cierra configuración» pidió confirmación): which windows hold no document of the
/// person is data (documentless_applications.v1.json), matched by the catalog identity a window was resolved from or
/// by its executable. Applications with documents, the shared frame host and anything unknown are never listed.
/// </summary>
[TestFixture]
public sealed class DocumentlessApplicationsTests
{
    [TestCase("windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel", null)]
    [TestCase("microsoft.windowsalarms_8wekyb3d8bbwe!App", null)]
    [TestCase(null, @"C:\Windows\System32\Taskmgr.exe")]
    [TestCase(null, @"C:\Windows\ImmersiveControlPanel\SystemSettings.exe")]
    // v3 r22 uso real (t4-c03 «ya cierra discord»): applications whose content lives in the person's account.
    [TestCase(null, @"C:\Users\person\AppData\Local\Discord\app-1.0.9200\Discord.exe")]
    [TestCase("com.squirrel.Discord.Discord", @"C:\Users\person\AppData\Local\Discord\app-1.0.9200\Discord.exe")]
    [TestCase("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", null)]
    [TestCase(null, @"C:\Program Files (x86)\Steam\steam.exe")]
    [TestCase(null, @"C:\Program Files (x86)\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe")]
    public void AWindowWithoutDocumentsIsListed(string? appUserModelId, string? executablePath) =>
        Assert.That(DocumentlessApplications.Contains(appUserModelId, executablePath), Is.True);

    // Contracasos: Word, Notepad and Paint hold documents; the frame host that draws every packaged application, an
    // unknown application and a window nobody can place are never listed.
    [TestCase("Microsoft.Office.WINWORD.EXE.15", @"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE")]
    [TestCase("Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", @"C:\Program Files\WindowsApps\Notepad\Notepad.exe")]
    [TestCase("Microsoft.Paint_8wekyb3d8bbwe!App", @"C:\Windows\System32\ApplicationFrameHost.exe")]
    [TestCase(null, @"C:\Windows\System32\ApplicationFrameHost.exe")]
    // File Explorer's process also owns the desktop, the taskbar and the copy/move progress dialog (closing it
    // cancels a transfer); its windows keep asking.
    [TestCase("Microsoft.Windows.Explorer", null)]
    [TestCase(null, @"C:\Windows\explorer.exe")]
    // Review r10a: the Calculator holds the calculation in progress and its session memory and history, Character
    // Map its «Characters to copy» field; reopening brings back neither, so their close keeps asking.
    [TestCase("Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", null)]
    [TestCase(null, @"C:\Program Files\WindowsApps\Microsoft.WindowsCalculator_8wekyb3d8bbwe\CalculatorApp.exe")]
    [TestCase(null, @"C:\Windows\System32\charmap.exe")]
    [TestCase("Contoso.Editor_abc!App", null)]
    [TestCase(null, null)]
    [TestCase("", "")]
    public void AWindowThatMayHoldWorkIsNotListed(string? appUserModelId, string? executablePath) =>
        Assert.That(DocumentlessApplications.Contains(appUserModelId, executablePath), Is.False);

    [TestCase("Microsoft.Windows.Explorer", null)]
    [TestCase(null, @"C:\Windows\explorer.exe")]
    public void FileExplorerNeverClosesWithoutAsking(string? appUserModelId, string? executablePath) =>
        Assert.That(DocumentlessApplications.NeverWithoutAsking(appUserModelId, executablePath), Is.True);

    [TestCase(null, @"C:\Users\person\AppData\Local\Discord\app-1.0.9200\Discord.exe")]
    [TestCase("Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", null)]
    [TestCase(null, null)]
    public void OtherApplicationsAreNotMarkedAsNeverClosingWithoutAsking(string? appUserModelId, string? executablePath) =>
        Assert.That(DocumentlessApplications.NeverWithoutAsking(appUserModelId, executablePath), Is.False);

    [Test]
    public void APackageFamilyMatchesOnlyBeforeTheBang()
    {
        // A packaged identity whose application part names a listed family is still another package.
        Assert.That(
            DocumentlessApplications.Contains("Contoso.Notes_abc!windows.immersivecontrolpanel_cw5n1h2txyewy", null),
            Is.False);
    }

    [Test]
    public async Task AFrameKeepsTheApplicationItWasResolvedFrom()
    {
        // Settings and Paint both draw inside ApplicationFrameHost.exe: only the resolved identity tells them apart.
        var applications = new WindowsInstalledApplicationOpenProvider(new AppPlatform());
        var provider = new WindowsWindowControlProvider(new FramePlatform(), applications);

        WindowResolveResult settings = await provider.ResolveApplicationAsync("Configuración", 10, CancellationToken.None);
        WindowResolveResult paint = await provider.ResolveApplicationAsync("Paint", 10, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(settings.Succeeded, Is.True, settings.ErrorCode);
            Assert.That(paint.Succeeded, Is.True, paint.ErrorCode);
            Assert.That(provider.HoldsNoDocument(settings.Windows.Single().WindowId), Is.True);
            Assert.That(provider.HoldsNoDocument(paint.Windows.Single().WindowId), Is.False);
            // Reading it does not consume the id: the close that follows still finds it.
            Assert.That(provider.HoldsNoDocument(settings.Windows.Single().WindowId), Is.True);
        });
    }

    // r27u (tandas v3b1 y r23q, t2-c04 t5): Configuración was resolved to the 71×41 popup host its process owns, that
    // was closed and the close was told. With nothing but owned popups to see, no window is resolved and nothing can
    // be closed or told closed.
    [Test]
    public async Task AnApplicationSeenOnlyThroughOwnedPopupsResolvesNoWindow()
    {
        var applications = new WindowsInstalledApplicationOpenProvider(new AppPlatform { OnlyOwnedPopups = true });
        var provider = new WindowsWindowControlProvider(new FramePlatform(), applications);

        WindowResolveResult settings = await provider.ResolveApplicationAsync("Configuración", 10, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(settings.Succeeded, Is.False);
            Assert.That(settings.Windows, Is.Empty);
            Assert.That(settings.ErrorCode, Is.EqualTo(WindowControlErrorCodes.WindowNotFound));
        });
    }

    private const string FrameHost = @"C:\Windows\System32\ApplicationFrameHost.exe";

    private static readonly InstalledApplicationEntry Settings = new(
        "Configuración", "windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel");

    private static readonly InstalledApplicationEntry Paint = new("Paint", "Microsoft.Paint_8wekyb3d8bbwe!App");

    private sealed class AppPlatform : IInstalledApplicationPlatform
    {
        public ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
            CancellationToken cancellationToken) =>
            ValueTask.FromResult<IReadOnlyList<InstalledApplicationEntry>>([Settings, Paint]);

        public IReadOnlyList<InstalledApplicationObservation> Inventory(InstalledApplicationEntry entry) =>
            InventoryForWindowResolution(entry, CancellationToken.None);

        public IReadOnlyList<InstalledApplicationObservation> InventoryForWindowResolution(
            InstalledApplicationEntry entry,
            CancellationToken cancellationToken)
        {
            var seen = new List<InstalledApplicationObservation>
            {
                new(77, 7, FrameHost, entry == Settings ? 1 : 2, true, false, "ApplicationFrameHost"),
            };
            WindowsInstalledApplicationPlatform.KeepOwnWindows(seen, _ => OnlyOwnedPopups, null);
            return seen;
        }

        public bool OnlyOwnedPopups { get; init; }

        public bool Activate(InstalledApplicationEntry entry) => false;

        public void RequestForeground(long windowHandle)
        {
        }

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }

    private sealed class FramePlatform : IWindowControlPlatform
    {
        public DateTimeOffset UtcNow => DateTimeOffset.UnixEpoch;

        public WindowSnapshot? FindForegroundWindow() => null;

        public WindowEnumeration FindVisibleWindows(string processName, int limit,
            bool byTitle = false, int offset = 0, bool allWindows = false,
            CancellationToken cancellationToken = default) => new([], 0, true);

        public WindowSnapshot Observe(WindowIdentity identity) =>
            new(identity, "normal", false, new WindowBounds(0, 0, 800, 600), "Ventana");

        public bool Execute(WindowIdentity identity, WindowControlAction action) => false;
        public bool SetBounds(WindowIdentity identity, WindowBounds bounds) => false;
        public bool RequestClose(WindowIdentity identity) => false;
        public bool RequestSystemClose(WindowIdentity identity) => false;
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }

    [TestCase("")]
    [TestCase("win_0123")]
    [TestCase("win_00000000000000000000000000000000")]
    public void AnIdTheProviderNeverIssuedHoldsADocument(string windowId)
    {
        var provider = new WindowsWindowControlProvider();
        Assert.That(provider.HoldsNoDocument(windowId), Is.False);
    }
}
