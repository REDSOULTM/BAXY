using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Automation.Provider;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// INT16, blind review: the overlay is on top of everything in a corner, and with «responder desde el overlay» on it
/// shows the card's Sí and No. A click the person meant for the window under that corner landed on a Sí that had just
/// appeared. OVL1 (VIVO2, 9c): the guard that held the Sí compared the time its handler ran with the time the card
/// arrived, so with the window's thread busy a click 173 and 225 ms after the Sí was painted approved and a console
/// command ran. The Sí takes a press only if the person made it after the Sí was drawn armed, and it is drawn armed
/// only after its whole wait in its place, drawn off; the No is never held back.
/// </summary>
[TestFixture]
public sealed class OverlayWindowTests
{
    private static readonly OverlaySettings Answering = new(On: true, Corner: "br", Size: "m", Opacity: 78, HideSeconds: 8,
        NotFullscreen: true, Answer: true);

    private static readonly Color Armed = Color.FromRgb(0xB8, 0x3A, 0x4A);

    private static OverlaySnapshot Ask(string card, string say = "Borrar notas.txt · Escritorio") =>
        new("ask", "Esperando tu sí", say, [], "borra notas.txt", "1:59", 0.08, card);

    [Test]
    public void TheSiIsOffUntilItsWholeWaitDrawnInItsPlaceAndThenTakesAPress()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            Assert.That(bench.Lit, Is.False, "a Sí that just appeared is off");
            bench.Pass(OverlayWindow.ArmMilliseconds - 1);
            Assert.That(bench.Lit, Is.False, "a millisecond short of its wait");
            bench.Pass(1);
            Assert.That(bench.Lit, Is.True);
            Assert.That(bench.Answered, Is.Empty);

