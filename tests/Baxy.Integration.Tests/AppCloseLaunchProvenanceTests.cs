using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// v3 r22 uso real, «cerrar sin confirmar lo que no pierde nada» (pasada r18 t3-c18 t4 «ya ciérrala» sobre la
/// Calculadora que BAXY abrió y sólo clicó → pidió confirmación): the Core's handlers keep the launch provenance the
/// window provider reads. A verified app.open that launched the application notes it; one that found it running does
/// not; a pointing operation (a click) leaves it unwritten and any operation that may write marks it written. The
/// app.close catalog label does not move, and a close the application answered with its own dialog comes back as
/// close_prompted with the window still there.
/// </summary>
[TestFixture]
public sealed class AppCloseLaunchProvenanceTests
{
    private const int LaunchedProcess = 4242;
    private const long LaunchedWindow = 11668164;

    [Test]
    public async Task AVerifiedLaunchIsNotedAndAClickLeavesItUnwritten()
    {
        var provenance = new LaunchProvenance(static _ => null, Watching());
        (OperationOutcome opened, long creation) = await OpenAsync(provenance, alreadyRunning: false);
        await InvokeAsync("input.visible.click", provenance);

        Assert.Multiple(() =>
        {
            Assert.That(opened.Verified, Is.True);
            Assert.That(provenance.LaunchedAndUnwritten(LaunchedWindow, LaunchedProcess, creation), Is.True);
        });
    }

    [Test]
    public async Task AnApplicationThatWasAlreadyRunningIsNotNoted()
    {
        // Contracaso: the person's own Calculator (alreadyRunning=true) keeps asking.
        var provenance = new LaunchProvenance(static _ => null, Watching());
        (OperationOutcome opened, long creation) = await OpenAsync(provenance, alreadyRunning: true);

        Assert.Multiple(() =>
        {
            Assert.That(opened.Verified, Is.True);
            Assert.That(provenance.LaunchedAndUnwritten(LaunchedWindow, LaunchedProcess, creation), Is.False);
        });
    }

    [Test]
    public async Task AProcessCreatedBeforeTheOpeningIsNotNotedEvenIfTheProviderSaysLaunched()
    {
        // v3 r22 revisión (bloqueante 1, sonda pid 5150 creado ayer con alreadyRunning=false): a window that appears
        // inside a process the person already had (a browser resident without windows, an application in the tray)
        // is not BAXY's, whatever the provider's reuse flag says.
        var provenance = new LaunchProvenance(static _ => null, Watching());
        long yesterday = DateTime.UtcNow.AddDays(-1).Ticks;
        (OperationOutcome opened, long creation) = await OpenAsync(provenance, alreadyRunning: false, yesterday);

        Assert.Multiple(() =>
        {
            Assert.That(opened.Verified, Is.True);
            Assert.That(creation, Is.EqualTo(yesterday));
            Assert.That(provenance.LaunchedAndUnwritten(LaunchedWindow, LaunchedProcess, creation), Is.False);
        });
    }

    [Test]
    public void OnlyAProcessCreatedSinceTheOpeningBeganCountsAsLaunchedByIt()
    {
        long mark = DateTime.UtcNow.Ticks;
        Assert.Multiple(() =>
        {
            Assert.That(AppOpenHandler.LaunchedByThisOpening(mark, mark), Is.True);
            Assert.That(AppOpenHandler.LaunchedByThisOpening(mark + 1, mark), Is.True);
            // Within one tick of the kernel's coarse clock (the stamp of a process created just after the mark).
            Assert.That(AppOpenHandler.LaunchedByThisOpening(mark - TimeSpan.FromMilliseconds(15).Ticks, mark),
                Is.True);
            Assert.That(AppOpenHandler.LaunchedByThisOpening(mark - TimeSpan.FromSeconds(1).Ticks, mark), Is.False);
            Assert.That(AppOpenHandler.LaunchedByThisOpening(null, mark), Is.False);
        });
    }

