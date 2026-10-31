using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Child = Baxy.Providers.Windows.External.CommonFileDialog.ChildWindow;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ajuste c3 (E017): Windows' common file dialog told by its structure, in any application and language, and the receipt
/// of the act that confirms it judged on the dialog. The child windows are the ones read live on the notebook (30-10,
/// Windows 11 Notepad 11 in Spanish, «Guardar como»: win32_dump of the dialog), cut to what matters.
/// </summary>
[TestFixture]
public sealed class CommonFileDialogTests
{
    private const nint Dialog = 3868442;

    // Notepad's «Guardar como» as Win32 gave it: the name combo's Edit (1001) under a FloatNotifySink, the type combo with
    // no Edit, the shell's view, the address band's breadcrumb, the search box and the push buttons IDOK and IDCANCEL.
    internal static Child[] SaveAs(string name = "lista pilas, cables", string address = "Dirección: C:\\Users\\usuario\\BAXY-bench") =>
    [
        new(12519206, Dialog, "DUIViewWndClassName", 0, true, ""),
        new(984624, 12519206, "DirectUIHWND", 0, true, ""),
        new(2164232, 984624, "FloatNotifySink", 0, true, ""),
        new(394886, 2164232, "ComboBox", 0, true, ""),
        new(1967706, 394886, "Edit", 1001, true, name),
        new(4850470, 15730192, "SHELLDLL_DefView", 1121, true, ""),
        new(15730192, 984624, "CtrlNotifySink", 0, true, ""),
        new(10290892, 984624, "FloatNotifySink", 0, true, ""),
        new(1705778, 10290892, "ComboBox", 0, true, ""),
        new(5965656, Dialog, "ComboBox", 0, true, ""),
        new(13895204, Dialog, "Button", 1, true, "&Guardar"),
        new(1377872, Dialog, "Button", 2, true, "Cancelar"),
        new(9635136, Dialog, "Button", 1038, false, "Ay&uda"),
        new(919268, Dialog, "WorkerW", 0, true, ""),
        new(7800376, 919268, "ReBarWindow32", 40965, true, ""),
        new(329400, 7800376, "Address Band Root", 41477, true, ""),
        new(8128288, 329400, "msctls_progress32", 0, true, ""),
        new(329392, 8128288, "Breadcrumb Parent", 0, true, ""),
        new(1836416, 329392, "ToolbarWindow32", 1001, true, address),
        new(11142706, 7800376, "UniversalSearchBand", 0, true, ""),
        new(9701100, 11142706, "Search Box", 0, true, ""),
        new(16254608, 9701100, "Edit", 0, true, ""),
    ];

