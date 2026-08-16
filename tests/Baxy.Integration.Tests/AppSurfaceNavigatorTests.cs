using System.Threading;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Baxy.App.Presentation;
using Microsoft.Web.WebView2.Wpf;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[Apartment(ApartmentState.STA)]
public sealed class AppSurfaceNavigatorTests
{
    [Test]
    public void DefaultCatalogCreatesTheLoadingSurfaceLazily()
    {
        AppSurfaceCatalog catalog = AppSurfaceCatalog.CreateDefault();

        Assert.That(
            catalog.TryCreate(
                AppSurfaceIds.FieldLoading,
                out AppSurfaceSession? session),
            Is.True);
        Assert.That(session!.Content, Is.TypeOf<FieldLoadingSurface>());

        session.DisposeAsync().AsTask().GetAwaiter().GetResult();
    }

    [Test]
    public void MainWindowPresenterPreservesTheFieldWhileASurfaceIsActive()
    {
        var field = new WebView2();
        var host = new ContentControl { Visibility = Visibility.Collapsed };
        var presenter = new MainWindowSurfacePresenter(field, host);
        var content = new FrameworkElement();
        var session = new AppSurfaceSession(content);

        presenter.ShowSurface(session);

        Assert.Multiple(() =>
        {
            Assert.That(field.Visibility, Is.EqualTo(Visibility.Collapsed));
            Assert.That(host.Visibility, Is.EqualTo(Visibility.Visible));
            Assert.That(host.Content, Is.SameAs(content));
        });

        presenter.ShowField();

        Assert.Multiple(() =>
        {
            Assert.That(field.Visibility, Is.EqualTo(Visibility.Visible));
            Assert.That(host.Visibility, Is.EqualTo(Visibility.Collapsed));
            Assert.That(host.Content, Is.Null);
        });

        session.DisposeAsync().AsTask().GetAwaiter().GetResult();
        field.Dispose();
    }

    [Test]
    public void MainWindowPresenterRejectsCrossThreadTransitions()
    {
        var field = new WebView2();
        var host = new ContentControl();
        var presenter = new MainWindowSurfacePresenter(field, host);

        Exception? exception = Task.Run(presenter.ShowField)
            .ContinueWith(
                static task => task.Exception?.GetBaseException(),
                TaskScheduler.Default)
            .GetAwaiter()
            .GetResult();

        Assert.That(exception, Is.TypeOf<InvalidOperationException>());
        field.Dispose();
    }

    [Test]
    public void CatalogRejectsReservedDuplicateAndMalformedIds()
    {
        Assert.Multiple(() =>
        {
            Assert.That(
                () => Catalog(
                    Descriptor(AppSurfaceIds.HistoricalField)),
                Throws.ArgumentException);
            Assert.That(
                () => Catalog(
                    Descriptor("fixture"),
                    Descriptor("fixture")),
                Throws.ArgumentException);
            Assert.That(
                () => Catalog(Descriptor("Fixture")),
                Throws.ArgumentException);
            Assert.That(
                () => Catalog(Descriptor("fixture..detail")),
                Throws.ArgumentException);
        });
    }

    [Test]
    public void UnknownSurfaceLeavesTheHistoricalFieldUntouched()
    {
        var presenter = new RecordingPresenter();
        var navigator = new AppSurfaceNavigator(
            Catalog(Descriptor("fixture")),
            presenter);
        try
        {
            AppSurfaceSession? result = Open(navigator, "missing");

            Assert.Multiple(() =>
            {
                Assert.That(result, Is.Null);
                Assert.That(navigator.CurrentId, Is.EqualTo(AppSurfaceIds.HistoricalField));
                Assert.That(presenter.FieldVisible, Is.True);
                Assert.That(presenter.Surface, Is.Null);
                Assert.That(presenter.SurfacePresentations, Is.Zero);
            });
        }
        finally
        {
            Dispose(navigator);
        }
    }

