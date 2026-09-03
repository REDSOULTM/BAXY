using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class FieldProductChannelParityTests
{
    [TearDown]
    public void TearDown() => FieldPublicationInjection.Reset();

    [Test]
    public async Task EmptyAndInvalidInputShareAdmissionBetweenAdapters()
    {
        await using AdapterPair pair = CreateReadyPair();
        FieldHttpResponse uiEmpty = await pair.Ui.HandleTrustedAsync(
            "POST",
            "/turn",
            """{"text":"   "}""")
            ?? throw new AssertionException("UI adapter dropped a trusted turn.");
        FieldHttpResponse conductorEmpty = await pair.Conductor.HandleHttpAsync(
            "POST",
            "/turn",
            """{"text":"   "}""");

        string tooLarge = new string('a', MissionInputContract.MaximumCharacters + 1);
        string tooLargeBody = new JsonObject { ["text"] = tooLarge }.ToJsonString();
        FieldHttpResponse uiLarge = await pair.Ui.HandleTrustedAsync(
            "POST",
            "/turn",
            tooLargeBody)
            ?? throw new AssertionException("UI adapter dropped a trusted turn.");
        FieldHttpResponse conductorLarge = await pair.Conductor.HandleHttpAsync(
            "POST",
            "/turn",
            tooLargeBody);

        Assert.Multiple(() =>
        {
            Assert.That(uiEmpty.Status, Is.EqualTo(400));
            Assert.That(conductorEmpty.Status, Is.EqualTo(uiEmpty.Status));
            Assert.That(ReadError(uiEmpty), Is.EqualTo("invalid_text"));
            Assert.That(ReadError(conductorEmpty), Is.EqualTo(ReadError(uiEmpty)));
            Assert.That(uiLarge.Status, Is.EqualTo(400));
            Assert.That(conductorLarge.Status, Is.EqualTo(uiLarge.Status));
            Assert.That(ReadError(uiLarge), Is.EqualTo("invalid_text"));
            Assert.That(ReadError(conductorLarge), Is.EqualTo(ReadError(uiLarge)));
            Assert.That(
                EventTypes(pair.UiEvents),
                Is.EqualTo(EventTypes(pair.ConductorEvents)));
        });
    }

    [Test]
    public async Task AttachmentUploadIsRejectedIdenticallyAndTurnIgnoresPaths()
    {
        await using AdapterPair pair = CreateReadyPair();
        FieldHttpResponse uiUpload = await pair.Ui.HandleTrustedAsync("POST", "/upload", null)
            ?? throw new AssertionException("UI adapter dropped a trusted upload.");
        FieldHttpResponse conductorUpload = await pair.Conductor.UploadAsync();
        string body = """{"text":"hola","attachments":["C:\\tmp\\a.txt"]}""";
        FieldHttpResponse uiTurn = await pair.Ui.HandleTrustedAsync("POST", "/turn", body)
            ?? throw new AssertionException("UI adapter dropped a trusted turn.");
        FieldHttpResponse conductorTurn = await pair.Conductor.HandleHttpAsync(
            "POST",
            "/turn",
            body);

        Assert.Multiple(() =>
        {
            Assert.That(uiUpload.Status, Is.EqualTo(501));
            Assert.That(conductorUpload.Status, Is.EqualTo(501));
            Assert.That(ReadError(uiUpload), Is.EqualTo("attachments_not_supported"));
            Assert.That(ReadError(conductorUpload), Is.EqualTo("attachments_not_supported"));
            Assert.That(uiTurn.Status, Is.EqualTo(conductorTurn.Status));
            Assert.That(ReadError(uiTurn), Is.EqualTo(ReadError(conductorTurn)));
            Assert.That(EventTypes(pair.UiEvents), Is.EqualTo(EventTypes(pair.ConductorEvents)));
        });
    }

    [Test]
    public async Task CancelAndNewSessionShareAdmissionAndPosteriorState()
    {
        await using AdapterPair pair = CreateReadyPair();
        FieldHttpResponse uiCancel = await pair.Ui.HandleTrustedAsync(
            "POST",
            "/turn",
            """{"text":"cancelar"}""")
            ?? throw new AssertionException("UI adapter dropped cancel.");
        FieldHttpResponse conductorCancel = await pair.Conductor.HandleHttpAsync(
            "POST",
            "/turn",
            """{"text":"cancelar"}""");
        FieldHttpResponse uiSession = await pair.Ui.HandleTrustedAsync(
            "POST",
            "/sessions/new",
            null)
            ?? throw new AssertionException("UI adapter dropped Nueva sesión.");
        FieldHttpResponse conductorSession = await pair.Conductor.NewSessionAsync();

        Assert.Multiple(() =>
        {
            Assert.That(uiCancel.Status, Is.EqualTo(conductorCancel.Status));
            Assert.That(ReadError(uiCancel), Is.EqualTo(ReadError(conductorCancel)));
            Assert.That(uiSession.Status, Is.EqualTo(200));
            Assert.That(conductorSession.Status, Is.EqualTo(200));
            Assert.That(
                pair.UiView.Messages.Count,
                Is.EqualTo(pair.Conductor.ViewModel.Messages.Count));
            Assert.That(
                pair.UiView.HasPendingPlan,
                Is.EqualTo(pair.Conductor.ViewModel.HasPendingPlan));
            Assert.That(pair.UiView.IsBusy, Is.EqualTo(pair.Conductor.ViewModel.IsBusy));
            Assert.That(
                pair.UiView.Messages.Any(static message => !message.IsUser),
                Is.True);
        });
    }

    [Test]
    public async Task UntrustedOriginNeverReachesAdmissionOnTheUiAdapter()
    {
        await using AdapterPair pair = CreateReadyPair();
        FieldHttpResponse? ignored = await pair.Ui.TryHandleFromDocumentAsync(
            "https://example.com/index.html",
            "POST",
            "/turn",
            """{"text":"hola"}""");
        FieldHttpResponse conductor = await pair.Conductor.HandleHttpAsync(
            "POST",
            "/turn",
            """{"text":"hola"}""");

        Assert.Multiple(() =>
        {
            Assert.That(ignored, Is.Null);
            Assert.That(pair.UiEvents.Snapshot(), Is.Empty);
            Assert.That(conductor.Status, Is.EqualTo(200));
            Assert.That(
                FieldUiProductAdapter.AcceptsDocumentSource("https://baxy.local/index.html"),
                Is.True);
        });
    }

    [Test]
    public void BridgeDelegatesHttpToTheSharedChannelAndKeepsOriginPolicy()
    {
        string bridge = File.ReadAllText(RepositoryPath("src", "Baxy.App", "FieldUiBridge.cs"));
        string channel = File.ReadAllText(RepositoryPath("src", "Baxy.App", "FieldProductChannel.cs"));
        string host = File.ReadAllText(RepositoryPath("src", "Baxy.App", "ProductConductorHost.cs"));
        string launcher = File.ReadAllText(RepositoryPath("scripts", "run_baxy_conductor.ps1"));
        Assert.Multiple(() =>
        {
            Assert.That(bridge, Does.Contain("_channel.HandleHttpAsync"));
            Assert.That(bridge, Does.Contain("HistoricalFieldOriginPolicy.IsTrustedDocumentSource"));
            Assert.That(bridge, Does.Not.Contain("FieldBridgeContract.TryAcceptTurn"));
            Assert.That(channel, Does.Contain("FieldBridgeContract.TryAcceptTurn"));
            Assert.That(channel, Does.Contain("new MissionInput(text, MissionInputSource.Text)"));
            Assert.That(host, Does.Contain("ProductConductor.Create"));
            Assert.That(host, Does.Not.Contain("HttpListener"));
            Assert.That(host, Does.Not.Contain("MapGet"));
            Assert.That(launcher, Does.Contain("WaitForExit"));
            Assert.That(launcher, Does.Contain("UseShellExecute = $false"));
            Assert.That(launcher, Does.Not.Contain("HttpListener"));
        });
    }

    private static AdapterPair CreateReadyPair()
    {
        var uiView = new MainWindowViewModel();
        var conductorView = new MainWindowViewModel();
        MarkReady(uiView);
        MarkReady(conductorView);
        var uiEvents = new CollectingFieldEventSink();
        var uiTelemetry = new FieldTelemetrySampler();
        var uiChannel = new FieldProductChannel(
            uiView,
            uiEvents,
            uiTelemetry,
            CancellationToken.None);
        var ui = new FieldUiProductAdapter(uiChannel);
        ProductConductor conductor = ProductConductor.Create(
            conductorView,
            CancellationToken.None,
            ownsViewModel: true);
        return new AdapterPair(
            uiView,
            uiEvents,
            uiChannel,
            uiTelemetry,
            ui,
            conductor);
    }

    private static void MarkReady(MainWindowViewModel viewModel)
    {
        PropertyInfo ready = typeof(MainWindowViewModel).GetProperty(
            nameof(MainWindowViewModel.IsReady))!;
        ready.SetValue(viewModel, true);
    }

    private static string? ReadError(FieldHttpResponse response)
    {
        try
        {
            return JsonNode.Parse(response.Body)?["error"]?.GetValue<string>();
        }
        catch (System.Text.Json.JsonException)
        {
            return null;
        }
    }

    private static string[] EventTypes(CollectingFieldEventSink sink) =>
        [.. sink.Snapshot().Select(static item => (string?)item["type"] ?? string.Empty)];

    private static string RepositoryPath(params string[] path)
    {
        DirectoryInfo? current = new(TestContext.CurrentContext.TestDirectory);
        while (current is not null && !File.Exists(Path.Combine(current.FullName, "Baxy.slnx")))
        {
            current = current.Parent;
        }

        if (current is null)
        {
            throw new AssertionException("Could not locate the BAXY repository root.");
        }

        return path.Aggregate(current.FullName, Path.Combine);
    }

    private sealed class AdapterPair(
        MainWindowViewModel uiView,
        CollectingFieldEventSink uiEvents,
        FieldProductChannel uiChannel,
        FieldTelemetrySampler uiTelemetry,
        FieldUiProductAdapter ui,
        ProductConductor conductor) : IAsyncDisposable
    {
        internal MainWindowViewModel UiView { get; } = uiView;

        internal CollectingFieldEventSink UiEvents { get; } = uiEvents;

        internal FieldProductChannel UiChannel { get; } = uiChannel;

        internal FieldUiProductAdapter Ui { get; } = ui;

        internal ProductConductor Conductor { get; } = conductor;

        internal CollectingFieldEventSink ConductorEvents => Conductor.Sink;

        public async ValueTask DisposeAsync()
        {
            await UiChannel.DisposeAsync();
            await uiTelemetry.DisposeAsync();
            await UiView.DisposeAsync();
            await Conductor.DisposeAsync();
        }
    }
}
