using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The click and the bursts that reopen what an opener showed. Estabilización D: the chains of fable/cu-v3-cadena (live on
/// Discord: «andá al canal Cotele» opened the search by Invoke, the worker's net handed the front back in 32 ms and the
/// search closed) are gone: the provider brings the mission's window to the front before its act and keeps it, so every
/// click is pressed with the lease untouched.
/// </summary>
[TestFixture]
public sealed class ComputerUseChainTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private const string Selected =
        "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Buscar\",\"kind\":\"ComboBox\"," +
        "\"controlIdentity\":\"5.1\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false," +
        "\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"method\":\"invoke\"}";

    // The same click, pressed behind, whose window the worker's net saw take the front and handed it back.
    private const string HandedBack =
        "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Buscar\",\"kind\":\"Button\"," +
        "\"controlIdentity\":\"5.1\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false," +
        "\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"method\":\"invoke\",\"frontChanged\":true," +
        "\"frontRestored\":true,\"frontReturnFailed\":0}";

    [TestCase("ComboBox", "", true)]
    [TestCase("Button", "collapsed", true)]
    [TestCase("MenuItem", "collapsed", true)]
    [TestCase("SplitButton", "focused collapsed", true)]
    [TestCase("Button", "", false)]
    [TestCase("MenuItem", "", false)]
    [TestCase("ListItem", "selected", false)]
    [TestCase("Button", "expanded", false)]
    [TestCase("Edit", "focused", false)]
    public void OnlyAComboBoxOrACollapsedControlOpensWhatLivesWhileActive(string kind, string state, bool opens) =>
        Assert.That(WindowsVisibleControlAdapter.OpensWhileActive(kind, state), Is.EqualTo(opens));

    // Review of combos-galerias (finding 3): the only controls a burst may press again to reopen what they showed are a
    // tab and an opener by structure; a button that acts («Nuevo», «Añadir», «Eliminar») or a menu entry never.
    [TestCase("TabItem", "selected", true)]
    [TestCase("ComboBox", "collapsed", true)]
    [TestCase("SplitButton", "collapsed", true)]
    [TestCase("Button", "", false)]
    [TestCase("MenuItem", "", false)]
    [TestCase("SplitButton", "", false)]
    [TestCase("ListItem", "selected", false)]
    public void OnlyATabOrAnOpenerByStructureIsPressedAgainToReopen(string kind, string state, bool again) =>
        Assert.That(WindowsVisibleControlAdapter.OpensAgain(kind, state), Is.EqualTo(again));

    // Finding 3: the opener a click noted holds only for the click right after the one view that followed it; a press
    // that is no opener is never noted, and a text, a key, another click or another mission's look (one more view)
    // takes it away.
    [TestCase(true, 1, true, TestName = "an opener, then its one view: reopened")]
    [TestCase(false, 1, false, TestName = "a button that acts: never")]
    [TestCase(true, 0, false, TestName = "an opener with no view after it: not yet")]
    [TestCase(true, 2, false, TestName = "an opener, then another act and its view: gone")]
    public void TheOpenerHoldsOnlyForTheNextViewAndClick(bool opens, int views, bool reopened)
    {
        WindowsVisibleControlAdapter adapter = Adapter(new OrderedWorker(), new RecordingLease());
        const BindingFlags Private = BindingFlags.NonPublic | BindingFlags.Instance;
        MethodInfo note = typeof(WindowsVisibleControlAdapter).GetMethod("NoteOpener", Private)!;
        MethodInfo take = typeof(WindowsVisibleControlAdapter).GetMethod("TakeOpener", Private)!;
        FieldInfo read = typeof(WindowsVisibleControlAdapter).GetField("_viewsRead", Private)!;
        _ = note.Invoke(adapter, [(nint)4660, "7.1", "Insertar", new HashSet<string>(StringComparer.Ordinal) { "Inicio" }, opens]);
        read.SetValue(adapter, (long)read.GetValue(adapter)! + views);

        object? taken = take.Invoke(adapter, []);
        object? again = take.Invoke(adapter, []);

        Assert.Multiple(() =>
        {
            Assert.That(taken is not null, Is.EqualTo(reopened));
            Assert.That(again, Is.Null, "once at most");
        });
    }

    // Estabilización D (the owner's decision of 2026-10-10): the provider brings the mission's window to the front before
    // its act and keeps it there (IForegroundLease.TakeForMissionAsync, MissionFrontTests), so no click opens a chain any
    // more: a combo box, a collapsed control, a button and a list item are pressed with the lease untouched, and the
    // receipt says nothing of a chain nor of a held front. Before, a combo box or a collapsed control took the chain's
    // front in the person's pause and kept it for the look.
    [TestCase("ComboBox", "collapsed")]
    [TestCase("Button", "collapsed")]
    [TestCase("Button", "")]
    [TestCase("ListItem", "")]
    public void EveryClickIsPressedWithTheLeaseUntouched(string kind, string state)
    {
        WithWindow(window =>
        {
            var lease = new RecordingLease();
            var worker = new OrderedWorker(Selected.Replace("ComboBox", kind, StringComparison.Ordinal));
            WindowsVisibleControlAdapter adapter = Adapter(worker, lease);
            RememberView(adapter, window, Control(5, "5.1", kind, "Buscar", state));

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Buscar", "5.1");

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(lease.Events, Is.Empty);
                Assert.That(receipt.Result?.TryGetProperty("chain", out _), Is.False);
                Assert.That(receipt.Result?.TryGetProperty("frontHeld", out _), Is.False);
                Assert.That(worker.Commands, Has.Count.EqualTo(1));
            });
        });
    }

    // Estabilización D: an arrow, a context menu and a double click are pressed as any click (before, an arrow or a
    // menu was refused behind a person who did not pause; now the provider refuses the whole act before it, when the
    // mission's window cannot be brought to the front in their pause).
    [TestCase("open")]
    [TestCase("menu")]
    [TestCase("double")]
    public void AnArrowAMenuOrADoubleClickIsPressedWithTheLeaseUntouched(string manner)
    {
        WithWindow(window =>
        {
            var lease = new RecordingLease();
            var worker = new OrderedWorker(Selected);
            WindowsVisibleControlAdapter adapter = Adapter(worker, lease);
            RememberView(adapter, window, Control(5, "5.1", "ListItem", "Fotos", "collapsed"));

            _ = adapter.InvokeAsync(
                    "input.visible.click",
                    Json("{\"label\":\"Fotos\",\"controlId\":\"5.1\",\"manner\":\"" + manner + "\",\"window\":" + (long)window + "}"),
                    CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(worker.Commands.Any(command => command.Contains("\"cmd\":\"click\"", StringComparison.Ordinal)), Is.True);
                Assert.That(lease.Events, Is.Empty);
            });
        });
    }

    // Estabilización D: a click whose front the worker's net handed back, followed by a view that shows exactly what the
    // window showed before, is no vanished opening that a later click would take a chain for: the next press of that
    // control goes as any other, with the lease untouched (before, it opened a chain).
    [Test]
    public void AClickWhoseFrontWasHandedBackOpensNoChainNextTime()
    {
        WithWindow(window =>
        {
            var lease = new RecordingLease();
            var worker = new OrderedWorker(HandedBack, HandedBack);
            WindowsVisibleControlAdapter adapter = Adapter(worker, lease);
            ViewControlSpec[] before = [Control(5, "5.1", "Button", "Buscar", string.Empty), Control(6, "6.1", "Text", "Ron92", string.Empty)];
            RememberView(adapter, window, before);

            ExternalCapabilityReceipt first = Click(adapter, window, "Buscar", "5.1");
            RememberView(adapter, window, before);
            ExternalCapabilityReceipt second = Click(adapter, window, "Buscar", "5.1");

            Assert.Multiple(() =>
            {
                Assert.That(first.Verified, Is.True, first.ErrorCode);
                Assert.That(second.Verified, Is.True, second.ErrorCode);
                Assert.That(lease.Events, Is.Empty);
            });
        });
    }

    // Review of menus-efímeros (finding 2), the adapter's glue: «Editar» (a collapsed menu entry) showed «Reemplazar» in
    // a popup of its window, and the click on it came back not found once the popup died with the activation. ONE burst
    // of the lease is asked for, on the opener's window (never on the popup's), whether the popup still lives as one of
    // the opener's or is gone. Contracases: a name the window showed before the opener («Archivo»), and a living window
    // that is none of the opener's popups, are answered not found with the lease untouched.
    [TestCase("Reemplazar", "popup", true, TestName = "not found in the opener's living popup: one burst on the opener's window")]
    [TestCase("Reemplazar", "dead", true, TestName = "not found in the opener's popup that died: one burst on the opener's window")]
    [TestCase("Archivo", "popup", false, TestName = "a name the window showed before the opener: lease untouched")]
    [TestCase("Reemplazar", "foreign", false, TestName = "a living window that is no popup of the opener: lease untouched")]
    public void ANotFoundItemOfTheOpenersPopupOpensOneBurstOnTheOpenersWindow(string item, string where, bool reopens)
    {
        WithWindow(opener => WithWindow(popup =>
        {
            const string Opened =
                "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Editar\",\"kind\":\"MenuItem\"," +
                "\"controlIdentity\":\"9.1\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false," +
                "\"surfaceChanged\":true,\"cascadeStage\":\"uia\",\"method\":\"invoke\"}";
            string notFound =
                "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"," +
                "\"name\":\"" + item + "\",\"controlIdentity\":\"42.7\"}";
            var lease = new RecordingLease { ReopenBurstNoted = true };
            var worker = new OrderedWorker(Opened, notFound);
            WindowsVisibleControlAdapter adapter = new(worker, null, null, elevated: _ => false, capture: (_, _, _) =>
                ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null))
            {
                BurstLease = lease,
                PopupsOf = window => window == opener && where == "popup" ? [popup] : [],
            };
            RememberView(adapter, opener,
                Control(3, "3.1", "MenuItem", "Archivo", string.Empty), Control(9, "9.1", "MenuItem", "Editar", "collapsed"));

            ExternalCapabilityReceipt opening = Click(adapter, opener, "Editar", "9.1");
            // The one view after the opener read the popup.
            List<string> afterOpening = [.. lease.Events];
            RememberView(adapter, popup, Control(7, "42.7", "MenuItem", item, string.Empty));
            FieldInfo read = typeof(WindowsVisibleControlAdapter).GetField("_viewsRead", BindingFlags.NonPublic | BindingFlags.Instance)!;
            read.SetValue(adapter, (long)read.GetValue(adapter)! + 1);
            if (where == "dead")
                _ = DestroyWindow(popup);

            ExternalCapabilityReceipt clicked = Click(adapter, popup, item, "42.7");

            Assert.Multiple(() =>
            {
                Assert.That(opening.Verified, Is.True, opening.ErrorCode);
                List<string> burst = [.. lease.Events.Skip(afterOpening.Count)];
                if (reopens)
                {
                    Assert.That(burst, Is.EqualTo(new[] { "burst " + (long)opener, "restore" }), "one burst, on the opener's window");
                    Assert.That(clicked.ErrorCode, Is.EqualTo("input_user_not_paused"), "the answer is the burst's");
                }
                else
                {
                    Assert.That(burst, Is.Empty, "the lease untouched");
                    Assert.That(clicked.ErrorCode, Is.EqualTo("visible_button_not_found"));
                }

                Assert.That(worker.Commands.Count(command => command.Contains("\"cmd\":\"click\"", StringComparison.Ordinal)),
                    Is.EqualTo(2), "the opener and the item, nothing pressed after");
            });
        }));
    }

    // Ronda 20 (P7, v3-09): «Dibujar» (a tab of a collapsed ribbon) showed its gallery in a popup; the act on the gallery's
    // «Marcador de resaltado: Amarillo, 5 mm» came with a manner (its arrow) and found the popup closed (stale). ONE burst
    // of the lease on the opener's window is asked for, as for an ordinary click. Contracases: the opener itself pressed in
    // a manner (a menu its own second press closes), an item whose name the window showed before the opener, and a press
    // in a manner that worked, leave the lease untouched.
    [TestCase("Marcador de resaltado: Amarillo, 5 mm", "42.7", "visible_control_identity_stale", true, TestName = "a gallery item opened by its arrow, gone stale: one burst on the opener's window")]
    [TestCase("Dibujar", "9.1", "visible_control_identity_stale", false, TestName = "the opener itself in a manner: never")]
    [TestCase("Inicio", "42.7", "visible_control_identity_stale", false, TestName = "a name shown before the opener: never")]
    [TestCase("Marcador de resaltado: Amarillo, 5 mm", "42.7", null, false, TestName = "an arrow that opened: never")]
    public void AnItemPressedInAMannerAfterItsOpenerIsReopenedInOneBurst(string item, string id, string? error, bool reopens)
    {
        WithWindow(opener => WithWindow(popup =>
        {
            const string Opened =
                "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Dibujar\",\"kind\":\"TabItem\"," +
                "\"controlIdentity\":\"9.1\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false," +
                "\"surfaceChanged\":true,\"cascadeStage\":\"uia\",\"method\":\"select\"}";
            string pressed = error is null
                ? "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"" + item + "\",\"kind\":\"SplitButton\"," +
                  "\"controlIdentity\":\"" + id + "\",\"opened\":true,\"method\":\"expand\"}"
                : "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"" + error + "\"," +
                  "\"name\":\"" + item + "\",\"controlIdentity\":\"" + id + "\"}";
            var lease = new RecordingLease { ReopenBurstNoted = true };
            var worker = new OrderedWorker(Opened, pressed);
            WindowsVisibleControlAdapter adapter = new(worker, null, null, elevated: _ => false, capture: (_, _, _) =>
                ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null))
            {
                BurstLease = lease,
                PopupsOf = window => window == opener ? [popup] : [],
            };
            RememberView(adapter, opener,
                Control(3, "3.1", "TabItem", "Inicio", string.Empty), Control(9, "9.1", "TabItem", "Dibujar", string.Empty));

            ExternalCapabilityReceipt opening = Click(adapter, opener, "Dibujar", "9.1");
            RememberView(adapter, popup, Control(18, "42.7", "SplitButton", "Marcador de resaltado: Amarillo, 5 mm", "collapsed"),
                Control(9, "9.1", "TabItem", "Dibujar", "selected"));
            FieldInfo read = typeof(WindowsVisibleControlAdapter).GetField("_viewsRead", BindingFlags.NonPublic | BindingFlags.Instance)!;
            read.SetValue(adapter, (long)read.GetValue(adapter)! + 1);
            List<string> afterOpening = [.. lease.Events];

            ExternalCapabilityReceipt clicked = Click(adapter, popup, item, id, "open");

            Assert.Multiple(() =>
            {
                Assert.That(opening.Verified, Is.True, opening.ErrorCode);
                List<string> bursts = [.. lease.Events.Skip(afterOpening.Count).Where(e => e.StartsWith("burst", StringComparison.Ordinal))];
                if (reopens)
                {
                    Assert.That(bursts, Is.EqualTo(new[] { "burst " + (long)opener }), "one burst, on the opener's window");
                    Assert.That(clicked.ErrorCode, Is.EqualTo("input_user_not_paused"), "the answer is the burst's");
                }
                else
                {
                    Assert.That(bursts, Is.Empty, "no burst");
                    Assert.That(clicked.ErrorCode, Is.EqualTo(error));
                }

                Assert.That(worker.Commands.Count(command => command.Contains("\"cmd\":\"click\"", StringComparison.Ordinal)),
                    Is.EqualTo(2), "the opener and the item, nothing pressed after");
            });
        }));
    }

    // Ronda 20 (P7): a click by a label alone right after an opener presses the one control of the mission's last view the
    // label names, by its identity, so its closed opening is answered stale and reopened, never looked for by a cascade on
    // a closed menu. Contracases: a label that names none, or several, or a view of another window, make up no identity.
    [Test]
    public void ALabelAloneRightAfterAnOpenerIsPressedByTheIdentityItNames()
    {
        WithWindow(window =>
        {
            const string Opened =
                "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Insertar\",\"kind\":\"TabItem\"," +
                "\"controlIdentity\":\"9.1\",\"selected\":true,\"surfaceChanged\":true,\"cascadeStage\":\"uia\",\"method\":\"select\"}";
            const string Pressed =
                "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Tabla\",\"kind\":\"Button\"," +
                "\"controlIdentity\":\"42.7\",\"surfaceChanged\":true,\"cascadeStage\":\"uia\",\"method\":\"invoke\"}";
            var lease = new RecordingLease { ReopenBurstNoted = true };
            var worker = new OrderedWorker(Opened, Pressed);
            WindowsVisibleControlAdapter adapter = Adapter(worker, lease);
            FieldInfo read = typeof(WindowsVisibleControlAdapter).GetField("_viewsRead", BindingFlags.NonPublic | BindingFlags.Instance)!;
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Insertar", string.Empty));
            _ = Click(adapter, window, "Insertar", "9.1");
            read.SetValue(adapter, (long)read.GetValue(adapter)! + 1);
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Insertar", "selected"),
                Control(42, "42.7", "Button", "Tabla", string.Empty), Control(43, "43.1", "Button", "Tabla dinámica", string.Empty),
                Control(44, "44.1", "Button", "Forma libre", string.Empty), Control(45, "45.1", "Button", "Forma básica", string.Empty));

            ExternalCapabilityReceipt clicked = adapter.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"tabla\",\"window\":" + (long)window + "}"), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();
            MethodInfo named = typeof(WindowsVisibleControlAdapter).GetMethod("NamedInView", BindingFlags.NonPublic | BindingFlags.Instance)!;

            Assert.Multiple(() =>
            {
                Assert.That(clicked.Verified, Is.True, clicked.ErrorCode);
                Assert.That(worker.Commands.Last(command => command.Contains("\"cmd\":\"click\"", StringComparison.Ordinal)),
                    Does.Contain("\"controlId\":\"42.7\""), "pressed by the identity the label names exactly");
                Assert.That(named.Invoke(adapter, [window, "dinámica"]), Is.EqualTo("43.1"), "the only one whose name holds it");
                Assert.That(named.Invoke(adapter, [window, "forma"]), Is.Null, "a label that names several");
                Assert.That(named.Invoke(adapter, [window, "Pegar"]), Is.Null, "a label that names none");
                Assert.That(named.Invoke(adapter, [(nint)1, "Tabla"]), Is.Null, "a view of another window");
            });
        });
    }

    // Revision 1 of the branch: a label alone after an opener never presses by identity a control the mind's own rule would
    // not choose. Measured scenario: «Pantalla» was the opener, and «activar el modo oscuro» comes as the label «Modo
    // oscuro» because the only control that holds it is a descriptive Custom whose long sentence is another setting (the
    // automatic schedule). Contracases: the exact name and a short actionable name that holds the label still resolve.
    [Test]
    public void ALabelAloneAfterAnOpenerNeverPressesADescriptiveSentenceThatMentionsIt()
    {
        WithWindow(window =>
        {
            const string Opened =
                "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Pantalla\",\"kind\":\"TabItem\"," +
                "\"controlIdentity\":\"9.1\",\"selected\":true,\"surfaceChanged\":true,\"cascadeStage\":\"uia\",\"method\":\"select\"}";
            var lease = new RecordingLease { ReopenBurstNoted = true };
            var worker = new OrderedWorker(Opened);
            WindowsVisibleControlAdapter adapter = Adapter(worker, lease);
            FieldInfo read = typeof(WindowsVisibleControlAdapter).GetField("_viewsRead", BindingFlags.NonPublic | BindingFlags.Instance)!;
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Pantalla", string.Empty));
            _ = Click(adapter, window, "Pantalla", "9.1");
            read.SetValue(adapter, (long)read.GetValue(adapter)! + 1);
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Pantalla", "selected"),
                Control(50, "50.1", "Custom", "Activar modo oscuro automáticamente al anochecer según tu ubicación y horario", string.Empty),
                Control(52, "52.1", "Button", "Brillo nocturno", string.Empty),
                Control(53, "53.1", "CheckBox", "Ajustar el contraste", string.Empty));

            _ = adapter.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Modo oscuro\",\"window\":" + (long)window + "}"), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();
            MethodInfo named = typeof(WindowsVisibleControlAdapter).GetMethod("NamedInView", BindingFlags.NonPublic | BindingFlags.Instance)!;

            Assert.Multiple(() =>
            {
                Assert.That(worker.Commands.Any(command => command.Contains("\"controlId\":\"50.1\"", StringComparison.Ordinal)), Is.False,
                    "a descriptive sentence that mentions the label is never pressed by identity: " + string.Join(" | ", worker.Commands));
                Assert.That(named.Invoke(adapter, [window, "Modo oscuro"]), Is.Null, "left to the cascade (its exact name, its line)");
                Assert.That(named.Invoke(adapter, [window, "brillo nocturno"]), Is.EqualTo("52.1"), "contracase: the exact name");
                Assert.That(named.Invoke(adapter, [window, "contraste"]), Is.EqualTo("53.1"), "contracase: a short actionable name");
            });
        });
    }

    // Revision 3 of the branch: the label alone after an opener resolves by the mind's find_control as it is, so a case the
    // mind found ambiguous (and therefore sent as a label alone, past none of its guards) is never pressed by identity.
    // Scenario: after «Pantalla», a short switch «Modo oscuro automático» and a long button that also holds «Modo oscuro»;
    // the mind finds both and chooses none, and the switch is another setting the request never names. Contracases:
    // without the long button the switch is the only one (as in the mind, which then weighs it with its guards), and an
    // exact name still wins over the sentences that hold it.
    [Test]
    public void ALabelAloneAfterAnOpenerNeverResolvesWhatTheMindFoundAmbiguous()
    {
        WithWindow(window =>
        {
            const string Opened =
                "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Pantalla\",\"kind\":\"TabItem\"," +
                "\"controlIdentity\":\"9.1\",\"selected\":true,\"surfaceChanged\":true,\"cascadeStage\":\"uia\",\"method\":\"select\"}";
            var lease = new RecordingLease { ReopenBurstNoted = true };
            var worker = new OrderedWorker(Opened);
            WindowsVisibleControlAdapter adapter = Adapter(worker, lease);
            FieldInfo read = typeof(WindowsVisibleControlAdapter).GetField("_viewsRead", BindingFlags.NonPublic | BindingFlags.Instance)!;
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Pantalla", string.Empty));
            _ = Click(adapter, window, "Pantalla", "9.1");
            read.SetValue(adapter, (long)read.GetValue(adapter)! + 1);
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Pantalla", "selected"),
                Control(51, "51.1", "CheckBox", "Modo oscuro automático", string.Empty),
                Control(54, "54.1", "Button",
                    "Programar el modo oscuro para que se active automáticamente al anochecer según tu zona horaria", string.Empty),
                Control(52, "52.1", "Button", "Brillo nocturno", string.Empty));

            _ = adapter.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Modo oscuro\",\"window\":" + (long)window + "}"), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();
            MethodInfo named = typeof(WindowsVisibleControlAdapter).GetMethod("NamedInView", BindingFlags.NonPublic | BindingFlags.Instance)!;
            string? ambiguous = (string?)named.Invoke(adapter, [window, "Modo oscuro"]);
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Pantalla", "selected"),
                Control(51, "51.1", "CheckBox", "Modo oscuro automático", string.Empty),
                Control(52, "52.1", "Button", "Brillo nocturno", string.Empty));
            string? alone = (string?)named.Invoke(adapter, [window, "Modo oscuro"]);
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Pantalla", "selected"),
                Control(51, "51.1", "CheckBox", "Modo oscuro automático", string.Empty),
                Control(54, "54.1", "Button",
                    "Programar el modo oscuro para que se active automáticamente al anochecer según tu zona horaria", string.Empty),
                Control(55, "55.1", "Button", "Modo oscuro", string.Empty));
            string? exact = (string?)named.Invoke(adapter, [window, "Modo oscuro"]);

            Assert.Multiple(() =>
            {
                Assert.That(worker.Commands.Any(command => command.Contains("\"controlId\":\"51.1\"", StringComparison.Ordinal)
                        || command.Contains("\"controlId\":\"54.1\"", StringComparison.Ordinal)), Is.False,
                    "an ambiguous label is never pressed by identity: " + string.Join(" | ", worker.Commands));
                Assert.That(ambiguous, Is.Null, "two actionables hold it: left to the cascade");
                Assert.That(alone, Is.EqualTo("51.1"), "contracase: the only one that holds it, as the mind finds it");
                Assert.That(exact, Is.EqualTo("55.1"), "contracase: the exact name");
            });
        });
    }

    // Revision 1 of the branch: an identity the adapter took from the label itself that fails before any effect leaves the
    // label to its ordinary cascade. Contracases: the same failure on an identity the view handed the mind is answered as
    // is, and a failure that may come after the press began is never followed by another press.
    [TestCase(true, "visible_control_label_mismatch", true, TestName = "identity from the label alone, nothing pressed: the cascade follows")]
    [TestCase(false, "visible_control_label_mismatch", false, TestName = "identity the mind sent: answered as is")]
    [TestCase(true, "visible_click_failed", false, TestName = "identity from the label alone, press may have begun: answered as is")]
    public void AnIdentityTakenFromALabelAloneThatFailsBeforeAnEffectFallsToTheCascade(bool labelAlone, string error, bool cascades)
    {
        WithWindow(window =>
        {
            const string Opened =
                "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Insertar\",\"kind\":\"TabItem\"," +
                "\"controlIdentity\":\"9.1\",\"selected\":true,\"surfaceChanged\":true,\"cascadeStage\":\"uia\",\"method\":\"select\"}";
            string failed =
                "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"" + error + "\",\"name\":\"Tabla\"," +
                "\"kind\":\"Button\",\"controlIdentity\":\"42.7\",\"cascadeStage\":\"uia\"}";
            var lease = new RecordingLease { ReopenBurstNoted = true };
            var worker = new OrderedWorker(Opened, failed);
            WindowsVisibleControlAdapter adapter = Adapter(worker, lease);
            FieldInfo read = typeof(WindowsVisibleControlAdapter).GetField("_viewsRead", BindingFlags.NonPublic | BindingFlags.Instance)!;
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Insertar", string.Empty));
            _ = Click(adapter, window, "Insertar", "9.1");
            read.SetValue(adapter, (long)read.GetValue(adapter)! + 1);
            RememberView(adapter, window, Control(9, "9.1", "TabItem", "Insertar", "selected"),
                Control(42, "42.7", "Button", "Tabla", string.Empty));

            _ = labelAlone
                ? adapter.InvokeAsync(
                        "input.visible.click", Json("{\"label\":\"Tabla\",\"window\":" + (long)window + "}"), CancellationToken.None)
                    .AsTask().GetAwaiter().GetResult()
                : Click(adapter, window, "Tabla", "42.7");
            int pressed = worker.Commands.FindLastIndex(command => command.Contains("\"controlId\":\"42.7\"", StringComparison.Ordinal));

            Assert.Multiple(() =>
            {
                Assert.That(pressed, Is.GreaterThanOrEqualTo(0), "pressed by the identity first");
                Assert.That(worker.Commands.Count > pressed + 1, Is.EqualTo(cascades), string.Join(" | ", worker.Commands));
            });
        });
    }

    // Encargo V (banco e2, c7): the worker found the control the label names by a word of its name, beyond the view, and
    // refused it, since that name joins a voice channel and the label does not say so. The click answers that refusal
    // with the control's name and no effect, and no later stage (OCR, tooltip, vision, the pointer) presses it. The click
    // carries RiskPolicy's own pattern (the worker's Test-AsksMore).
    [TestCase(true, TestName = "by label alone: named, and no later stage presses it")]
    [TestCase(false, TestName = "by identity: named, answered as is")]
    public void AControlThatAsksMoreThanItsLabelIsNamedAndNotPressed(bool labelAlone)
    {
        WithWindow(window =>
        {
            const string Refused =
                "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_control_needs_confirmation\"," +
                "\"name\":\"Cotele, Canal de voz, Choche\",\"kind\":\"ListItem\",\"controlIdentity\":\"42.6\"}";
            var lease = new RecordingLease();
            var worker = new OrderedWorker(Refused);
            WindowsVisibleControlAdapter adapter = Adapter(worker, lease);
            RememberView(adapter, window, Control(3, "42.3", "Button", "Buscar", string.Empty));

            ExternalCapabilityReceipt receipt = labelAlone
                ? adapter.InvokeAsync(
                        "input.visible.click", Json("{\"label\":\"cotele\",\"window\":" + (long)window + "}"), CancellationToken.None)
                    .AsTask().GetAwaiter().GetResult()
                : Click(adapter, window, "cotele", "42.6");
            int pressed = worker.Commands.FindIndex(command => command.Contains("\"cmd\":\"click\"", StringComparison.Ordinal));

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_needs_confirmation"));
                Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.False);
                Assert.That(receipt.Result?.GetProperty("name").GetString(), Is.EqualTo("Cotele, Canal de voz, Choche"));
                Assert.That(pressed, Is.GreaterThanOrEqualTo(0), string.Join(" | ", worker.Commands));
                Assert.That(worker.Commands[pressed], Does.Contain("\"asks\":{\"pattern\":"));
                Assert.That(worker.Commands.Skip(pressed + 1), Is.Empty, string.Join(" | ", worker.Commands));
            });
        });
    }

    private static ExternalCapabilityReceipt Click(WindowsVisibleControlAdapter adapter, nint window, string label, string id, string? manner = null) =>
        adapter.InvokeAsync(
                "input.visible.click",
                Json("{\"label\":\"" + label + "\",\"controlId\":\"" + id + "\",\"window\":" + (long)window
                    + (manner is null ? string.Empty : ",\"manner\":\"" + manner + "\"") + "}"),
                CancellationToken.None)
            .AsTask().GetAwaiter().GetResult();

    private static WindowsVisibleControlAdapter Adapter(OrderedWorker worker, RecordingLease lease) =>
        new(worker, null, null, elevated: _ => false, capture: (_, _, _) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null))
        {
            BurstLease = lease,
        };

    // An off-screen window of this test that takes no activation: alive for the adapter, never the person's.
    private static void WithWindow(Action<nint> test)
    {
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY chain fixture", 0x90000000u,
            -31000, -31000, 200, 120, 0, 0, 0, 0);
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            test(window);
        }
        finally
        {
            _ = DestroyWindow(window);
        }
    }

    internal readonly record struct ViewControlSpec(int Index, string Id, string Kind, string Name, string State);

    private static ViewControlSpec Control(int index, string id, string kind, string name, string state) =>
        new(index, id, kind, name, state);

    private static List<WindowsVisibleControlAdapter.ViewControl> Controls(ViewControlSpec[] specs)
    {
        var controls = new List<WindowsVisibleControlAdapter.ViewControl>();
        foreach (ViewControlSpec spec in specs)
        {
            controls.Add(new WindowsVisibleControlAdapter.ViewControl
            {
                Index = spec.Index,
                Id = spec.Id,
                Kind = spec.Kind,
                Name = spec.Name,
                State = spec.State,
            });
        }

        return controls;
    }

    // The last view, as input.visible.controls leaves it.
    private static void RememberView(WindowsVisibleControlAdapter adapter, nint window, params ViewControlSpec[] specs)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [window, Controls(specs)], null)!;
        field.SetValue(adapter, view);
    }

    // A lease that records what the adapter asks of it.
    private sealed class RecordingLease : IForegroundLease
    {
        internal List<string> Events { get; } = [];

        // Only a test of the reopening burst lets a plain burst be asked for: it is noted and refused (the person does
        // not pause), so nothing is pressed nor marked for the worker's net.
        internal bool ReopenBurstNoted { get; init; }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken)
        {
            if (!ReopenBurstNoted)
                throw new AssertionException("a click acquires no plain burst");
            Events.Add("burst " + (long)window);
            return ValueTask.FromResult<IInputBurst>(new ChainBurst(this, "input_user_not_paused"));
        }

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("a click runs no helper");

        private sealed class ChainBurst(RecordingLease lease, string? refusal) : IInputBurst
        {
            public string? Refusal => refusal;

            public long WaitedMs => 600;

            public bool UserActed => false;

            public bool Restore()
            {
                lease.Events.Add("restore");
                return true;
            }
        }
    }

    // A worker that answers in order.
    private sealed class OrderedWorker(params string[] answers) : IUiaWorker
    {
        private readonly Queue<string> _answers = new(answers);

        internal List<string> Commands { get; } = [];

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Commands.Add(commandJson);
            return ValueTask.FromResult<JsonDocument?>(_answers.Count == 0 ? null : JsonDocument.Parse(_answers.Dequeue()));
        }
    }

    [DllImport("user32.dll", EntryPoint = "CreateWindowExW",
        CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern nint CreateWindowEx(uint extendedStyle, string className,
        string title, uint style, int x, int y, int width, int height,
        nint parent, nint menu, nint instance, nint parameter);

    // Menús efímeros (pasada r15b t-form-2): «Reemplazar» was shown in the popup host «Editar» opened (another top-level
    // window of the application) and failed as not found once it died; the burst reopens «Editar». Its contracases: a
    // name the window showed before the opener, the opener itself, an error that is no missing item, and a living window
    // that is none of the opener's popups.
    [TestCase("visible_button_not_found", "Reemplazar", "42.7", 5000, false, new long[0], true, TestName = "popup died, item not found: reopened")]
    [TestCase("visible_control_identity_stale", "Reemplazar", "42.7", 5000, true, new long[] { 5000 }, true, TestName = "item in a living popup of the opener: reopened")]
    [TestCase("visible_button_not_found", "Reemplazar", "42.7", 4660, true, new long[0], true, TestName = "item in the opener's own window: reopened")]
    [TestCase("visible_button_not_found", "Reemplazar", "42.7", 7777, true, new long[] { 5000 }, false, TestName = "a living window that is no popup of the opener: never")]
    [TestCase("visible_button_not_found", "Archivo", "42.7", 5000, false, new long[0], false, TestName = "a name shown before the opener: never")]
    [TestCase("visible_button_not_found", "Editar", "9.1", 5000, false, new long[0], false, TestName = "the opener itself: never")]
    [TestCase("visible_click_failed", "Reemplazar", "42.7", 5000, false, new long[0], false, TestName = "another failure: never")]
    [TestCase(null, "Reemplazar", "42.7", 5000, false, new long[0], false, TestName = "a press that worked: never")]
    public void AnItemOfTheOpenersOpeningThatDiedIsReopenedOnlyThere(
        string? error, string label, string controlId, long itemWindow, bool alive, long[] popups, bool reopens)
    {
        var namesBefore = new HashSet<string>(StringComparer.Ordinal) { "Archivo", "Editar", "Ver" };

        bool decided = WindowsVisibleControlAdapter.ReopensShownItem(
            error, label, controlId, (nint)itemWindow, 4660, "9.1", namesBefore, alive, [.. popups.Select(popup => (nint)popup)]);

        Assert.That(decided, Is.EqualTo(reopens));
    }

    [DllImport("user32.dll", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyWindow(nint window);
}