    [Test]
    public void ASaveDialogIsToldByItsStructureWithItsNameFolderAndButtons()
    {
        CommonFileDialog.Facts? facts = CommonFileDialog.Recognize(Dialog, "#32770", SaveAs());

        Assert.That(facts, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(facts!.Accept, Is.EqualTo((nint)13895204));
            Assert.That(facts.AcceptText, Is.EqualTo("Guardar"));
            Assert.That(facts.Cancel, Is.EqualTo((nint)1377872));
            Assert.That(facts.NameField, Is.EqualTo((nint)1967706), "not the search box's edit");
            Assert.That(facts.Name, Is.EqualTo("lista pilas, cables"));
            Assert.That(facts.Folder, Is.EqualTo("C:\\Users\\usuario\\BAXY-bench"));
            Assert.That(facts.Path, Is.EqualTo("C:\\Users\\usuario\\BAXY-bench\\lista pilas, cables"));
        });
    }

    // A message box (#32770 with no shell view), an ordinary window and a dialog with no IDOK are no file dialog; the
    // explorer-style dialog of GetSaveFileName (cmb13 1148 holding its Edit, edt1 1152) is one.
    [Test]
    public void OnlyADialogWithTheShellsViewAndIdOkIsAFileDialog()
    {
        Child[] messageBox = [new(1377804, Dialog, "Button", 1, true, "Aceptar"), new(394812, Dialog, "DirectUIHWND", 0, true, "")];
        Child[] noOk = [.. SaveAs().Where(static child => child.Id != 1)];
        Child[] legacy =
        [
            new(10, Dialog, "SHELLDLL_DefView", 1121, true, ""),
            new(11, Dialog, "ComboBox", 1137, true, "BAXY-bench"),
            new(12, Dialog, "ComboBox", 0x047C, true, ""),
            new(13, 12, "Edit", 1001, true, "informe.txt"),
            new(14, Dialog, "Button", 1, true, "&Guardar"),
            new(15, Dialog, "Button", 2, true, "Cancelar"),
        ];

        CommonFileDialog.Facts? old = CommonFileDialog.Recognize(Dialog, "#32770", legacy);

        Assert.Multiple(() =>
        {
            Assert.That(CommonFileDialog.Recognize(Dialog, "#32770", messageBox), Is.Null);
            Assert.That(CommonFileDialog.Recognize(Dialog, "Notepad", SaveAs()), Is.Null);
            Assert.That(CommonFileDialog.Recognize(Dialog, "#32770", noOk), Is.Null);
            Assert.That(old?.NameField, Is.EqualTo((nint)13));
            Assert.That(old?.Folder, Is.Null, "the explorer-style dialog shows the folder's name, not its path");
            Assert.That(old?.Path, Is.Null);
        });
    }

    // The folder is the path the address shows from its drive or share on, whatever the label before it says; a place
    // that is no folder of the disk gives none.
    [TestCase("Dirección: C:\\Users\\usuario\\BAXY-bench", "C:\\Users\\usuario\\BAXY-bench")]
    [TestCase("Address: D:\\BAXYeval\\dlg_prueba", "D:\\BAXYeval\\dlg_prueba")]
    [TestCase("アドレス: C:\\", "C:\\")]
    [TestCase("Dirección: \\\\servidor\\compartida\\informes", "\\\\servidor\\compartida\\informes")]
    [TestCase("Dirección: \u200eC:\\Users\\usuario\u200e", "C:\\Users\\usuario")]
    [TestCase("Dirección: Este equipo", null)]
    [TestCase("Dirección: Bibliotecas\\Documentos", null)]
    [TestCase("", null)]
    public void TheFolderIsThePathTheAddressShows(string address, string? folder) =>
        Assert.That(CommonFileDialog.FolderOf(address), Is.EqualTo(folder));

    [TestCase("C:\\Users\\usuario\\BAXY-bench", "lista.txt", "C:\\Users\\usuario\\BAXY-bench\\lista.txt")]
    [TestCase("C:\\Users\\usuario\\OneDrive", "D:\\BAXYeval\\dlg_prueba\\np\\lista.txt", "D:\\BAXYeval\\dlg_prueba\\np\\lista.txt")]
    [TestCase(null, "D:\\x\\lista.txt", "D:\\x\\lista.txt")]
    [TestCase("C:\\a", "\"lista.txt\"", "C:\\a\\lista.txt")]
    [TestCase("C:\\a\\b", "..\\lista.txt", "C:\\a\\lista.txt")]
    [TestCase(null, "lista.txt", null)]
    [TestCase("C:\\a", "\"uno.txt\" \"dos.txt\"", null)]
    [TestCase("C:\\a", "  ", null)]
    [TestCase("C:\\a", "\\lista.txt", null)]
    public void TheNameFieldGivesAWholePath(string? folder, string name, string? path) =>
        Assert.That(CommonFileDialog.Resolve(folder, name), Is.EqualTo(path));

    // The button pressed is the dialog's IDOK by its window (UI Automation's runtime id «42.<handle>») or by its caption.
    [TestCase("42.13895204", "Guardar", "Button", true)]
    [TestCase("42.1377872", "Cancelar", "Button", false)]
    [TestCase(null, "Guardar", "Button", true)]
    [TestCase("vision.68.48", "guardar", null, true)]
    [TestCase("42.1967706", "Nombre de archivo:", "Edit", false)]
    [TestCase(null, "Guardar", "TreeItem", false)]
    public void TheAcceptIsTheDialogsIdOk(string? identity, string name, string? kind, bool accept) =>
        Assert.That(CommonFileDialog.PressedAccept(Facts(), identity, name, kind), Is.EqualTo(accept));

    // Live on the notebook (30-10): «Guardar» pressed with a name the dialog refused opened an error box over it, and the
    // press came back completed (dialogOpened); in E017 (pc-c3r9b_1-sB s0) the dialog closed and the file went to the
    // dialog's last folder, told completed. The receipt is the dialog's ending.
    [TestCase("Closed", true, null, true)]
    [TestCase("Closed", false, "file_dialog_file_missing", false)]
    [TestCase("Blocked", null, "file_dialog_answered_by_another_window", false)]
    [TestCase("Open", null, "file_dialog_still_open", false)]
    public void TheConfirmationsReceiptIsTheDialogsEnding(string end, bool? exists, string? error, bool verified)
    {
        CommonFileDialog.Ending ending = Enum.Parse<CommonFileDialog.Ending>(end);
        ExternalCapabilityReceipt pressed = ExternalJson.Success("input.visible.click", Json(
            """{"ok":true,"name":"Guardar","kind":"Button","controlIdentity":"42.13895204","dialogOpened":true,"effectObserved":true}"""));
        var outcome = new CommonFileDialog.Outcome(ending, "C:\\Users\\usuario\\BAXY-bench\\lista.txt", exists,
            ending == CommonFileDialog.Ending.Blocked ? "Guardar como" : null,
            ending == CommonFileDialog.Ending.Open ? "C:\\Users\\usuario\\Documents" : null, null);

        ExternalCapabilityReceipt receipt = CommonFileDialog.Apply(pressed, Facts(), outcome, next: true);

        JsonElement said = receipt.Result!.Value.GetProperty("fileDialog");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.EqualTo(verified));
            Assert.That(receipt.ErrorCode, Is.EqualTo(error));
            Assert.That(said.GetProperty("closed").GetBoolean(), Is.EqualTo(ending == CommonFileDialog.Ending.Closed));
            Assert.That(said.GetProperty("path").GetString(), Is.EqualTo("C:\\Users\\usuario\\BAXY-bench\\lista.txt"));
            Assert.That(receipt.Result!.Value.TryGetProperty("next", out _), Is.EqualTo(!verified));
            Assert.That(receipt.EffectMayHaveOccurred, Is.EqualTo(!verified));
        });
    }

    // A press whose own post-read was lost (visible_click_postread_unread) whose dialog closed with the file there is the
    // act done; the same press with the dialog answered by an error box stays a failure.
    [Test]
    public void ALostPostReadIsSettledByTheDialog()
    {
        ExternalCapabilityReceipt unread = ExternalJson.FailureAfterEffect("input.visible.click", "visible_click_postread_unread");
        var closed = new CommonFileDialog.Outcome(CommonFileDialog.Ending.Closed, "C:\\a\\lista.txt", true, null, null, null);
        var blocked = new CommonFileDialog.Outcome(CommonFileDialog.Ending.Blocked, "C:\\a\\lista.txt", null, "Guardar como", null, null);

        ExternalCapabilityReceipt done = CommonFileDialog.Apply(unread, Facts(), closed, next: false);
        ExternalCapabilityReceipt answered = CommonFileDialog.Apply(unread, Facts(), blocked, next: false);

        Assert.Multiple(() =>
        {
            Assert.That(done.Verified, Is.True);
            Assert.That(done.ErrorCode, Is.Null);
            Assert.That(done.Result!.Value.GetProperty("fileDialog").GetProperty("exists").GetBoolean(), Is.True);
            Assert.That(answered.ErrorCode, Is.EqualTo("file_dialog_answered_by_another_window"));
            Assert.That(answered.Result!.Value.TryGetProperty("next", out _), Is.False, "the aid off says no next");
        });
    }

    // The adapter judges a click on the dialog's IDOK: by the pressed control the receipt names, or by the label asked
    // when the receipt names none.
    [TestCase("""{"controlIdentity":"42.13895204","name":"Guardar","kind":"Button"}""", """{"label":"Guardar"}""", true)]
    [TestCase("""{"controlIdentity":"42.1377872","name":"Cancelar","kind":"Button"}""", """{"label":"Cancelar"}""", false)]
    [TestCase(null, """{"label":"Guardar","index":29}""", true)]
    [TestCase(null, """{"label":"Documentos","manner":"open"}""", false)]
    public void TheClickOnTheAcceptIsKnownFromItsReceiptOrItsLabel(string? result, string arguments, bool accept) =>
        Assert.That(WindowsVisibleControlAdapter.PressedAccept(Facts(), result is null ? null : Json(result), Json(arguments)),
            Is.EqualTo(accept));

    // Live (Paint's «Guardar como»): «Guardar» by its label alone was ambiguous; the same click goes to IDOK by its identity.
    // A click with its own index, control or manner, or by another label, is left as it was.
    [TestCase("""{"label":"Guardar","window":1771072}""", true)]
    [TestCase("""{"label":"guardar"}""", true)]
    [TestCase("""{"label":"Guardar","index":16}""", false)]
    [TestCase("""{"label":"Guardar","manner":"menu"}""", false)]
    [TestCase("""{"label":"Cancelar"}""", false)]
    public void AnAmbiguousAcceptGoesToIdOkByItsIdentity(string arguments, bool retried)
    {
        JsonElement? again = WindowsVisibleControlAdapter.AcceptByIdentity(Facts(), Json(arguments));

        Assert.That(again?.GetProperty("controlId").GetString(), Is.EqualTo(retried ? "42.13895204" : null));
    }

    // Live (Chrome, 30-10): the dialog Chrome shows from another of its processes is the browser window's: the look goes to
    // the file dialog the window owns; not to one another window owns, nor to an owned window that is no file dialog.
    [Test]
    public void TheFileDialogAWindowOwnsIsItsWhateverProcessDrawsIt()
    {
        var owners = new Dictionary<nint, nint> { [50] = 10, [60] = 10, [70] = 20 };
        var dialogs = new HashSet<nint> { 60, 70 };
        nint Owned(nint owner) => CommonFileDialog.OwnedBy(owner, [50, 60, 70, 10], top => owners.GetValueOrDefault(top), dialogs.Contains);

        Assert.Multiple(() =>
        {
            Assert.That(Owned(10), Is.EqualTo((nint)60), "the file dialog, not the other owned window (50)");
            Assert.That(Owned(20), Is.EqualTo((nint)70));
            Assert.That(Owned(30), Is.EqualTo((nint)0));
            Assert.That(Owned(0), Is.EqualTo((nint)0));
        });
    }

    // A look writes the dialog's facts with the indexes it gave the name field and IDOK (UI Automation's «42.<handle>»).
    [Test]
    public void ALookWritesTheDialogsFactsAndItsIndexes()
    {
        var controls = new List<WindowsVisibleControlAdapter.ViewControl>
        {
            new() { Index = 22, Kind = "Edit", Name = "Nombre de archivo:", Id = "42.1967706" },
            new() { Index = 29, Kind = "Button", Name = "Guardar", Id = "42.13895204" },
        };

        JsonElement written = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            WindowsVisibleControlAdapter.WriteFileDialog(writer, Facts(), controls);
            writer.WriteEndObject();
        });

        Assert.That(written.GetProperty("fileDialog").GetRawText(), Is.EqualTo(
            """{"folder":"C:\\Users\\usuario\\BAXY-bench","name":"lista pilas, cables","nameIndex":22,"path":"C:\\Users\\usuario\\BAXY-bench\\lista pilas, cables","accept":"Guardar","acceptIndex":29}"""));
    }

    private static CommonFileDialog.Facts Facts() => CommonFileDialog.Recognize(Dialog, "#32770", SaveAs())!;

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();
}
