using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 20b, palanca 8, objetivo 3 (pasada r18, v3-44): in the Control Panel a click on «Ver dispositivos e
/// impresoras» makes Windows open Settings in its frame host. The Control Panel's image stayed the same and the click
/// was told <c>visible_button_postread_unchanged</c>. The desktop's root windows are taken before the click; a window
/// of another process born or brought to the front during the post-read is where the click handed its effect, and the
/// receipt names it (<c>handedTo</c>). Pure rules and a scripted worker: nothing on the desktop is touched.
/// r27: the fixed 1.2 s tail after the post-read is gone. Measured on 3 runs of the bank after it was added (c24b, c25,
/// clat: 226 missions, 267 clicks): 20 unchanged clicks paid it whole and it found no window in any; no frozen trace
/// holds a handed window, and the live v3-44 click was told by its own surface at 788 ms.
/// </summary>
[TestFixture]
public sealed class ComputerUseHandoffTests
{
    private const int ControlPanel = 4100;
    private const int FrameHost = 5200;
    private const int Person = 6300;
    private const nint PanelWindow = 4660;
    private const nint SettingsFrame = 9100;
    private const nint PersonWindow = 7000;

    private static readonly HashSet<int> Clicked = [ControlPanel];

    private static VisibleControlSurface.RootSnapshot Snapshot(nint front, long personInput, params (nint Window, int Process)[] windows) =>
        new([.. windows.Select(window => new VisibleControlSurface.RootWindow(window.Window, window.Process))], front, Clicked, personInput);

    [Test]
    public void AWindowOfAnotherProcessBornDuringTheClickIsWhereItHandedItsEffect()
    {
        VisibleControlSurface.RootSnapshot before = Snapshot(PersonWindow, 10, (PersonWindow, Person), (PanelWindow, ControlPanel));
        VisibleControlSurface.RootSnapshot after = Snapshot(
            PersonWindow, 10, (SettingsFrame, FrameHost), (PersonWindow, Person), (PanelWindow, ControlPanel));
        Assert.That(VisibleControlSurface.HandedTo(before, after).Window, Is.EqualTo(SettingsFrame));
    }

