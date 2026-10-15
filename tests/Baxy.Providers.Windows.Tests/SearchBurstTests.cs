using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The search burst (goal v3 point 0, fix 3; the review's compound operation): open, type and choose go in one burst of
/// the lease inside a pause of the person, the result chosen by its identity on a look read inside the burst. Fakes for
/// the lease, the clock and the acts: the whole sequence, the person who types in the middle, the ceiling that runs out,
/// the result that is not there (nothing pressed), a result that reaches a person (pressed only when the invocation
/// names it), an opening that did not take the keyboard, and a person who never pauses.
/// </summary>
[TestFixture]
public sealed class SearchBurstTests
{
    private const nint Window = 4660;

    private static readonly WindowsVisibleControlAdapter.ViewControl Opener = Control("5.1", "Button", "Buscar o iniciar una conversación");
    private static readonly WindowsVisibleControlAdapter.ViewControl Composer = Control("6.1", "Edit", "Enviar mensaje a #general");
    private static readonly WindowsVisibleControlAdapter.ViewControl SwitcherBox = Control("9.1", "Edit", "Busca servidores, canales o MD", "focused");

    [Test]
    public void TheWholeSequenceGoesInOneBurstAndChoosesTheResultByItsIdentity()
    {
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks =
            [
                [Opener, Composer, SwitcherBox],
                [Opener, Composer, SwitcherBox, Control("12.4", "ListItem", "Cotele"), Control("12.5", "ListItem", "Cotele-memes")],
            ],
        };

        ExternalCapabilityReceipt receipt = Run(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(acts.Calls, Is.EqualTo(new[] { "open 5.1", "look", "type Cotele", "look", "choose 12.4 Cotele" }));
            Assert.That(lease.Events, Is.EqualTo(new[] { "acquire " + (long)Window, "restore" }));
            Assert.That(lease.Events.Count(item => item == "restore"), Is.EqualTo(1), "the front went back once, at the end");
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("name").GetString(), Is.EqualTo("Cotele"));
            Assert.That(result.GetProperty("restored").GetBoolean(), Is.True);
            Assert.That(
                result.GetProperty("acts").EnumerateArray().Select(act => act.GetProperty("operation").GetString()),
                Is.EqualTo(new[] { "input.visible.click", "input.text.type", "input.visible.click" }));
            Assert.That(result.GetProperty("acts").EnumerateArray().All(act => act.GetProperty("ok").GetBoolean()), Is.True);
        });
    }

    // What the search listed after the text goes before what the window already showed with the same name (a server in
    // its side bar).
    [Test]
    public void ANewResultGoesBeforeAControlTheWindowAlreadyShowed()
    {
        var lease = new Lease();
        WindowsVisibleControlAdapter.ViewControl sideBar = Control("3.1", "ListItem", "Cotele");
        var acts = new Acts(lease)
        {
            Looks = [[Opener, sideBar, SwitcherBox], [Opener, sideBar, SwitcherBox, Control("12.4", "ListItem", "Cotele")]],
        };

        ExternalCapabilityReceipt receipt = Run(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(acts.Calls[^1], Is.EqualTo("choose 12.4 Cotele"));
        });
    }

    // The person types while the burst types: the burst stops at their first input, nothing is chosen, and the front and
    // the cursor go back at once.
    [Test]
    public void APersonWhoTypesInTheMiddleStopsTheBurstAndGetsTheFrontBack()
    {
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[Opener, SwitcherBox], [Opener, SwitcherBox, Control("12.4", "ListItem", "Cotele")]],
            OnType = () => lease.PersonActs(),
        };

        ExternalCapabilityReceipt receipt = Run(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(acts.Calls, Has.None.StartsWith("choose"));
            Assert.That(acts.Calls.Count(call => call == "look"), Is.EqualTo(1), "no look after their input");
            Assert.That(lease.Events, Is.EqualTo(new[] { "acquire " + (long)Window, "restore" }));
        });
    }

    // The ceiling runs out before the text: nothing more is sent and the front goes back.
    [Test]
    public void TheCeilingThatRunsOutEndsTheBurstBeforeTheNextSubAct()
    {
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[Opener, SwitcherBox]],
            OnOpen = () => lease.Clock.Advance(SearchBurst.CapMs + 1),
        };

        ExternalCapabilityReceipt receipt = Run(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(SearchBurst.CapReached));
            Assert.That(acts.Calls, Is.EqualTo(new[] { "open 5.1" }));
            Assert.That(lease.Events, Is.EqualTo(new[] { "acquire " + (long)Window, "restore" }));
        });
    }

    // No result names the destination while the search fills its list: nothing is pressed after the text (never an
    // Enter blind), the looks stop at the ceiling, and the receipt says the result was not there.
    [Test]
    public void AResultThatIsNotThereIsNeverPressed()
    {
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[Opener, SwitcherBox], [Opener, SwitcherBox, Control("12.4", "ListItem", "General")]],
        };

        ExternalCapabilityReceipt receipt = Run(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(SearchBurst.ResultNotFound));
            Assert.That(acts.Calls, Has.None.StartsWith("choose"));
            Assert.That(acts.Calls.Count(call => call.StartsWith("type", StringComparison.Ordinal)), Is.EqualTo(1));
            Assert.That(lease.Clock.NowMs, Is.GreaterThanOrEqualTo(SearchBurst.CapMs));
            JsonElement last = receipt.Result!.Value.GetProperty("acts").EnumerateArray().Last();
            Assert.That(last.GetProperty("error").GetString(), Is.EqualTo(SearchBurst.ResultNotFound));
            Assert.That(receipt.Result!.Value.GetProperty("seen").EnumerateArray().Select(name => name.GetString()),
                Is.EqualTo(new[] { "General" }), "auditoría B1: the names it saw");
            Assert.That(lease.Events, Is.EqualTo(new[] { "acquire " + (long)Window, "restore" }));
        });
    }

    // Auditoría B1: a result that only holds the search («Cotele (canal de voz)» for «Cotele») is never pressed for it;
    // the burst says it saw it, and the model names it with «choose», which RiskPolicy confirmed (a voice channel
    // reaches people).
    [TestCase(null, false)]
    [TestCase("Cotele (canal de voz)", true)]
    public void AResultThatOnlyHoldsTheSearchIsPressedOnlyWhenTheInvocationNamesIt(string? choose, bool pressed)
    {
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[Opener, SwitcherBox], [Opener, SwitcherBox, Control("12.4", "ListItem", "Cotele (canal de voz)")]],
        };

        ExternalCapabilityReceipt receipt = Run(lease, acts, choose);

        Assert.Multiple(() =>
        {
            Assert.That(acts.Calls.Any(call => call.StartsWith("choose", StringComparison.Ordinal)), Is.EqualTo(pressed));
            Assert.That(receipt.ErrorCode, Is.EqualTo(pressed ? null : SearchBurst.ResultNotFound));
            if (!pressed)
            {
                Assert.That(receipt.Result!.Value.GetProperty("seen").EnumerateArray().Select(name => name.GetString()),
                    Does.Contain("Cotele (canal de voz)"));
            }
        });
    }

    // Contracase of the keyboard: the opening showed nothing new, or the keyboard stayed on a field the window already
    // had (a message box): the destination is never typed there.
    [Test]
    public void AnOpeningThatDidNotTakeTheKeyboardGetsNoText()
    {
        var focusedComposer = Control("6.1", "Edit", "Enviar mensaje a #general", "focused");
        foreach (WindowsVisibleControlAdapter.ViewControl[] look in new[]
        {
            new[] { Opener, Composer },
            new[] { Opener, focusedComposer, Control("13.1", "ListItem", "Algo nuevo") },
        })
        {
            var lease = new Lease();
            var acts = new Acts(lease) { Looks = [look] };

            ExternalCapabilityReceipt receipt = Run(lease, acts);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo(SearchBurst.FocusUnproven));
                Assert.That(acts.Calls, Is.EqualTo(new[] { "open 5.1", "look" }));
                Assert.That(lease.Events, Is.EqualTo(new[] { "acquire " + (long)Window, "restore" }));
            });
        }
    }

    // A person who never pauses gets nothing pressed: the act waits for them, as every act of the real input does.
    [Test]
    public void APersonWhoDoesNotPauseGetsNothingPressed()
    {
        var lease = new Lease { Refusal = "input_user_not_paused" };
        var acts = new Acts(lease);

        ExternalCapabilityReceipt receipt = Run(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_not_paused"));
            Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(acts.Calls, Is.Empty);
        });
    }

    [TestCase("ListItem", "Cotele", "", true)]
    [TestCase("Edit", "Cotele", "", false)]
    [TestCase("CheckBox", "Cotele", "", false)]
    [TestCase("ListItem", "Cotele", "checked", false)]
    [TestCase("ListItem", "General", "", false)]
    [TestCase("Button", "Cotele", "", true)]
    [TestCase("ListItem", "COTELÉ", "", true)]
    // Auditoría B1: only the name itself, folded; never one that holds it nor one a typo away.
    [TestCase("TabItem", "Cotele - Resultados de la búsqueda", "", false)]
    [TestCase("Text", "Cotele es el canal de los memes", "", false)]
    [TestCase("ListItem", "Cotele!!!, Canal de voz", "", false)]
    [TestCase("Button", "Comprimir Cotele", "", false)]
    [TestCase("ListItem", "Cotelería", "", false)]
    [TestCase("ListItem", "Cotle", "", false)]
    public void TheResultIsTheExactNameAndNeverAFieldNorASwitch(string kind, string name, string state, bool chosen) =>
        Assert.That(
            SearchBurst.ResultNaming([Control("1.1", kind, name, state)], "Cotele", null, "5.1") is not null,
            Is.EqualTo(chosen));

    // Auditoría B1: with «choose», exactly that name, whatever the search typed.
    [Test]
    public void TheChosenResultIsTheOneOfThatExactName() =>
        Assert.Multiple(() =>
        {
            WindowsVisibleControlAdapter.ViewControl[] listed =
                [Control("1.1", "ListItem", "Cotele"), Control("1.2", "ListItem", "Cotele (canal de voz)")];
            Assert.That(SearchBurst.ResultNaming(listed, "Cotele", "cotele (canal de voz)", "5.1")?.Id, Is.EqualTo("1.2"));
            Assert.That(SearchBurst.ResultNaming(listed, "Cotele", "Cotele canal", "5.1"), Is.Null);
        });

    // Ronda 25 (banco r23 c7 and s13): the Text a search box draws with its value, or the search itself, is no result;
    // the channel's entry of that name is.
    [Test]
    public void TheEchoOfTheSearchOrOfAFieldsValueIsNoResult()
    {
        WindowsVisibleControlAdapter.ViewControl box = Control("2.1", "ComboBox", "Buscar .wolfsoultm.4191");
        box.Value = "cotele";
        Assert.Multiple(() =>
        {
            Assert.That(SearchBurst.ResultNaming([box, Control("2.2", "Text", "cotele")], "Cotele", null, "5.1"), Is.Null);
            Assert.That(SearchBurst.ResultNaming([box, Control("2.2", "Text", "cotele"), Control("3.1", "ListItem", "Cotele")],
                "Cotele", null, "5.1")?.Id, Is.EqualTo("3.1"));
        });
    }

    // ---------------------------------------------------------------- reopen (pasada r15b, v3-09)
    private static readonly WindowsVisibleControlAdapter.ViewControl Tab = Control("10.1", "TabItem", "Dibujar");
    private static readonly WindowsVisibleControlAdapter.ViewControl Yellow =
        Control("18.7", "SplitButton", "Marcador de resaltado: Amarillo, 5 mm", "collapsed");

    private static ExternalCapabilityReceipt Reopen(Lease lease, Acts acts) =>
        new SearchBurst(lease, lease.Clock, acts)
            .ReopenAsync("input.visible.click", Window, Tab.Name, Tab.Id, Yellow.Name, CancellationToken.None)
            .AsTask().GetAwaiter().GetResult();

    // The gallery closed between the look and the press: its tab and the item go in one burst, the tab pressed once.
    [Test]
    public void AClosedGalleryIsReopenedAndItsItemPressedInOneBurst()
    {
        var lease = new Lease();
        var acts = new Acts(lease) { Looks = [[Tab], [Tab, Yellow]] };

        ExternalCapabilityReceipt receipt = Reopen(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(acts.Calls, Is.EqualTo(new[] { "look", "open 10.1", "look", "choose 18.7 " + Yellow.Name }));
            Assert.That(lease.Events, Is.EqualTo(new[] { "acquire " + (long)Window, "restore" }));
            Assert.That(receipt.Result!.Value.GetProperty("method").GetString(), Is.EqualTo("reopen_burst"));
            Assert.That(receipt.Result!.Value.GetProperty("name").GetString(), Is.EqualTo(Yellow.Name));
        });
    }

    // Still open on the burst's first look: pressing its tab again would close it. The item alone is pressed.
    [Test]
    public void AGalleryStillOpenIsNotToggledShut()
    {
        var lease = new Lease();
        var acts = new Acts(lease) { Looks = [[Tab, Yellow]] };

        ExternalCapabilityReceipt receipt = Reopen(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(acts.Calls, Is.EqualTo(new[] { "look", "choose 18.7 " + Yellow.Name }));
        });
    }

    // The item never shows again: the tab was pressed once, nothing else, and the receipt says the item was not found.
    [Test]
    public void AnItemThatDoesNotReturnIsNeverGuessed()
    {
        var lease = new Lease();
        var acts = new Acts(lease) { Looks = [[Tab], [Tab, Control("18.9", "SplitButton", "Marcador de resaltado: Verde, 5 mm")]] };

        ExternalCapabilityReceipt receipt = Reopen(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(SearchBurst.ItemNotReopened));
            Assert.That(acts.Calls.Count(call => call.StartsWith("open", StringComparison.Ordinal)), Is.EqualTo(1));
            Assert.That(acts.Calls.Any(call => call.StartsWith("choose", StringComparison.Ordinal)), Is.False);
            Assert.That(lease.Events.Count(item => item == "restore"), Is.EqualTo(1));
        });
    }

    // Menús efímeros (pasada r15b t-form-2): «Reemplazar» lived in the popup host «Editar» opened, which died when the
    // person took the front back. The burst reopens «Editar» on the window and presses the item in the popup born of it.
    [Test]
    public void AnItemOfTheOpenersOwnPopupIsPressedThereAfterTheReopen()
    {
        const nint Popup = 5000;
        var editar = Control("9.1", "MenuItem", "Editar", "collapsed");
        var reemplazar = Control("42.7", "MenuItem", "Reemplazar");
        bool opened = false;
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[editar]],
            Popups = () => opened ? [Popup] : [],
            PopupLook = [reemplazar],
            OnOpen = () => opened = true,
        };

        ExternalCapabilityReceipt receipt = new SearchBurst(lease, lease.Clock, acts)
            .ReopenAsync("input.visible.click", Window, editar.Name, editar.Id, reemplazar.Name, CancellationToken.None)
            .AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(acts.Calls, Is.EqualTo(new[] { "look", "open 9.1", "look", "look 5000", "choose 42.7 Reemplazar @5000" }));
            Assert.That(lease.Events, Is.EqualTo(new[] { "acquire " + (long)Window, "restore" }));
        });
    }

    // Contracase: a popup that shows another name is never pressed, and the opener is pressed once only.
    [Test]
    public void APopupWithoutTheItemGetsNothingPressed()
    {
        var editar = Control("9.1", "MenuItem", "Editar", "collapsed");
        bool opened = false;
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[editar]],
            Popups = () => opened ? [5000] : [],
            PopupLook = [Control("42.9", "MenuItem", "Eliminar")],
            OnOpen = () => opened = true,
        };

        ExternalCapabilityReceipt receipt = new SearchBurst(lease, lease.Clock, acts)
            .ReopenAsync("input.visible.click", Window, editar.Name, editar.Id, "Reemplazar", CancellationToken.None)
            .AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(SearchBurst.ItemNotReopened));
            Assert.That(acts.Calls.Count(call => call.StartsWith("open", StringComparison.Ordinal)), Is.EqualTo(1));
            Assert.That(acts.Calls.Any(call => call.StartsWith("choose", StringComparison.Ordinal)), Is.False);
        });
    }

    // Review of the branch (finding 1): another window of the same process the person already had up over the mission's
    // (a second document of a single-process editor, another browser window) lies inside its frame and counts as one of
    // its popups; it was there before the burst, so it is never looked into nor pressed, even when it shows the name.
    [Test]
    public void AWindowOfTheSameProcessUpBeforeTheBurstIsNeverPressed()
    {
        const nint PersonsDocument = 7000;
        var editar = Control("9.1", "MenuItem", "Editar", "collapsed");
        var reemplazar = Control("42.7", "MenuItem", "Reemplazar");
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[editar]],
            Popups = () => [PersonsDocument],
            PopupLook = [reemplazar],
        };

        ExternalCapabilityReceipt receipt = new SearchBurst(lease, lease.Clock, acts)
            .ReopenAsync("input.visible.click", Window, editar.Name, editar.Id, reemplazar.Name, CancellationToken.None)
            .AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(SearchBurst.ItemNotReopened));
            Assert.That(acts.Calls.Any(call => call.Contains("7000", StringComparison.Ordinal)), Is.False,
                "the person's window is neither looked into nor pressed");
        });
    }

    // The popup the mission's look saw the item in, still up, is looked into first and the item pressed there with no
    // second press of its opener; a window of the same process up beside it is still none of the burst's.
    [Test]
    public void ThePopupTheMissionSawTheItemInIsPressedWhileItLives()
    {
        const nint Popup = 5000;
        var editar = Control("9.1", "MenuItem", "Editar", "collapsed");
        var reemplazar = Control("42.7", "MenuItem", "Reemplazar");
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[editar]],
            Popups = () => [7000, Popup],
            PopupLook = [reemplazar],
        };

        ExternalCapabilityReceipt receipt = new SearchBurst(lease, lease.Clock, acts)
            .ReopenAsync("input.visible.click", Window, editar.Name, editar.Id, reemplazar.Name, CancellationToken.None, shownIn: Popup)
            .AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(acts.Calls, Is.EqualTo(new[] { "look", "look 5000", "choose 42.7 Reemplazar @5000" }));
        });
    }

    // Ronda 20 (P7, v3-09): the gallery's item was asked for by its arrow (open); in the burst the tab is pressed as it was
    // and the item by its arrow, never by its ordinary press (a split button's Invoke is its own action).
    [Test]
    public void AnItemAskedForByItsArrowIsOpenedByItsArrowInTheBurst()
    {
        var lease = new Lease();
        var acts = new Acts(lease) { Looks = [[Tab], [Tab, Yellow]] };

        ExternalCapabilityReceipt receipt = new SearchBurst(lease, lease.Clock, acts)
            .ReopenAsync("input.visible.click", Window, Tab.Name, Tab.Id, Yellow.Name, CancellationToken.None, itemManner: "open")
            .AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(acts.Calls, Is.EqualTo(new[] { "look", "open 10.1", "look", "press open 18.7" }));
            Assert.That(acts.Calls.Any(call => call.StartsWith("choose", StringComparison.Ordinal)), Is.False);
        });
    }

    // Ronda 20 (P7, v3-37): an opener pressed by its arrow («Nueva pestaña», a split button) is pressed by its arrow again
    // to bring its list back, never by its own action (another tab); the item of the list by its ordinary press.
    [Test]
    public void AnOpenerPressedByItsArrowIsReopenedByItsArrow()
    {
        var nueva = Control("4.2", "SplitButton", "Nueva pestaña");
        var simbolo = Control("51.3", "MenuItem", "Símbolo del sistema");
        bool opened = false;
        var lease = new Lease();
        var acts = new Acts(lease)
        {
            Looks = [[nueva]],
            Popups = () => opened ? [5000] : [],
            PopupLook = [simbolo],
            OnOpen = () => opened = true,
        };

        ExternalCapabilityReceipt receipt = new SearchBurst(lease, lease.Clock, acts)
            .ReopenAsync("input.visible.click", Window, nueva.Name, nueva.Id, simbolo.Name, CancellationToken.None, openerManner: "open")
            .AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(acts.Calls, Is.EqualTo(new[] { "look", "press open 4.2", "look", "look 5000", "choose 51.3 Símbolo del sistema @5000" }));
            Assert.That(acts.Calls.Count(call => call.StartsWith("open", StringComparison.Ordinal)), Is.Zero,
                "the arrow once; its own action never");
        });
    }

    // A disabled entry of that name is no item to press.
    [Test]
    public void ADisabledItemIsNotPressed()
    {
        var lease = new Lease();
        var acts = new Acts(lease) { Looks = [[Tab, Control("18.7", "SplitButton", Yellow.Name, "disabled")]] };

        ExternalCapabilityReceipt receipt = Reopen(lease, acts);

        Assert.That(acts.Calls.Any(call => call.StartsWith("choose", StringComparison.Ordinal)), Is.False);
        Assert.That(receipt.Verified, Is.False);
    }

    // The person types before anything was pressed: the burst ends with nothing done, the front given back.
    [Test]
    public void ThePersonsInputStopsTheReopenBeforeAnyPress()
    {
        var lease = new Lease();
        lease.PersonActs();
        var acts = new Acts(lease) { Looks = [[Tab], [Tab, Yellow]] };

        ExternalCapabilityReceipt receipt = Reopen(lease, acts);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(acts.Calls, Is.Empty);
            Assert.That(lease.Events.Count(item => item == "restore"), Is.EqualTo(1));
        });
    }

    private static ExternalCapabilityReceipt Run(Lease lease, Acts acts, string? choose = null) =>
        new SearchBurst(lease, lease.Clock, acts)
            .RunAsync("input.visible.click", Window, Opener.Name, Opener.Id, [Opener, Composer], "Cotele", choose, CancellationToken.None)
            .AsTask().GetAwaiter().GetResult();

    private static WindowsVisibleControlAdapter.ViewControl Control(string id, string kind, string name, string state = "") =>
        new() { Id = id, Kind = kind, Name = name, State = state };

    private static ExternalCapabilityReceipt Done(string operation, string kind = "") =>
        ExternalJson.Success(operation, JsonDocument.Parse("{\"ok\":true,\"kind\":\"" + kind + "\",\"method\":\"invoke\"}").RootElement.Clone());

    private sealed class Clock : ILeaseClock
    {
        public long NowMs { get; private set; } = 1_000;

        internal void Advance(long milliseconds) => NowMs += milliseconds;

        public ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken)
        {
            NowMs += milliseconds;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class Lease : IForegroundLease
    {
        private bool _acted;

        internal Clock Clock { get; } = new();

        internal List<string> Events { get; } = [];

        internal string? Refusal { get; init; }

        internal void PersonActs() => _acted = true;

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken)
        {
            Events.Add("acquire " + (long)window);
            return ValueTask.FromResult<IInputBurst>(new Burst(this));
        }

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("a search burst runs no helper");

        private sealed class Burst(Lease lease) : IInputBurst
        {
            public string? Refusal => lease.Refusal;

            public long WaitedMs => 520;

            public bool UserActed => lease._acted;

            public bool Restore()
            {
                lease.Events.Add("restore");
                return true;
            }
        }
    }

    private sealed class Acts(Lease lease) : ISearchBurstActs
    {
        internal List<string> Calls { get; } = [];

        internal IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>[] Looks { get; init; } = [];

        internal Action? OnOpen { get; init; }

        internal Action? OnType { get; init; }

        public ValueTask<ExternalCapabilityReceipt> OpenAsync(nint window, string label, string controlId, CancellationToken cancellationToken)
        {
            Calls.Add("open " + controlId);
            OnOpen?.Invoke();
            return ValueTask.FromResult(Done("input.visible.click", "Button"));
        }

        // The window's own popups now, and what a look at one shows (menus-efímeros: a menu bar's popup host).
        internal Func<IReadOnlyList<nint>> Popups { get; init; } = () => [];

        internal IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> PopupLook { get; init; } = [];

        public IReadOnlyList<nint> PopupsOfWindow(nint window) => Popups();

        public ValueTask<IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>?> LookAsync(nint window, CancellationToken cancellationToken)
        {
            lease.Clock.Advance(150);
            if (window != Window)
            {
                Calls.Add("look " + (long)window);
                return ValueTask.FromResult<IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>?>(PopupLook);
            }

            Calls.Add("look");
            int seen = Calls.Count(call => call == "look") - 1;
            return ValueTask.FromResult<IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>?>(Looks.Length == 0 ? null : Looks[Math.Min(seen, Looks.Length - 1)]);
        }

        public ValueTask<ExternalCapabilityReceipt> TypeAsync(nint window, string text, CancellationToken cancellationToken)
        {
            Calls.Add("type " + text);
            OnType?.Invoke();
            return ValueTask.FromResult(Done("input.text.type"));
        }

        public ValueTask<ExternalCapabilityReceipt> ChooseAsync(nint window, string label, string controlId, CancellationToken cancellationToken)
        {
            Calls.Add("choose " + controlId + " " + label + (window == Window ? string.Empty : " @" + (long)window));
            return ValueTask.FromResult(Done("input.visible.click", "ListItem"));
        }

        public ValueTask<ExternalCapabilityReceipt> PressInMannerAsync(
            nint window, string label, string controlId, string manner, CancellationToken cancellationToken)
        {
            Calls.Add("press " + manner + " " + controlId);
            OnOpen?.Invoke();
            return ValueTask.FromResult(Done("input.visible.click", "SplitButton"));
        }
    }
}