    [Test]
    public async Task AClickThatTypesItsSearchMarksTheLaunchedApplicationWritten()
    {
        // v3 r22 revisión (bloqueante 5, sonda {label:'Buscar', search:'texto escrito'}): the click types its search
        // into what it opened (SearchBurst.TypeAsync), so the window BAXY launched now holds text BAXY wrote.
        var provenance = new LaunchProvenance(static _ => null, Watching());
        (_, long creation) = await OpenAsync(provenance, alreadyRunning: false);
        await InvokeAsync("input.visible.click", provenance, """{"label":"Buscar","search":"texto escrito"}""");

        Assert.That(provenance.LaunchedAndUnwritten(LaunchedWindow, LaunchedProcess, creation), Is.False);
    }

    [TestCase("""{"label":"Buscar"}""")]
    [TestCase("""{"label":"Buscar","search":null}""")]
    [TestCase("""{"label":"Buscar","search":""}""")]
    public async Task AClickWithoutTextToTypeLeavesItUnwritten(string arguments)
    {
        // Contracaso: a plain click (no search, or an empty one) types nothing.
        var provenance = new LaunchProvenance(static _ => null, Watching());
        (_, long creation) = await OpenAsync(provenance, alreadyRunning: false);
        await InvokeAsync("input.visible.click", provenance, arguments);

        Assert.That(provenance.LaunchedAndUnwritten(LaunchedWindow, LaunchedProcess, creation), Is.True);
    }

    [Test]
    public void EveryTypedArgumentOfAPointingOperationIsDeclaredInTheRealCatalog()
    {
        foreach ((string operation, string[] typed) in ExternalCapabilityHandler.PointingOperationsTypedArguments)
        {
            OperationArgumentsSchema schema = ProductCatalog.Descriptors
                .Single(descriptor => descriptor.Name == operation).ArgumentsSchema;
            foreach (string name in typed)
            {
                Assert.That(schema.Properties.Select(static property => property.Name), Does.Contain(name),
                    operation);
            }
        }

        Assert.That(ExternalCapabilityHandler.PointingOperationsTypedArguments["input.visible.click"],
            Does.Contain("search"));
    }

    [TestCase("input.text.type")]
    [TestCase("clipboard.paste")]
    [TestCase("input.key.press")]
    public async Task AnOperationThatMayWriteMarksTheLaunchedApplicationWritten(string operation)
    {
        // Contracaso: a window BAXY opened and wrote into keeps asking.
        var provenance = new LaunchProvenance(static _ => null, Watching());
        (_, long creation) = await OpenAsync(provenance, alreadyRunning: false);
        await InvokeAsync(operation, provenance);

        Assert.That(provenance.LaunchedAndUnwritten(LaunchedWindow, LaunchedProcess, creation), Is.False);
    }

    [TestCase("input.visible.click", "{}", false)]
    [TestCase("input.visible.click", """{"label":"Buscar","search":"texto escrito"}""", true)]
    [TestCase("input.scroll", "{}", false)]
    [TestCase("input.visible.controls", "{}", false)]
    [TestCase("input.text.type", "{}", true)]
    [TestCase("clipboard.paste", "{}", true)]
    [TestCase("input.key.press", "{}", true)]
    [TestCase("input.select.all", "{}", true)]
    public void WhatMayWriteIsReadFromTheRealCatalog(string operation, string arguments, bool writes) =>
        Assert.That(ExternalCapabilityHandler.MayWriteIntoAWindow(
                ProductCatalog.CreateDefinition(operation), JsonDocument.Parse(arguments).RootElement),
            Is.EqualTo(writes));

    [Test]
    public async Task AClosePromptedByTheApplicationIsNotDoneAndSaysSo()
    {
        IOperationHandler close = WindowControlHandlers.Create(new PromptingProvider())
            .Single(handler => handler.Definition.Name == "app.close");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([close]), journal);