    [Test]
    public void AnAlreadyOpenWindowThatTookTheFrontIsWhereItHandedItsEffect()
    {
        // Settings was open behind: the click brought it forward instead of opening another.
        VisibleControlSurface.RootSnapshot before = Snapshot(
            PersonWindow, 10, (PersonWindow, Person), (PanelWindow, ControlPanel), (SettingsFrame, FrameHost));
        VisibleControlSurface.RootSnapshot after = Snapshot(
            SettingsFrame, 10, (SettingsFrame, FrameHost), (PersonWindow, Person), (PanelWindow, ControlPanel));
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.HandedTo(before, after, out bool born).Window, Is.EqualTo(SettingsFrame));
            Assert.That(born, Is.False, "it was open before the click: never the mission's to clean up");
        });
    }

    [Test]
    public void NothingIsHandedWhenNoOtherWindowCameOrThePersonMovedTheFront()
    {
        VisibleControlSurface.RootSnapshot before = Snapshot(
            PersonWindow, 10, (PersonWindow, Person), (PanelWindow, ControlPanel), (SettingsFrame, FrameHost));
        Assert.Multiple(() =>
        {
            // Contracase: the same windows, the same front.
            Assert.That(VisibleControlSurface.HandedTo(before, before).Window, Is.EqualTo((nint)0));
            // Contracase: a window of the clicked process itself (its own dialog) is the click's own surface, not a handoff.
            Assert.That(VisibleControlSurface.HandedTo(before, Snapshot(
                PersonWindow, 10, (8800, ControlPanel), (PersonWindow, Person), (PanelWindow, ControlPanel),
                (SettingsFrame, FrameHost))).Window, Is.EqualTo((nint)0));
            // Contracase: the person clicked or switched meanwhile: the window in front or born now may be theirs.
            Assert.That(VisibleControlSurface.HandedTo(before, Snapshot(
                SettingsFrame, 11, (SettingsFrame, FrameHost), (PersonWindow, Person), (PanelWindow, ControlPanel))).Window,
                Is.EqualTo((nint)0));
            Assert.That(VisibleControlSurface.HandedTo(before, Snapshot(
                PersonWindow, 11, (8801, 9999), (PersonWindow, Person), (PanelWindow, ControlPanel),
                (SettingsFrame, FrameHost))).Window, Is.EqualTo((nint)0));
        });
    }

    // Review 3 of palanca 8 (B1): Ctrl+N in the person's editor or Enter on a file in their folder moves no front by
    // its kind (no mouse button, no Alt or Windows key), yet it opens a window of theirs. The mark a handoff is measured
    // against is any input of theirs that reaches a window, so a key of theirs during the click hands nothing.
    [Test]
    public void AKeyOfThePersonDuringTheClickHandsNothing()
    {
        var pause = new KeyPause { Reaching = 10, FrontMoving = 10 };
        VisibleControlSurface.RootSnapshot before = Snapshot(
            PersonWindow, VisibleControlSurface.PersonInputMark(pause), (PersonWindow, Person), (PanelWindow, ControlPanel));
        pause.Reaching = 20;  // Ctrl+N, Enter or a typed key: reaches their window, moves no front by its kind.
        VisibleControlSurface.RootSnapshot after = Snapshot(
            PersonWindow, VisibleControlSurface.PersonInputMark(pause), (8802, Person), (PersonWindow, Person),
            (PanelWindow, ControlPanel));
        Assert.Multiple(() =>
        {
            Assert.That(pause.LastFrontMovingInputMs, Is.EqualTo(10), "the key moved no front by its kind");
            Assert.That(VisibleControlSurface.HandedTo(before, after).Window, Is.EqualTo((nint)0),
                "the window their key opened is never where the click handed its effect");
            // Contracase: with no input of theirs the same new window is the click's.
            Assert.That(VisibleControlSurface.HandedTo(before, after with { PersonInput = before.PersonInput }).Window,
                Is.EqualTo((nint)8802));
        });
    }

    private sealed class KeyPause : IUserInputPause
    {
        internal long Reaching { get; set; }

        internal long FrontMoving { get; set; }

        public long LastForeignInputMs => Math.Max(Reaching, FrontMoving);

        public long LastReachingInputMs => Reaching;

        public long LastFrontMovingInputMs => FrontMoving;

        public bool HeldDown() => false;

        public bool TellsOwnInput => true;

        public string Source => "raw_input";
    }

    private const string PendingClick =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
        "\"pending\":true,\"name\":\"Ver dispositivos e impresoras\",\"kind\":\"Hyperlink\",\"controlIdentity\":\"1.2.3\"," +
        "\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}";

    private const string UnchangedControl =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
        "\"name\":\"Ver dispositivos e impresoras\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false}";

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private static ValueTask<VisibleControlSurface.CapturedWindow?> SameImage(nint window, bool? selfDrawn, CancellationToken token) =>
        ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
            new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, "same"));

    private static readonly VisibleClickTiming Fast = VisibleClickTiming.Default with
    {
        ControlPostread = TimeSpan.FromMilliseconds(100),
        SurfaceFirstSample = TimeSpan.FromMilliseconds(20),
        SurfacePostread = TimeSpan.FromMilliseconds(200),
        PostreadPeriod = TimeSpan.FromMilliseconds(10),
    };

    private static WindowsVisibleControlAdapter Adapter(Func<int, VisibleControlSurface.RootSnapshot> roots, VisibleClickTiming timing)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        int looked = 0;
        return new WindowsVisibleControlAdapter(worker, null, null, timing: timing, capture: SameImage)
        {
            PopupsOf = window => [],
            RootWindows = window => roots(looked++),
            DescribeHanded = found => new VisibleControlSurface.HandedWindow(found.Window, found.ProcessId, "SystemSettings", "Configuración"),
        };
    }

    // v3-44: the Control Panel stays the same and Settings is slow: it comes after the control's own answer gave up and
    // many equal images of the Control Panel, within the post-read's budget. The receipt comes when it does, not at the
    // budget's end.
    [Test]
    public async Task AClickThatOpenedAnotherProcesssWindowIsDoneAndNamesIt()
    {
        VisibleControlSurface.RootSnapshot before = Snapshot(PersonWindow, 10, (PersonWindow, Person), (PanelWindow, ControlPanel));
        VisibleControlSurface.RootSnapshot after = Snapshot(
            PersonWindow, 10, (SettingsFrame, FrameHost), (PersonWindow, Person), (PanelWindow, ControlPanel));
        var started = Stopwatch.StartNew();
        WindowsVisibleControlAdapter adapter = Adapter(
            looked => looked == 0 || started.Elapsed < TimeSpan.FromMilliseconds(300) ? before : after,
            Fast with { SurfacePostread = TimeSpan.FromSeconds(30) });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Ver dispositivos e impresoras","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(started.Elapsed, Is.GreaterThanOrEqualTo(TimeSpan.FromMilliseconds(300))
                .And.LessThan(TimeSpan.FromSeconds(15)), "told when the window came");
            JsonElement handed = receipt.Result!.Value.GetProperty("handedTo");
            Assert.That(handed.GetProperty("hwnd").GetInt64(), Is.EqualTo((long)SettingsFrame));
            Assert.That(handed.GetProperty("title").GetString(), Is.EqualTo("Configuración"));
            Assert.That(handed.GetProperty("process").GetString(), Is.EqualTo("SystemSettings"));
            Assert.That(handed.GetProperty("processId").GetInt32(), Is.EqualTo(FrameHost));
            Assert.That(handed.GetProperty("born").GetBoolean(), Is.True, "it came with the click");
            Assert.That(receipt.Result!.Value.TryGetProperty("surfaceChanged", out JsonElement changed) && changed.GetBoolean(),
                Is.False, "the clicked window did not change");
        });
    }

    // Contracase: no other window comes; the click is unchanged at the post-read's budget (0.2 s here) and nothing is
    // waited after it (r27: the tail added 1.2 s to every such click).
    [Test]
    public async Task AClickWithNoOtherWindowStaysUnchangedAtThePostreadsBudget()
    {
        VisibleControlSurface.RootSnapshot before = Snapshot(PersonWindow, 10, (PersonWindow, Person), (PanelWindow, ControlPanel));
        WindowsVisibleControlAdapter adapter = Adapter(_ => before, Fast);
        var took = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Ver dispositivos e impresoras","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
            Assert.That(took.Elapsed, Is.GreaterThanOrEqualTo(Fast.SurfacePostread).And.LessThan(TimeSpan.FromSeconds(1)));
        });
    }

    // Review 3 of palanca 8 (B1): the receipt says where the person's input last went (to the window, to its process or
    // the shell), what the mission's guard of their windows reads before following it.
    [Test]
    public async Task TheReceiptSaysWhereThePersonsInputLastWent()
    {
        VisibleControlSurface.RootSnapshot before = Snapshot(PersonWindow, 10, (PersonWindow, Person), (PanelWindow, ControlPanel));
        VisibleControlSurface.RootSnapshot after = Snapshot(
            PersonWindow, 10, (SettingsFrame, FrameHost), (PersonWindow, Person), (PanelWindow, ControlPanel));
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        int looked = 0;
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, timing: Fast, capture: SameImage)
        {
            PopupsOf = window => [],
            RootWindows = window => looked++ == 0 ? before : after,
            DescribeHanded = found => new VisibleControlSurface.HandedWindow(
                found.Window, found.ProcessId, "WINWORD", "Informe final.docx - Word", PersonInputAgoMs: 40, PersonNearAgoMs: 40),
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Ver dispositivos e impresoras","window":4660}"""), CancellationToken.None);

        JsonElement handed = receipt.Result!.Value.GetProperty("handedTo");
        Assert.Multiple(() =>
        {
            Assert.That(handed.GetProperty("personInputAgoMs").GetInt64(), Is.EqualTo(40));
            Assert.That(handed.GetProperty("personNearAgoMs").GetInt64(), Is.EqualTo(40));
        });
    }

    // Contracase: a window the receipt cannot name (gone, or an editor, a console, BAXY) is not followed.
    [Test]
    public async Task AWindowThatCannotBeNamedIsNotFollowed()
    {
        VisibleControlSurface.RootSnapshot before = Snapshot(PersonWindow, 10, (PersonWindow, Person), (PanelWindow, ControlPanel));
        VisibleControlSurface.RootSnapshot after = Snapshot(
            PersonWindow, 10, (SettingsFrame, FrameHost), (PersonWindow, Person), (PanelWindow, ControlPanel));
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        int looked = 0;
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, timing: Fast, capture: SameImage)
        {
            PopupsOf = window => [],
            RootWindows = window => looked++ == 0 ? before : after,
            DescribeHanded = found => null,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Ver dispositivos e impresoras","window":4660}"""), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
    }
}
