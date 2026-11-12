using System.IO;
using System.Windows;
using System.Windows.Threading;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// CER1 (INFORME_UPD1, in the live run of 11-11: 3 of 8 asks to exit left BAXY open, each with its line in
/// unhandled.v1.jsonl): when everything the teardown waits for is already over, its last Close() came still inside the
/// window's Closing, WPF refused it, and BAXY stayed with its window disabled and the one-shot exit event spent. A real
/// window here, off the screen and never activated, on a thread and dispatcher of its own.
/// </summary>
[TestFixture]
public sealed class ClosingTeardownTests
{
    private static readonly TimeSpan Limit = TimeSpan.FromSeconds(10);

    [Test]
    public void AWindowWhoseTeardownIsAlreadyOverClosesAndNothingIsLeftUncaught()
    {
        Bench bench = RunOnSta(bench =>
        {
            bench.Start(() =>
            {
                bench.Teardowns++;
                return Task.CompletedTask;
            });
            bench.AskToClose();
        });

        Assert.That(bench.Uncaught, Is.Empty, "WPF refused a Close() made inside Closing");
        Assert.That(bench.WindowClosed, Is.True);
        Assert.That(bench.Teardowns, Is.EqualTo(1));
        Assert.That(bench.Exits, Is.EqualTo(1), "the application is asked to end once the window is gone");
    }

    [Test]
    public void ATeardownThatTakesItsTimeClosesTheWindowWhenItIsOver()
    {
        Bench bench = RunOnSta(bench =>
        {
            var stopped = new TaskCompletionSource();
            bench.Start(() => stopped.Task);
            bench.AskToClose();
            bench.Then(() =>
            {
                Assert.That(bench.WindowClosed, Is.False, "the window waits for what it stops");
                stopped.SetResult();
            });
        });

        Assert.That(bench.Uncaught, Is.Empty);
        Assert.That(bench.WindowClosed, Is.True);
        Assert.That(bench.Exits, Is.EqualTo(1));
    }

    [Test]
    public void ASecondAskWhileTheFirstIsUnderWayNeitherTearsDownAgainNorIsLost()
    {
        Bench bench = RunOnSta(bench =>
        {
            var stopped = new TaskCompletionSource();
            bench.Start(() =>
            {
                bench.Teardowns++;
                return stopped.Task;
            });
            bench.AskToClose();
            bench.Then(() =>
            {
                bench.AskToClose();
                bench.Then(() =>
                {
                    Assert.That(bench.WindowClosed, Is.False);
                    stopped.SetResult();
                });
            });
        });

        Assert.That(bench.Uncaught, Is.Empty);
        Assert.That(bench.WindowClosed, Is.True);
        Assert.That(bench.Teardowns, Is.EqualTo(1));
        Assert.That(bench.Exits, Is.EqualTo(1));
    }

    [Test]
    public void ATeardownThatFailsStillClosesTheWindowAndTheFailureIsRecorded()
    {
        string directory = Path.Combine(Path.GetTempPath(), "baxy-cer1-" + Guid.NewGuid().ToString("N"));
        try
        {
            Bench bench = RunOnSta(bench =>
            {
                bench.Start(() => throw new InvalidOperationException("the core did not answer its stop"), directory);
                bench.AskToClose();
            });

            Assert.That(bench.Uncaught, Is.Empty);
            Assert.That(bench.WindowClosed, Is.True, "the person asked to exit: a half-stopped BAXY does not stay");
            Assert.That(bench.Exits, Is.EqualTo(1));
            string[] lines = File.ReadAllLines(Path.Combine(directory, "unhandled.v1.jsonl"));
            Assert.That(lines, Has.Length.EqualTo(1));
            Assert.That(lines[0], Does.Contain("\"source\":\"exit\"").And.Contain("InvalidOperationException"));
        }
        finally
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
    }

    private static Bench RunOnSta(Action<Bench> arrange)
    {
        Bench? bench = null;
        Exception? failure = null;
        var ui = new Thread(() =>
        {
            try
            {
                bench = new Bench();
                arrange(bench);
                bench.RunUntilClosed();
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

        return bench!;
    }

    private sealed class Bench
    {
        private readonly Dispatcher _dispatcher = Dispatcher.CurrentDispatcher;
        private readonly Window _window = new()
        {
            Width = 40,
            Height = 40,
            Left = -32000,
            Top = -32000,
            WindowStyle = WindowStyle.None,
            ShowInTaskbar = false,
            ShowActivated = false,
        };

        internal Bench()
        {
            SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(_dispatcher));
            _dispatcher.UnhandledException += (_, eventArgs) =>
            {
                Uncaught.Add(eventArgs.Exception);
                eventArgs.Handled = true;
            };
            _window.Closed += (_, _) => WindowClosed = true;
        }

        internal List<Exception> Uncaught { get; } = [];

        internal bool WindowClosed { get; private set; }

        internal int Teardowns { get; set; }

        internal int Exits { get; private set; }

        internal void Start(Func<Task> teardown, string? directory = null)
        {
            var closing = new ClosingTeardown(_window, teardown, () => Exits++, directory);
            _window.Closing += (_, eventArgs) => closing.OnClosing(eventArgs);
            _window.Show();
        }

        // As PresenceHost.RequestExit does on the window's thread.
        internal void AskToClose() => Then(_window.Close);

        internal void Then(Action action) => _dispatcher.BeginInvoke(DispatcherPriority.Background, action);

        internal void RunUntilClosed()
        {
            var frame = new DispatcherFrame();
            var limit = new DispatcherTimer(Limit, DispatcherPriority.Normal, (_, _) => frame.Continue = false, _dispatcher);
            _window.Closed += (_, _) => _dispatcher.BeginInvoke(DispatcherPriority.ApplicationIdle, () => frame.Continue = false);
            Then(() => { });
            Dispatcher.PushFrame(frame);
            limit.Stop();
            if (!WindowClosed)
            {
                _window.Closing += (_, eventArgs) => eventArgs.Cancel = false;
                // What is left open is closed so the thread ends; the test has already seen it stay.
                ForceClose();
            }

            _dispatcher.InvokeShutdown();
        }

        private void ForceClose()
        {
            try
            {
                Application.Current?.Shutdown();
                _window.Close();
            }
            catch (InvalidOperationException)
            {
                // A window that cannot be closed now ends with its dispatcher.
            }
        }
    }
}
