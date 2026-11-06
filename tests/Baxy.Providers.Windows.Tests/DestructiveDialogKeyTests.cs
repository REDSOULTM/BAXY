using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión de la guarda F013 (teclas): the guard of the destructive dialog read only clicks. Enter or space on the
/// focused «Reemplazar» of «¿Reemplazar?» wrote over the file without the person's yes, unless the model declared it
/// (onto, consequence). The key press's preflight reads the control that would take the key (the focus of the window it
/// goes to, by the worker's «focuskind») and judges it with F013's own reading of the dialog. Through the engine, with
/// Core's handler, the real adapters and an owned window as the dialog; the worker is a fake that answers by command.
/// </summary>
[TestFixture]
public sealed class DestructiveDialogKeyTests
{
    private const string ReplaceTitle = "Confirmar Guardar como";
    private static readonly (string Kind, string Name)[] ReplaceDialog =
    [
        ("Text", "prueba.txt ya existe. ¿Quieres reemplazarlo?"),
        ("Button", "Reemplazar"),
        ("Button", "Sí"),
        ("Button", "No"),
        ("CheckBox", "No volver a preguntar"),
    ];

    // Enter or space on the focused affirmative button of a dialog that asks about replacing waits for the yes.
    [TestCase("enter", "Reemplazar")]
    [TestCase("space", "Sí")]
    public void AKeyOnTheFocusedYesOfADestructiveDialogAsks(string key, string focused)
    {
        Pressed pressed = PressInDialog(ReplaceTitle, ReplaceDialog, $$"""{"key":"{{key}}"}""", Focus("Button", focused));

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(pressed.Keys, Is.Zero, "nothing goes before the yes");
            Assert.That(pressed.Commands.Any(command => command.Contains("\"cmd\":\"focuskind\"", StringComparison.Ordinal)),
                Is.True, "the focus was read");
        });
    }

    // The person's yes, given to that same press, lets it go.
    [Test]
    public void TheYesGivenToThatPressLetsItGo()
    {
        Pressed pressed = PressInDialog(
            ReplaceTitle, ReplaceDialog, """{"key":"enter"}""", Focus("Button", "Reemplazar"), confirm: true);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Response.ErrorCode, Is.Not.EqualTo("confirmation_required"));
            Assert.That(pressed.Keys, Is.EqualTo(1));
        });
    }

    // What the key presses there is no yes: the focused «No», or space on a checkbox (it toggles; it presses no button).
    [TestCase("enter", "Button", "No")]
    [TestCase("space", "CheckBox", "No volver a preguntar")]
    public void AKeyThatAnswersNoOrTogglesGoesStraight(string key, string kind, string focused)
    {
        Pressed pressed = PressInDialog(ReplaceTitle, ReplaceDialog, $$"""{"key":"{{key}}"}""", Focus(kind, focused));

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Response.ErrorCode, Is.Not.EqualTo("confirmation_required"));
            Assert.That(pressed.Keys, Is.EqualTo(1));
        });
    }

    // Enter on a control that is no button goes to the dialog's default button, which may be its yes; a focus that
    // cannot be read is not known to be the «No».
    [TestCase("""{"ok":true,"kind":"CheckBox","name":"No volver a preguntar","editable":false,"text":false,"inside":true}""")]
    [TestCase("""{"ok":false,"error":"focus_not_found"}""")]
    [TestCase("""{"ok":true,"kind":"Button","name":"No","editable":false,"text":false,"inside":false}""")]
    public void EnterWhereTheDefaultButtonAnswersAsks(string focus)
    {
        Pressed pressed = PressInDialog(ReplaceTitle, ReplaceDialog, """{"key":"enter"}""", focus);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(pressed.Keys, Is.Zero);
        });
    }

    // Contracase of F013: saving destroys nothing. Enter on «Sí» under «¿Quieres guardar los cambios?» goes straight.
    [Test]
    public void EnterOnTheYesOfADialogThatSavesGoesStraight()
    {
        Pressed pressed = PressInDialog(
            "Bloc de notas",
            [("Text", "¿Quieres guardar los cambios?"), ("Button", "Sí"), ("Button", "No"), ("Button", "Cancelar")],
            """{"key":"enter"}""",
            Focus("Button", "Sí"));

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Response.ErrorCode, Is.Not.EqualTo("confirmation_required"));
            Assert.That(pressed.Keys, Is.EqualTo(1));
        });
    }

    // Enter in a text field of an ordinary window (no dialog) whose fields hold no text: goes, and no look of the window
    // is taken for it (only its focus and, for an undeclared Enter, whether a field holds text).
    [TestCase("""{"key":"enter"}""")]
    [TestCase("""{"key":"enter","target":"text_field"}""")]
    [TestCase("""{"key":"space","onto":"Aceptar"}""")]
    public void EnterInAnOrdinaryWindowGoesStraight(string arguments)
    {
        Pressed pressed = PressInDialog(
            ReplaceTitle, ReplaceDialog, arguments, Focus("Edit", "Nombre de archivo", editable: true), owned: false);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Response.ErrorCode, Is.Not.EqualTo("confirmation_required"));
            Assert.That(pressed.Keys, Is.EqualTo(1));
            Assert.That(pressed.Commands.Any(command => !command.Contains("\"cmd\":\"focuskind\"", StringComparison.Ordinal)
                    && !command.Contains("\"cmd\":\"heldtext\"", StringComparison.Ordinal)),
                Is.False, "no look of the window");
        });
    }

    // Auditoría de falsedades 2026-11-04 (P6): the same undeclared Enter where the worker reads a field of the window
    // holding text, or cannot read the fields, asks, through the real visible controls' adapter.
    [TestCase("""{"ok":true,"held":true}""")]
    [TestCase("""{"ok":false,"error":"held_text_unreadable"}""")]
    [TestCase("""{"ok":true}""")]
    public void AnUndeclaredEnterWhereAFieldHoldsTextAsks(string held)
    {
        Pressed pressed = PressInDialog(
            ReplaceTitle, ReplaceDialog, """{"key":"enter"}""", Focus("Edit", "Nombre de archivo", editable: true),
            owned: false, held: held);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(pressed.Keys, Is.Zero);
        });
    }

    // The model's own word keeps asking as RiskPolicy says (a destructive onto, consequence overwrite), dialog or not;
    // and an onto that RiskPolicy lets go («Reemplazar», «Sí») no longer lowers what the focused control of the dialog
    // would do.
    [TestCase("""{"key":"enter","onto":"Eliminar"}""", false)]
    [TestCase("""{"key":"space","consequence":"overwrite"}""", false)]
    [TestCase("""{"key":"enter","onto":"Reemplazar"}""", true)]
    [TestCase("""{"key":"enter","onto":"Sí"}""", true)]
    public void TheModelsDeclaredPathStillAsks(string arguments, bool owned)
    {
        Pressed pressed = PressInDialog(ReplaceTitle, ReplaceDialog, arguments, Focus("Button", "Sí"), owned: owned);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(pressed.Keys, Is.Zero);
        });
    }

    private static string Focus(string kind, string name, bool editable = false) =>
        "{\"ok\":true,\"kind\":\"" + kind + "\",\"name\":" + JsonSerializer.Serialize(name) + ",\"editable\":"
        + (editable ? "true" : "false") + ",\"text\":" + (editable ? "true" : "false") + ",\"inside\":true}";

    private sealed record Pressed(OperationResponse Response, int Keys, IReadOnlyList<string> Commands);

    // A window owned by another (a dialog, as F013 tells it) or one that is not (owned: false), the key named to it;
    // the worker answers the focus and the view of that window. Synchronous: the windows are made and destroyed by this
    // thread, which answers their messages meanwhile.
    private static Pressed PressInDialog(
        string title,
        (string Kind, string Name)[] shown,
        string arguments,
        string focus,
        bool confirm = false,
        bool owned = true,
        string held = """{"ok":true,"held":false}""")
    {
        nint owner = CreateWindowEx(0x08000080, "STATIC", "BAXY key dialog fixture owner", 0x90000000u, -31000, -31000, 400, 300, 0, 0, 0, 0);
        nint dialog = CreateWindowEx(0x08000080, "STATIC", title, 0x90000000u, -31000, -31000, 300, 120, owned ? owner : 0, 0, 0, 0);
        Assert.That(owner != 0 && dialog != 0, Is.True, $"CreateWindowEx failed: {Marshal.GetLastPInvokeError()}");
        try
        {
            string controls = string.Join(",", shown.Select((control, k) =>
                "{\"kind\":\"" + control.Kind + "\",\"name\":" + JsonSerializer.Serialize(control.Name) + ",\"id\":\"9." + k
                + "\",\"state\":\"\",\"value\":null,\"rect\":{\"x\":10,\"y\":" + (10 + 30 * k) + ",\"w\":80,\"h\":24},\"repeated\":0}"));
            var worker = new ByCommandWorker(
                focus,
                "{\"ok\":true,\"error\":\"\",\"hwnd\":" + (long)dialog + ",\"window\":" + JsonSerializer.Serialize(title)
                + ",\"controls\":[" + controls + "],\"controlCount\":" + shown.Length + ",\"focused\":null}",
                held);
            var visible = new WindowsVisibleControlAdapter(worker, null, null);
            var adapter = new WindowsDesktopInteractionAdapter(
                new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", new FakeDesktopKeyboard(), visible)
            {
                KeyWindows = new Reader(),
            };
            var keys = new Keys(adapter);
            IOperationHandler handler = ExternalCapabilityHandlers.Create(keys, keyWindows: new Reader())
                .Single(candidate => candidate.Definition.Name == "input.key.press");
            using JsonDocument parsed = JsonDocument.Parse(arguments);
            var named = new Dictionary<string, object?>();
            foreach (JsonProperty property in parsed.RootElement.EnumerateObject())
                named[property.Name] = property.Value.GetString();
            named["window"] = (long)dialog;
            JsonElement call = JsonSerializer.SerializeToElement(named);
            OperationResponse response = ComputerUseSpeedTests.Pumped(() => PressThroughEngine(handler, call, confirm));
            return new Pressed(response, keys.Count, worker.Commands);
        }
        finally
        {
            _ = DestroyWindow(dialog);
            _ = DestroyWindow(owner);
        }
    }

    private static async Task<OperationResponse> PressThroughEngine(IOperationHandler handler, JsonElement arguments, bool confirm)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-dialog-key-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                Path.Combine(root, "journal.jsonl"),
                new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
            using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
            var request = new OperationRequest(
                ProtocolTypes.OperationRequest,
                Guid.NewGuid().ToString("D"),
                Guid.NewGuid().ToString("D"),
                Guid.NewGuid().ToString("D"),
                "input.key.press",
                arguments);
            OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);
            return confirm && response.ErrorCode == "confirmation_required"
                ? await engine.ExecuteAsync(
                    request with { ConfirmationToken = response.Result!.Value.GetProperty("token").GetString() },
                    CancellationToken.None)
                : response;
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // The worker: «focuskind» answers the focus; «heldtext» whether a field of the window holds text (auditoría de
    // falsedades 2026-11-04, P6: an undeclared Enter asks while one does); any other command (a look) the view of the
    // dialog.
    private sealed class ByCommandWorker(string focus, string view, string held) : IUiaWorker
    {
        internal List<string> Commands { get; } = [];

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            lock (Commands)
                Commands.Add(commandJson);
            return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(
                commandJson.Contains("\"cmd\":\"focuskind\"", StringComparison.Ordinal) ? focus
                : commandJson.Contains("\"cmd\":\"heldtext\"", StringComparison.Ordinal) ? held
                : view));
        }
    }

    // The provider: its preflight is the real adapter's; pressing is counted, nothing is sent.
    private sealed class Keys(WindowsDesktopInteractionAdapter adapter) : IExternalCapabilityProvider
    {
        public int Count { get; private set; }

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            Count++;
            return ValueTask.FromResult(ExternalJson.Success(
                operation, JsonDocument.Parse("""{"version":1,"accepted":2}""").RootElement.Clone(), effectObserved: true));
        }

        public ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken) =>
            adapter.PreflightAsync(operation, arguments, cancellationToken);

        public bool PreflightMayRaise(string operation, JsonElement arguments) =>
            adapter.PreflightMayRaise(operation, arguments);
    }

    // Every window an ordinary one (K-2 refinada would lower an undeclared Enter there).
    private sealed class Reader : IKeyWindowReader
    {
        public KeyWindowKind KindOf(long? window) => KeyWindowKind.Ordinary;
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("a preflight starts no process");
    }

    [DllImport("user32.dll", EntryPoint = "CreateWindowExW", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern nint CreateWindowEx(uint extendedStyle, string className, string title, uint style, int x, int y,
        int width, int height, nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyWindow(nint window);
}