        OperationResponse response = await engine.ExecuteAsync(new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            "app.close",
            JsonDocument.Parse("""{"windowId":"win_calculator"}""").RootElement.Clone()), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.Not.EqualTo(OperationStatuses.Completed));
            Assert.That(response.ErrorCode, Is.EqualTo(WindowControlErrorCodes.ClosePrompted));
            Assert.That(response.Result?.GetProperty("closePrompted").GetBoolean(), Is.True);
            Assert.That(response.Result?.GetProperty("windowClosed").GetBoolean(), Is.False);
            Assert.That(ProductCatalog.GetRequired("app.close").Risk, Is.EqualTo(OperationRisks.WorkLoss));
        });
    }

    // The person's input watched since long before the case and none of it reached the launched window.
    private static PersonInputLedger Watching()
    {
        var ledger = new PersonInputLedger(static () => true, static () => true, static () => 1);
        ledger.EnsureWatching();
        return ledger;
    }

    private static async Task<(OperationOutcome Outcome, long Creation)> OpenAsync(
        LaunchProvenance provenance, bool alreadyRunning, long? createdAt = null)
    {
        var invocation = new OperationInvocation(
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            JsonDocument.Parse("""{"appId":"windows.calculator"}""").RootElement.Clone());
        long creation = 0;
        ApplicationOpenResult Open()
        {
            // The process is created while the opening runs, unless the case says when it was.
            creation = createdAt ?? DateTime.UtcNow.Ticks;
            var receipt = new ApplicationLaunchReceipt(
                invocation.InvocationId,
                ApplicationIds.Calculator,
                LaunchIssued: !alreadyRunning,
                ReusedExisting: alreadyRunning,
                LaunchedProcess,
                creation,
                @"C:\Program Files\WindowsApps\Microsoft.WindowsCalculator_8wekyb3d8bbwe\CalculatorApp.exe",
                PackageFamilyName: null,
                PackageFullName: null,
                LaunchedWindow,
                ErrorCode: null);
            return new ApplicationOpenResult(
                Succeeded: true, Verified: true, "Calculadora", alreadyRunning, LaunchedProcess, LaunchedWindow, null,
                receipt);
        }

        OperationOutcome outcome = await new AppOpenHandler(new OpenProvider(Open), provenance)
            .ExecuteAsync(invocation, CancellationToken.None);
        return (outcome, creation);
    }

    private static async Task InvokeAsync(string operation, LaunchProvenance provenance, string arguments = "{}")
    {
        var handler = new ExternalCapabilityHandler(operation, new NoEffectProvider(), provenance);
        _ = await handler.ExecuteAsync(new OperationInvocation(
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            JsonDocument.Parse(arguments).RootElement.Clone()), CancellationToken.None);
    }

    private sealed class OpenProvider(Func<ApplicationOpenResult> open) : IApplicationOpenProvider
    {
        public ValueTask<ApplicationOpenResult> OpenAsync(
            ApplicationOpenRequest request, CancellationToken cancellationToken) =>
            ValueTask.FromResult(open());
    }

    private sealed class NoEffectProvider : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ExternalCapabilityReceipt(operation, false, false, null, "not_used"));
    }

    private sealed class PromptingProvider : IWindowControlProvider
    {
        public bool HoldsNoDocument(string windowId) => true;

        public ValueTask<WindowCloseResult> CloseAsync(string windowId, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new WindowCloseResult(
                false, true, 77, WindowControlErrorCodes.ClosePrompted, ClosePrompted: true));

        public ValueTask<WindowResolveResult> ResolveForegroundAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowResolveResult> ResolveAsync(
            string processName, int limit, CancellationToken cancellationToken, bool byTitle = false, int offset = 0) =>
            throw new AssertionException("not used");

        public ValueTask<WindowActionResult> ExecuteAsync(
            string windowId, WindowControlAction action, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowActionResult> SetBoundsAsync(
            string windowId, int? x, int? y, int? width, int? height, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");
    }
}
