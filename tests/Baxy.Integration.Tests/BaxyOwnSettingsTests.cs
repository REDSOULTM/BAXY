using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización U (identity live check 2026-10-11, I §4): bypass and the accessible mode are BAXY's own settings,
/// one file each in the profile. The interface writes them through the trusted channel and the engine reads the very
/// same confirmation-mode (ConfirmationModeStore → RiskPolicy); the chat switches them through system.settings.set,
/// which never switches bypass on (a conscious gesture in BAXY's own window).
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class BaxyOwnSettingsTests
{
    private string? _previousDataRoot;
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        _root = PrivateDataRootTestSupport.NewPath("own-settings");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", _root);
    }

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", _previousDataRoot);
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    [Test]
    public async Task TheBypassTheInterfaceWritesIsTheModeTheEngineReads()
    {
        await using Channel ui = new();
        string root = MemoryOperationProtector.ResolveDataRoot();
        PolicyDecision before = RiskPolicy.Evaluate(
            OperationRisk.Irreversible, ConfirmationModeStore.Read(root), "system.recyclebin.empty");

        FieldHttpResponse on = await ui.Trusted("PUT", "/confirmation", """{"confirmationPolicy":"bypass"}""");
        string written = File.ReadAllText(Path.Combine(root, ConfirmationModeStore.FileName));
        PolicyDecision during = RiskPolicy.Evaluate(
            OperationRisk.Irreversible, ConfirmationModeStore.Read(root), "system.recyclebin.empty");
        FieldHttpResponse shown = await ui.Trusted("GET", "/confirmation", null);
        FieldHttpResponse off = await ui.Trusted("PUT", "/confirmation", """{"confirmationPolicy":"normal"}""");
        PolicyDecision after = RiskPolicy.Evaluate(
            OperationRisk.Irreversible, ConfirmationModeStore.Read(root), "system.recyclebin.empty");

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.EqualTo(PolicyDecision.RequireConfirmation));
            Assert.That(on.Status, Is.EqualTo(200));
            Assert.That((string?)JsonNode.Parse(on.Body)!["confirmationPolicy"], Is.EqualTo("bypass"));
            Assert.That(written, Is.EqualTo("bypass"));
            Assert.That(during, Is.EqualTo(PolicyDecision.Allow));
            Assert.That((string?)JsonNode.Parse(shown.Body)!["confirmationPolicy"], Is.EqualTo("bypass"));
            Assert.That(off.Status, Is.EqualTo(200));
            Assert.That(after, Is.EqualTo(PolicyDecision.RequireConfirmation));
        });
    }

    [Test]
    public async Task OnlyTheTrustedDocumentAndANamedPolicyChangeTheConfirmationMode()
    {
        // Contracases: a page that is not BAXY's own never reaches the route, and a body naming no policy (or a
        // misspelt one) changes nothing — it no longer falls back to writing «normal».
        await using Channel ui = new();
        string root = MemoryOperationProtector.ResolveDataRoot();
        ConfirmationModeStore.Write(root, ConfirmationMode.Bypass);

        FieldHttpResponse? foreign = await ui.Adapter.TryHandleFromDocumentAsync(
            "https://example.com/index.html", "PUT", "/confirmation", """{"confirmationPolicy":"normal"}""");
        FieldHttpResponse unnamed = await ui.Trusted("PUT", "/confirmation", """{"telemetry":false}""");
        FieldHttpResponse misspelt = await ui.Trusted("PUT", "/confirmation", """{"confirmationPolicy":"bypas"}""");

        Assert.Multiple(() =>
        {
            Assert.That(foreign, Is.Null);
            Assert.That(unnamed.Status, Is.EqualTo(400));
            Assert.That(misspelt.Status, Is.EqualTo(400));
            Assert.That(ConfirmationModeStore.Read(root), Is.EqualTo(ConfirmationMode.Bypass));
        });
    }

    [Test]
    public async Task TheSettingsPanelNeverCarriesTheConfirmationMode()
    {
        // Revisión U, H1: the historical panel GETs /settings, keeps a snapshot and PUTs it back on «apply». Its
        // snapshot no longer holds the mode, and its PUT neither switches bypass back on nor fails without it
        // (after «reset to defaults»).
        await using Channel ui = new();
        string root = MemoryOperationProtector.ResolveDataRoot();

        FieldHttpResponse snapshot = await ui.Trusted("GET", "/settings", null);
        FieldHttpResponse stale = await ui.Trusted(
            "PUT", "/settings", """{"llamaUrl":"local sidecar","telemetry":false,"confirmationPolicy":"bypass"}""");
        ConfirmationMode afterStale = ConfirmationModeStore.Read(root);
        ConfirmationModeStore.Write(root, ConfirmationMode.Bypass);
        FieldHttpResponse defaults = await ui.Trusted("PUT", "/settings", """{"confirmationPolicy":"normal"}""");
        FieldHttpResponse empty = await ui.Trusted("PUT", "/settings", "{}");

        Assert.Multiple(() =>
        {
            Assert.That(JsonNode.Parse(snapshot.Body)!.AsObject().ContainsKey("confirmationPolicy"), Is.False);
            Assert.That(stale.Status, Is.EqualTo(200));
            Assert.That(afterStale, Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(defaults.Status, Is.EqualTo(200));
            Assert.That(empty.Status, Is.EqualTo(200));
            Assert.That(ConfirmationModeStore.Read(root), Is.EqualTo(ConfirmationMode.Bypass));
        });
    }

    [Test]
    public async Task TheAccessibleModePersistsInTheProfileAndIsPresentedByTheHost()
    {
        await using Channel ui = new();
        var presented = new List<bool>();
        ui.Product.ApplyPresentation = presented.Add;
        string root = MemoryOperationProtector.ResolveDataRoot();

        FieldHttpResponse first = await ui.Trusted("GET", "/accessibility", null);
        FieldHttpResponse on = await ui.Trusted("PUT", "/accessibility", """{"mode":"accessible"}""");
        bool stored = PresentationModeStore.ReadAccessible(root);
        await using Channel restarted = new();
        FieldHttpResponse afterRestart = await restarted.Trusted("GET", "/accessibility", null);
        FieldHttpResponse retired = await ui.Trusted("PUT", "/accessibility", """{"mode":"no_vidente"}""");
        FieldHttpResponse off = await ui.Trusted("PUT", "/accessibility", """{"mode":"normal"}""");

        Assert.Multiple(() =>
        {
            Assert.That((string?)JsonNode.Parse(first.Body)!["active"], Is.EqualTo("normal"));
            Assert.That((string?)JsonNode.Parse(on.Body)!["active"], Is.EqualTo("accessible"));
            Assert.That(stored, Is.True);
            Assert.That((string?)JsonNode.Parse(afterRestart.Body)!["active"], Is.EqualTo("accessible"));
            Assert.That(retired.Status, Is.EqualTo(400));
            Assert.That((string?)JsonNode.Parse(off.Body)!["active"], Is.EqualTo("normal"));
            Assert.That(PresentationModeStore.ReadAccessible(root), Is.False);
            Assert.That(presented, Is.EqualTo(new[] { false, true, false }));
        });
    }

    [Test]
    public async Task TheChatSwitchesTheAccessibleModeBothWaysWithItsPostRead()
    {
        var windows = new CountingProvider();
        BaxySettingHandler handler = Handler(windows);

        OperationOutcome on = await handler.ExecuteAsync(Invocation("""{"setting":"accessible_mode","value":1}"""), default);
        bool stored = PresentationModeStore.ReadAccessible(_root);
        OperationOutcome again = await handler.ExecuteAsync(Invocation("""{"setting":"accessible_mode","value":1}"""), default);
        OperationOutcome off = await handler.ExecuteAsync(Invocation("""{"setting":"accessible_mode","value":0}"""), default);

        Assert.Multiple(() =>
        {
            Assert.That(on.Succeeded && on.Verified, Is.True);
            Assert.That(on.Result!.Value.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(stored, Is.True);
            Assert.That(again.Succeeded, Is.True);
            Assert.That(again.Result!.Value.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(off.Succeeded, Is.True);
            Assert.That(PresentationModeStore.ReadAccessible(_root), Is.False);
            Assert.That(windows.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task TheChatNeverSwitchesBypassOnButSwitchesItOff()
    {
        var windows = new CountingProvider();
        BaxySettingHandler handler = Handler(windows);

        OperationOutcome refused = await handler.ExecuteAsync(
            Invocation("""{"setting":"confirmation_bypass","value":1}"""), default);
        ConfirmationMode afterRefusal = ConfirmationModeStore.Read(_root);
        ConfirmationModeStore.Write(_root, ConfirmationMode.Bypass);
        OperationOutcome off = await handler.ExecuteAsync(
            Invocation("""{"setting":"confirmation_bypass","value":0}"""), default);

        Assert.Multiple(() =>
        {
            Assert.That(refused.Succeeded, Is.False);
            Assert.That(refused.ErrorCode, Is.EqualTo("confirmation_bypass_interface_only"));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(afterRefusal, Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(off.Succeeded && off.Verified, Is.True);
            Assert.That(ConfirmationModeStore.Read(_root), Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(windows.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task AWindowsSettingStillGoesToWindows()
    {
        // Contracase: the night light is not BAXY's; the handler hands it on untouched.
        var windows = new CountingProvider();
        OperationOutcome outcome = await Handler(windows).ExecuteAsync(
            Invocation("""{"setting":"night_light","value":1}"""), default);

        Assert.Multiple(() =>
        {
            Assert.That(windows.Calls, Is.EqualTo(1));
            Assert.That(outcome.ErrorCode, Is.EqualTo("night_light_public_api_unavailable"));
            Assert.That(File.Exists(Path.Combine(_root, PresentationModeStore.FileName)), Is.False);
        });
    }

    [Test]
    public void BaxysSettingsAreDeclaredInTheRealCatalog()
    {
        string schema = ProductCatalog.CreateToolDescriptor(ProductCatalog.CreateDefinition("system.settings.set"))
            .ArgumentsSchema.GetRawText();
        IOperationHandler[] handlers = ExternalCapabilityHandlers.Create(new CountingProvider(), _root);

        Assert.Multiple(() =>
        {
            Assert.That(schema, Does.Contain($"\"{BaxySettingHandler.AccessibleMode}\""));
            Assert.That(schema, Does.Contain($"\"{BaxySettingHandler.ConfirmationBypass}\""));
            Assert.That(
                handlers.Single(handler => handler.Definition.Name == "system.settings.set"),
                Is.InstanceOf<BaxySettingHandler>());
        });
    }

    private BaxySettingHandler Handler(CountingProvider windows) =>
        new BaxySettingHandler(new ExternalCapabilityHandler("system.settings.set", windows), _root);

    private static OperationInvocation Invocation(string arguments) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(arguments).RootElement.Clone());

    private sealed class CountingProvider : IExternalCapabilityProvider
    {
        internal int Calls { get; private set; }

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            Calls++;
            return ValueTask.FromResult(new ExternalCapabilityReceipt(
                operation, EffectObserved: false, Verified: false, null, "night_light_public_api_unavailable"));
        }
    }

    private sealed class Channel : IAsyncDisposable
    {
        private readonly MainWindowViewModel _view = new();
        private readonly FieldTelemetrySampler _telemetry = new();

        internal Channel()
        {
            Product = new FieldProductChannel(_view, new CollectingFieldEventSink(), _telemetry, CancellationToken.None);
            Adapter = new FieldUiProductAdapter(Product);
        }

        internal FieldProductChannel Product { get; }

        internal FieldUiProductAdapter Adapter { get; }

        internal async Task<FieldHttpResponse> Trusted(string method, string path, string? body) =>
            await Adapter.HandleTrustedAsync(method, path, body)
            ?? throw new AssertionException("The trusted adapter dropped the request.");

        public async ValueTask DisposeAsync()
        {
            await Product.DisposeAsync();
            await _telemetry.DisposeAsync();
            await _view.DisposeAsync();
        }
    }
}