            bench.Click("Sí", pressedAt: bench.Now);
            Assert.That(bench.Answered, Is.EqualTo(new[] { ("c1", true) }));
        });
    }

    [Test]
    public void APressMadeBeforeTheSiArmedDoesNotApproveHoweverLateItIsHandled()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            // the person pressed 200 ms after the card; the window's thread, busy, handles nothing for longer than the
            // wait, and once free it first draws (the Sí, lit by now) and then reads the press that was waiting
            long pressedAt = bench.Now + 200;
            bench.Pass(OverlayWindow.ArmMilliseconds + 400);
            bench.Click("Sí", pressedAt);
            Assert.That(bench.Answered, Is.Empty, "the press was made with the Sí off: when it is handled does not count");

            Assert.That(bench.Lit, Is.False, "and a press that came too soon starts the wait again");
            bench.Pass(OverlayWindow.ArmMilliseconds);
            bench.Click("Sí", pressedAt: bench.Now);
            Assert.That(bench.Answered, Is.EqualTo(new[] { ("c1", true) }));
        });
    }

    [Test]
    public void APressBegunBeforeTheSiArmedAndReleasedAfterDoesNotApprove()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            bench.Pass(OverlayWindow.ArmMilliseconds - 20);
            bench.Down("Sí", pressedAt: bench.Now);
            bench.Pass(40);
            bench.Release("Sí");
            Assert.That(bench.Answered, Is.Empty, "the button went down with the Sí off");
        });
    }

    [Test]
    public void AClickWithNoPressOfTheMouseCountsFromWhenItIsHandled()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            bench.Release("Sí"); // a click with no press before it (an assistive tool's invoke is judged by the Sí's peer)
            bench.Pass(OverlayWindow.ArmMilliseconds - 1);
            bench.Release("Sí");
            Assert.That(bench.Answered, Is.Empty, "the first one, too soon, started the wait again");
            bench.Pass(OverlayWindow.ArmMilliseconds);
            bench.Release("Sí");
            Assert.That(bench.Answered, Is.EqualTo(new[] { ("c1", true) }));
        });
    }

    [Test]
    public void AnInvokeAskedOfASiThatIsOffIsRefusedWhenAskedHoweverLateTheClickIsHandled()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            bench.Pass(OverlayWindow.ArmMilliseconds - 1);
            AutomationPeer peer = UIElementAutomationPeer.CreatePeerForElement(bench.Button("Sí"));
            var invoke = (IInvokeProvider)peer.GetPattern(PatternInterface.Invoke);

            // asked with the Sí off; the window's thread, busy, lights it before it gets round to the click
            try
            {
                invoke.Invoke();
            }
            catch (ElementNotEnabledException)
            {
            }

            bench.Pass(1);
            Assert.That(bench.Answered, Is.Empty, "the invoke was asked of a Sí that was off");

            Assert.That(peer.IsEnabled(), Is.True);
            invoke.Invoke();
            Bench.Drawn();
            Assert.That(bench.Answered, Is.EqualTo(new[] { ("c1", true) }));

            bench.Show(Ask("c2"));
            peer = UIElementAutomationPeer.CreatePeerForElement(bench.Button("Sí"));
            Assert.That(peer.IsEnabled(), Is.False, "an assistive tool is told that the Sí that is off takes nothing");
            Assert.Throws<ElementNotEnabledException>(((IInvokeProvider)peer.GetPattern(PatternInterface.Invoke)).Invoke);
        });
    }

    [Test]
    public void AnInvokeTakenIsThePressOfItsClickHoweverLateThatIsHandled()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            bench.Pass(OverlayWindow.ArmMilliseconds);
            var invoke = (IInvokeProvider)UIElementAutomationPeer.CreatePeerForElement(bench.Button("Sí")).GetPattern(PatternInterface.Invoke);
            invoke.Invoke(); // taken, the Sí armed: its click waits for the window's thread

            // before the thread gets round to it, the same card asks for something else, and that Sí is armed in turn
            bench.Busy(Ask("c1", "Vaciar la papelera"));
            bench.Busy(OverlayWindow.ArmMilliseconds);
            Assert.That(bench.Lit, Is.True);
            Bench.Drawn();
            Assert.That(bench.Answered, Is.Empty, "the invoke was taken for what the card asked before");
        });
    }

    [Test]
    public void AnotherCardOrASiThatMovedOrChangedSizeStartsTheWaitAgain()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            bench.Pass(OverlayWindow.ArmMilliseconds);
            Assert.That(bench.Lit, Is.True);

            bench.Show(Ask("c2"));
            Assert.That(bench.Lit, Is.False, "another confirmation: a Sí meant for the first one must not approve it");
            bench.Click("Sí", pressedAt: bench.Now);
            Assert.That(bench.Answered, Is.Empty);
            bench.Pass(OverlayWindow.ArmMilliseconds);
            Assert.That(bench.Lit, Is.True);

            bench.Show(Ask("c2", "Vaciar la papelera"));
            Assert.That(bench.Lit, Is.False, "the same card asking for something else is another confirmation");
            bench.Click("Sí", pressedAt: bench.Now);
            Assert.That(bench.Answered, Is.Empty);
            bench.Pass(OverlayWindow.ArmMilliseconds);
            Assert.That(bench.Lit, Is.True);

            bench.Placed(new Rect(1500, 900, 150, 28));
            Assert.That(bench.Lit, Is.False, "its place on the screen is known only now");
            bench.Pass(OverlayWindow.ArmMilliseconds);
            bench.Placed(new Rect(1500, 900, 150, 28));
            Assert.That(bench.Lit, Is.True, "laid out again where it was");

            bench.Placed(new Rect(1500, 830, 150, 28));
            Assert.That(bench.Lit, Is.False, "moved");
            bench.Click("Sí", pressedAt: bench.Now);
            Assert.That(bench.Answered, Is.Empty);
            bench.Pass(OverlayWindow.ArmMilliseconds);
            Assert.That(bench.Lit, Is.True);

            bench.Placed(new Rect(1500, 830, 180, 28));
            Assert.That(bench.Lit, Is.False, "changed size");
            bench.Pass(OverlayWindow.ArmMilliseconds - 1);
            bench.Click("Sí", pressedAt: bench.Now);
            Assert.That(bench.Answered, Is.Empty);
            bench.Pass(OverlayWindow.ArmMilliseconds);
            bench.Click("Sí", pressedAt: bench.Now);
            Assert.That(bench.Answered, Is.EqualTo(new[] { ("c2", true) }));
        });
    }

    [Test]
    public void TheSiLooksOffWhileItIsOffAndTheAnswersStayTheSameButtonsWhileTheirCardWaits()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            Button yes = bench.Button("Sí");
            Button no = bench.Button("No");
            Assert.That(((SolidColorBrush)yes.Background).Color, Is.Not.EqualTo(Armed), "a Sí that looks ready and does not answer is the trap");
            Assert.That(yes.Cursor, Is.Not.EqualTo(Cursors.Hand));
            Assert.That(yes.Focusable || no.Focusable, Is.False, "the overlay never takes the keyboard: no key presses its buttons");

            bench.Pass(500); // the half-second clock draws the overlay again: a press under way must not lose its button
            bench.Pass(OverlayWindow.ArmMilliseconds);
            Assert.That(bench.Button("Sí"), Is.SameAs(yes));
            Assert.That(bench.Button("No"), Is.SameAs(no));
            Assert.That(((SolidColorBrush)yes.Background).Color, Is.EqualTo(Armed));
            Assert.That(yes.Cursor, Is.EqualTo(Cursors.Hand));
        });
    }

    [Test]
    public void TheNoIsNeverHeldAndAButtonDrawnForOneCardNeverAnswersAnother()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            bench.Show(Ask("c1"));
            Button noOfC1 = bench.Button("No");
            Button yesOfC1 = bench.Button("Sí");
            bench.Pass(OverlayWindow.ArmMilliseconds);
            bench.Show(Ask("c2"));
            noOfC1.RaiseEvent(new RoutedEventArgs(ButtonBase.ClickEvent));
            yesOfC1.RaiseEvent(new RoutedEventArgs(ButtonBase.ClickEvent));
            Assert.That(bench.Answered, Is.Empty, "a button drawn for c1 never answers c2");

            bench.Click("No", pressedAt: bench.Now);
            Assert.That(bench.Answered, Is.EqualTo(new[] { ("c2", false) }), "No is never held");
        });
    }

    [Test]
    [Explicit("Live: shows the overlay itself in a corner for a moment, without taking the front.")]
    public void Live_TheSiGoesOffWhenTheOverlayMovesChangesSizeOrShowsAgain()
    {
        RunOnSta(() =>
        {
            var bench = new Bench();
            OverlayWindow overlay = bench.Overlay;
            try
            {
                bench.Show(Ask("c1"), live: true);
                bench.Pass(OverlayWindow.ArmMilliseconds, live: true);
                Assert.That(bench.Lit, Is.True, "drawn in its corner for its whole wait");
                bench.Pass(500, live: true);
                Assert.That(bench.Lit, Is.True, "drawn again in the same place: still armed");

                overlay.Left -= 60;
                Bench.Drawn();
                Assert.That(bench.Lit, Is.False, "the window moved");
                bench.Pass(OverlayWindow.ArmMilliseconds, live: true);
                Assert.That(bench.Lit, Is.False, "put back in its corner: it moved again");
                bench.Pass(OverlayWindow.ArmMilliseconds, live: true);
                Assert.That(bench.Lit, Is.True);

                bench.Show(Ask("c1", "Borrar notas.txt · Escritorio · y otra línea que hace crecer la tarjeta hacia arriba y mueve su esquina"), live: true, corner: "tr");
                Assert.That(bench.Lit, Is.False, "the same card, drawn elsewhere");
                bench.Pass(OverlayWindow.ArmMilliseconds, live: true, corner: "tr");
                Assert.That(bench.Lit, Is.True);

                overlay.Hide();
                Bench.Drawn();
                overlay.Show();
                Bench.Drawn();
                Assert.That(bench.Lit, Is.False, "shown again");
                bench.Pass(OverlayWindow.ArmMilliseconds, live: true, corner: "tr");
                bench.Click("Sí", pressedAt: bench.Now);
                Assert.That(bench.Answered, Is.EqualTo(new[] { ("c1", true) }));
            }
            finally
            {
                overlay.Close();
            }
        });
    }

    /// <summary>An overlay with a clock of its own, and what a person and the window's thread do to it.</summary>
    private sealed class Bench
    {
        private OverlaySnapshot? _shown;

        internal Bench()
        {
            Overlay = new OverlayWindow { Ticks = () => Now, MessageTicks = () => unchecked((int)Now) };
            Overlay.Answered += (card, approve) => Answered.Add((card, approve));
        }

        internal OverlayWindow Overlay { get; }

        internal long Now { get; private set; } = 1_000_000;

        internal List<(string Card, bool Approve)> Answered { get; } = [];

        internal bool Lit => ((SolidColorBrush)Button("Sí").Background).Color == Armed;

        /// <summary>What the window's thread does once it is free: it draws, then runs what waited for the drawing.</summary>
        internal static void Drawn() => Dispatcher.CurrentDispatcher.Invoke(static () => { }, DispatcherPriority.ContextIdle);

        internal void Show(OverlaySnapshot shown, bool live = false, string corner = "br")
        {
            _shown = shown;
            Overlay.Render(shown, Answering, english: false);
            if (live)
            {
                Overlay.Show();
                Overlay.Place(corner);
            }

            Drawn();
        }

        /// <summary>Time passes and the overlay's clock draws the same card again.</summary>
        internal void Pass(long milliseconds, bool live = false, string corner = "br")
        {
            Now += milliseconds;
            Show(_shown!, live, corner);
        }

        /// <summary>
        /// The overlay draws that card (with time passed, if given) while the window's thread, busy, does all that
        /// comes before input and leaves the input waiting.
        /// </summary>
        internal void Busy(OverlaySnapshot shown)
        {
            _shown = shown;
            Busy(0);
        }

        internal void Busy(long milliseconds)
        {
            Now += milliseconds;
            Overlay.Render(_shown!, Answering, english: false);
            Dispatcher.CurrentDispatcher.Invoke(static () => { }, DispatcherPriority.Loaded);
        }

        /// <summary>The Sí was laid out there on the screen.</summary>
        internal void Placed(Rect at)
        {
            Overlay.SiAt(at);
            Drawn();
        }

        internal Button Button(string label) => Buttons(Overlay).Single(button => (string)button.Content == label);

        /// <summary>The mouse goes down on a button: the person pressed at that time, the window reads it now.</summary>
        internal void Down(string label, long pressedAt)
        {
            Button(label).RaiseEvent(new MouseButtonEventArgs(Mouse.PrimaryDevice, unchecked((int)pressedAt), MouseButton.Left) { RoutedEvent = UIElement.PreviewMouseLeftButtonDownEvent });
            Drawn();
        }

        /// <summary>The click itself: the mouse let go on the button, or an assistive tool invoked it.</summary>
        internal void Release(string label)
        {
            Button(label).RaiseEvent(new RoutedEventArgs(ButtonBase.ClickEvent));
            Drawn();
        }

        internal void Click(string label, long pressedAt)
        {
            Down(label, pressedAt);
            Release(label);
        }
    }

    private static IEnumerable<Button> Buttons(DependencyObject node)
    {
        foreach (object child in LogicalTreeHelper.GetChildren(node))
        {
            if (child is Button button)
            {
                yield return button;
            }

            if (child is DependencyObject inner)
            {
                foreach (Button found in Buttons(inner))
                {
                    yield return found;
                }
            }
        }
    }

    private static void RunOnSta(Action action)
    {
        Exception? failure = null;
        var ui = new Thread(() =>
        {
            try
            {
                action();
            }
            catch (Exception exception)
            {
                failure = exception;
            }
        });
        ui.SetApartmentState(ApartmentState.STA);
        ui.Start();
        ui.Join();
        if (failure is not null)
        {
            System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(failure).Throw();
        }
    }
}
