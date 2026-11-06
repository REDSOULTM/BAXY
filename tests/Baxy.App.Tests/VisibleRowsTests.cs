using System.Diagnostics;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Threading;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Banco de uso 2026-11-03 (R11, R12): the visible rows of other windows' lists, read through UI Automation, kept only
/// when the comparison given accepts them, within a budget.
/// </summary>
[TestFixture]
public sealed class VisibleRowsTests
{
    // Encargo 65 (revisión): a window's tabs are a strip of pages when the window is titled by the one it shows (every
    // browser, an editor); a ribbon's («Inicio» shown in «Documento1 - Word») is not, nor one whose shown tab does not title
    // the window.
    [TestCase("Recibidos (3) - ana@ejemplo.test - Gmail - Opera", "Recibidos (3) - ana@ejemplo.test - Gmail", true)]
    [TestCase("Alfa Cuaderno y 1 página más - Personal: Microsoft Edge", "Alfa Cuaderno - Uso de memoria - 21.9 MB", true)]
    [TestCase("Documento1 - Word", "Inicio", false)]
    public void TabsAreAStripOfPagesWhenTheWindowIsTitledByTheOneShown(string title, string shown, bool pages)
    {
        Assert.Multiple(() =>
        {
            Assert.That(VisibleRows.PageStrip(title, [("Otra página - Sitio", false), (shown, true)]), Is.EqualTo(pages));
            // Chrome (measured 03-11) says no tab selected: the strip is one when the window is titled by one of them.
            Assert.That(VisibleRows.PageStrip(title, [(shown, false)]), Is.EqualTo(pages));
            Assert.That(VisibleRows.PageStrip(title, [(shown, false), ("Otra página - Sitio", true)]), Is.False);
        });
    }