    [Test]
    public void RegisteredSurfaceOpensLazilyAndReturnsToTheSameField()
    {
        int factoryCalls = 0;
        var lifetime = new CountingLifetime();
        var content = new FrameworkElement();
        var presenter = new RecordingPresenter();
        var navigator = new AppSurfaceNavigator(
            Catalog(new AppSurfaceDescriptor(
                "fixture",
                () =>
                {
                    factoryCalls++;
                    return new AppSurfaceSession(content, lifetime);
                })),
            presenter);
        try
        {
            Assert.That(factoryCalls, Is.Zero);
            AppSurfaceSession? session = Open(navigator, "fixture");

            Assert.Multiple(() =>
            {
                Assert.That(session, Is.Not.Null);
                Assert.That(session!.Content, Is.SameAs(content));
                Assert.That(factoryCalls, Is.EqualTo(1));
                Assert.That(navigator.CurrentId, Is.EqualTo("fixture"));
                Assert.That(presenter.FieldVisible, Is.False);
                Assert.That(presenter.Surface, Is.SameAs(content));
            });

            ReturnToField(navigator);

            Assert.Multiple(() =>
            {
                Assert.That(navigator.CurrentId, Is.EqualTo(AppSurfaceIds.HistoricalField));
                Assert.That(presenter.FieldVisible, Is.True);
                Assert.That(presenter.Surface, Is.Null);
                Assert.That(lifetime.DisposeCalls, Is.EqualTo(1));
            });
        }
        finally
        {
            Dispose(navigator);
        }

        Assert.That(lifetime.DisposeCalls, Is.EqualTo(1));
    }

    [Test]
    public void FailingFactoryNeverHidesTheHistoricalField()
    {
        var presenter = new RecordingPresenter();
        var navigator = new AppSurfaceNavigator(
            Catalog(new AppSurfaceDescriptor(
                "broken",
                static () => throw new InvalidOperationException("fixture failure"))),
            presenter);
        try
        {
            Assert.That(
                () => Open(navigator, "broken"),
                Throws.TypeOf<InvalidOperationException>());
            Assert.Multiple(() =>
            {
                Assert.That(navigator.CurrentId, Is.EqualTo(AppSurfaceIds.HistoricalField));
                Assert.That(presenter.FieldVisible, Is.True);
                Assert.That(presenter.Surface, Is.Null);
            });
        }
        finally
        {
            Dispose(navigator);
        }
    }

    [Test]
    public void FailingPresentationDisposesTheCandidateAndKeepsTheField()
    {
        var lifetime = new CountingLifetime();
        var presenter = new RecordingPresenter { FailPresentation = true };
        var navigator = new AppSurfaceNavigator(
            Catalog(Descriptor("broken", lifetime)),
            presenter);
        try
        {
            Assert.That(
                () => Open(navigator, "broken"),
                Throws.TypeOf<InvalidOperationException>());
            Assert.Multiple(() =>
            {
                Assert.That(navigator.CurrentId, Is.EqualTo(AppSurfaceIds.HistoricalField));
                Assert.That(presenter.FieldVisible, Is.True);
                Assert.That(presenter.Surface, Is.Null);
                Assert.That(lifetime.DisposeCalls, Is.EqualTo(1));
            });
        }
        finally
        {
            Dispose(navigator);
        }
    }

    [Test]
    public void AdditionalFactoryComposesWithoutChangingTheNavigator()
    {
        var firstLifetime = new CountingLifetime();
        var secondLifetime = new CountingLifetime();
        var presenter = new RecordingPresenter();
        var navigator = new AppSurfaceNavigator(
            Catalog(
                Descriptor("first", firstLifetime),
                Descriptor("second", secondLifetime)),
            presenter);
        try
        {
            _ = Open(navigator, "first");
            _ = Open(navigator, "second");

            Assert.Multiple(() =>
            {
                Assert.That(navigator.CurrentId, Is.EqualTo("second"));
                Assert.That(presenter.SurfacePresentations, Is.EqualTo(2));
                Assert.That(firstLifetime.DisposeCalls, Is.EqualTo(1));
                Assert.That(secondLifetime.DisposeCalls, Is.Zero);
            });
        }
        finally
        {
            Dispose(navigator);
        }

        Assert.That(secondLifetime.DisposeCalls, Is.EqualTo(1));
    }

    [Test]
    public void CorrelatedReturnDoesNotCloseANewerSurface()
    {
        var firstLifetime = new CountingLifetime();
        var secondLifetime = new CountingLifetime();
        var presenter = new RecordingPresenter();
        var navigator = new AppSurfaceNavigator(
            Catalog(
                Descriptor("first", firstLifetime),
                Descriptor("second", secondLifetime)),
            presenter);
        try
        {
            AppSurfaceSession first = Open(navigator, "first")
                ?? throw new AssertionException("First surface was not created.");
            AppSurfaceSession second = Open(navigator, "second")
                ?? throw new AssertionException("Second surface was not created.");

            bool returned = navigator
                .ReturnToFieldIfCurrentAsync(first)
                .AsTask()
                .GetAwaiter()
                .GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(returned, Is.False);
                Assert.That(navigator.CurrentId, Is.EqualTo("second"));
                Assert.That(presenter.FieldVisible, Is.False);
                Assert.That(presenter.Surface, Is.SameAs(second.Content));
                Assert.That(firstLifetime.DisposeCalls, Is.EqualTo(1));
                Assert.That(secondLifetime.DisposeCalls, Is.Zero);
            });
        }
        finally
        {
            Dispose(navigator);
        }

        Assert.That(secondLifetime.DisposeCalls, Is.EqualTo(1));
    }

    [Test]
    public void FieldStatusTransitionNeverReplacesAnotherActiveSurface()
    {
        var presenter = new RecordingPresenter();
        var navigator = new AppSurfaceNavigator(
            Catalog(
                Descriptor("fixture"),
                Descriptor(AppSurfaceIds.FieldLoading)),
            presenter);
        try
        {
            AppSurfaceSession fixture = Open(navigator, "fixture")
                ?? throw new AssertionException("Fixture surface was not created.");

            AppSurfaceSession? blocked = navigator
                .OpenFromFieldAsync(AppSurfaceIds.FieldLoading)
                .AsTask()
                .GetAwaiter()
                .GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(blocked, Is.Null);
                Assert.That(navigator.CurrentId, Is.EqualTo("fixture"));
                Assert.That(presenter.Surface, Is.SameAs(fixture.Content));
            });

            ReturnToField(navigator);
            AppSurfaceSession? loading = navigator
                .OpenFromFieldAsync(AppSurfaceIds.FieldLoading)
                .AsTask()
                .GetAwaiter()
                .GetResult();
            AppSurfaceSession? repeated = navigator
                .OpenFromFieldAsync(AppSurfaceIds.FieldLoading)
                .AsTask()
                .GetAwaiter()
                .GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(loading, Is.Not.Null);
                Assert.That(repeated, Is.SameAs(loading));
                Assert.That(
                    navigator.CurrentId,
                    Is.EqualTo(AppSurfaceIds.FieldLoading));
            });
        }
        finally
        {
            Dispose(navigator);
        }
    }

    [Test]
    public void AsynchronousDisposalResumesPresentationOnTheUiDispatcher()
    {
        var completion = new TaskCompletionSource<Exception?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var thread = new Thread(() =>
        {
            Dispatcher dispatcher = Dispatcher.CurrentDispatcher;
            _ = dispatcher.InvokeAsync(
                async () =>
                {
                    try
                    {
                        var presenter = new DispatcherPresenter(dispatcher);
                        var navigator = new AppSurfaceNavigator(
                            Catalog(
                                Descriptor("first", new AsynchronousLifetime()),
                                Descriptor("second")),
                            presenter);

                        _ = await navigator.OpenAsync("first");
                        _ = await navigator.OpenAsync("second");
                        await navigator.DisposeAsync();

                        Assert.That(presenter.Presentations, Is.EqualTo(2));
                        completion.TrySetResult(null);
                    }
                    catch (Exception exception)
                    {
                        completion.TrySetResult(exception);
                    }
                    finally
                    {
                        dispatcher.BeginInvokeShutdown(
                            DispatcherPriority.Background);
                    }
                });
            Dispatcher.Run();
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();

        Exception? failure = completion.Task.GetAwaiter().GetResult();
        thread.Join();

        Assert.That(failure, Is.Null);
    }

    [Test]
    public void DisposalFailureStillRestoresTheHistoricalField()
    {
        var presenter = new RecordingPresenter();
        var navigator = new AppSurfaceNavigator(
            Catalog(Descriptor("fixture", new FailingLifetime())),
            presenter);
        _ = Open(navigator, "fixture");

        Assert.That(
            () => Dispose(navigator),
            Throws.TypeOf<InvalidOperationException>());
        Assert.Multiple(() =>
        {
            Assert.That(navigator.CurrentId, Is.EqualTo(AppSurfaceIds.HistoricalField));
            Assert.That(presenter.FieldVisible, Is.True);
            Assert.That(presenter.Surface, Is.Null);
        });

        Assert.That(() => Dispose(navigator), Throws.Nothing);
    }

    private static AppSurfaceCatalog Catalog(
        params AppSurfaceDescriptor[] descriptors) =>
        new(descriptors);

    private static AppSurfaceDescriptor Descriptor(
        string id,
        IAsyncDisposable? lifetime = null) =>
        new(
            id,
            () => new AppSurfaceSession(new FrameworkElement(), lifetime));

    private static AppSurfaceSession? Open(
        AppSurfaceNavigator navigator,
        string id) =>
        navigator.OpenAsync(id).AsTask().GetAwaiter().GetResult();

    private static void ReturnToField(AppSurfaceNavigator navigator) =>
        navigator.ReturnToFieldAsync().AsTask().GetAwaiter().GetResult();

    private static void Dispose(AppSurfaceNavigator navigator) =>
        navigator.DisposeAsync().AsTask().GetAwaiter().GetResult();

    private sealed class RecordingPresenter : IAppSurfacePresenter
    {
        internal bool FieldVisible { get; private set; } = true;

        internal FrameworkElement? Surface { get; private set; }

        internal int SurfacePresentations { get; private set; }

        internal bool FailPresentation { get; init; }

        public void ShowField()
        {
            FieldVisible = true;
            Surface = null;
        }

        public void ShowSurface(AppSurfaceSession session)
        {
            FieldVisible = false;
            Surface = session.Content;
            if (FailPresentation)
            {
                throw new InvalidOperationException("fixture presentation failure");
            }

            SurfacePresentations++;
        }
    }

    private sealed class CountingLifetime : IAsyncDisposable
    {
        internal int DisposeCalls { get; private set; }

        public ValueTask DisposeAsync()
        {
            DisposeCalls++;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class FailingLifetime : IAsyncDisposable
    {
        public ValueTask DisposeAsync() =>
            ValueTask.FromException(
                new InvalidOperationException("fixture disposal failure"));
    }

    private sealed class AsynchronousLifetime : IAsyncDisposable
    {
        public async ValueTask DisposeAsync()
        {
            await Task.Delay(1).ConfigureAwait(false);
        }
    }

    private sealed class DispatcherPresenter(Dispatcher dispatcher)
        : IAppSurfacePresenter
    {
        internal int Presentations { get; private set; }

        public void ShowField()
        {
            dispatcher.VerifyAccess();
        }

        public void ShowSurface(AppSurfaceSession session)
        {
            dispatcher.VerifyAccess();
            Presentations++;
        }
    }
}