    // A window that is gone (or a handle that is no window) gives no rows and no failure, within the budget.
    [Test]
    public void AWindowThatIsGoneGivesNoRows()
    {
        var clock = Stopwatch.StartNew();
        IReadOnlyList<VisibleRow> rows =
            VisibleRows.Read([0x7FFF_FFF0], static _ => true, static _ => true, TimeSpan.FromSeconds(5));

        Assert.Multiple(() =>
        {
            Assert.That(rows, Is.Empty);
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(5)));
        });
    }

    // Live: a window of this test's own (a list «Chats» with three rows, shown without taking the front) is read; every
    // visible row is given to the comparison and only the one it accepts comes back, with its window's title. No other
    // window is read: the reader is given only this one.
    [Test]
    [Explicit("Live: shows a window of its own for a moment, without taking the front.")]
    public void TheRowsOfAListAreReadAndOnlyTheOneNamedIsKept()
    {
        nint handle = 0;
        Dispatcher? dispatcher = null;
        using var shown = new ManualResetEventSlim();
        var ui = new Thread(() =>
        {
            var list = new ListBox();
            AutomationProperties.SetName(list, "Chats");
            foreach (string chat in new[] { "Equipo Lunes y Martes", "Equipo Lunes 🌙", "Vecinos de prueba" })
            {
                list.Items.Add(chat);
            }

            var window = new Window
            {
                Title = "Chat de prueba BAXY",
                Content = list,
                Width = 300,
                Height = 200,
                ShowActivated = false,
                ShowInTaskbar = false,
                WindowStartupLocation = WindowStartupLocation.Manual,
                Left = 0,
                Top = 0,
            };
            // The list's rows exist once the window has rendered (its items' containers are made by layout).
            window.ContentRendered += (_, _) => shown.Set();
            window.Show();
            handle = new WindowInteropHelper(window).Handle;
            dispatcher = Dispatcher.CurrentDispatcher;
            Dispatcher.Run();
        });
        ui.SetApartmentState(ApartmentState.STA);
        ui.IsBackground = true;
        ui.Start();
        try
        {
            Assert.That(shown.Wait(TimeSpan.FromSeconds(10)), Is.True, "the window shows");
            var offered = new List<string>();
            IReadOnlyList<VisibleRow> rows = VisibleRows.Read([handle], row =>
            {
                lock (offered)
                {
                    offered.Add(row);
                }

                return row == "Equipo Lunes 🌙";
            }, static _ => false, VisibleRows.Budget);

            Assert.Multiple(() =>
            {
                Assert.That(offered, Is.EquivalentTo(new[] { "Equipo Lunes y Martes", "Equipo Lunes 🌙", "Vecinos de prueba" }));
                Assert.That(rows.Select(static row => (row.Title, row.Name)).ToArray(), Is.EqualTo(new[]
                {
                    ("Chat de prueba BAXY", "Equipo Lunes 🌙"),
                }));
            });
        }
        finally
        {
            dispatcher?.InvokeShutdown();
            _ = ui.Join(TimeSpan.FromSeconds(5));
        }
    }

    // Encargo 65 (cosecha F2), live: a window of this test's own with a tab strip (three tabs titled as pages are, the
    // first shown) is read in the same pass as the rows; the tabs go to the second comparison, only the one it accepts
    // comes back, marked as a tab and whether it is the one shown. No other window is read.
    [Test]
    [Explicit("Live: shows a window of its own for a moment, without taking the front.")]
    public void TheTabsOfATabStripAreReadAndOnlyTheOneNamedIsKept()
    {
        nint handle = 0;
        Dispatcher? dispatcher = null;
        using var shown = new ManualResetEventSlim();
        string[] pages = ["Proyecto Faro - Notas", "Recibidos (2) - ana@ejemplo.test - Gmail", "Mi unidad - Google Drive"];
        var ui = new Thread(() =>
        {
            var strip = new TabControl();
            foreach (string page in pages)
            {
                strip.Items.Add(new TabItem { Header = page, Content = new TextBlock { Text = page } });
            }

            var window = new Window
            {
                // Titled by the tab it shows, as a browser is (VisibleRows.PageStrip).
                Title = pages[0] + " - Navegador de prueba BAXY",
                Content = strip,
                Width = 500,
                Height = 200,
                ShowActivated = false,
                ShowInTaskbar = false,
                WindowStartupLocation = WindowStartupLocation.Manual,
                Left = 0,
                Top = 0,
            };
            window.ContentRendered += (_, _) => shown.Set();
            window.Show();
            handle = new WindowInteropHelper(window).Handle;
            dispatcher = Dispatcher.CurrentDispatcher;
            Dispatcher.Run();
        });
        ui.SetApartmentState(ApartmentState.STA);
        ui.IsBackground = true;
        ui.Start();
        try
        {
            Assert.That(shown.Wait(TimeSpan.FromSeconds(10)), Is.True, "the window shows");
            var egress = new NetworkEgress();
            egress.Heard("abre en el Gmail lo último que me mandó Codeberg");
            var offered = new List<string>();
            Func<string, bool> names = egress.NamesTab();
            IReadOnlyList<VisibleRow> rows = VisibleRows.Read([handle], static _ => false, tab =>
            {
                lock (offered)
                {
                    offered.Add(tab);
                }

                return names(tab);
            }, VisibleRows.Budget);

            Assert.Multiple(() =>
            {
                Assert.That(offered, Is.EquivalentTo(pages));
                Assert.That(rows.Select(static row => (row.Title, row.Name, row.Tab, row.Shown)).ToArray(), Is.EqualTo(new[]
                {
                    (pages[0] + " - Navegador de prueba BAXY", pages[1], true, false),
                }));
                Assert.That(NetworkEgress.Elsewhere("Outlook", () => egress.Named([], rows)),
                    Does.Contain("not the one shown"));
            });
        }
        finally
        {
            dispatcher?.InvokeShutdown();
            _ = ui.Join(TimeSpan.FromSeconds(5));
        }
    }
}
