using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// v3 r6 lectores (t2-r4 c04-5 «ya quedó, cierra configuración porfa» → «¿Quieres confirmar que cierre la ventana de
/// Configuración…?»): app.close keeps its work_loss label, but the Core's handler tells the engine when the window it
/// closes holds no document of the person; that close goes straight and is still verified. A window with a document,
/// or one the provider cannot place, asks first.
/// </summary>
[TestFixture]
public sealed class AppCloseDocumentRiskTests
{
    [Test]
    public async Task ClosingAWindowWithoutDocumentsGoesWithoutAsking()
    {
        var provider = new Provider(documentless: "win_settings");
        using var journal = new InMemoryInvocationJournal();
        using var engine = Engine(provider, journal);

        OperationResponse response = await engine.ExecuteAsync(Close("win_settings"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(response.Verified, Is.True);
            Assert.That(provider.CloseCalls, Is.EqualTo(1));
            // Encargo H1 (tandas fin1/fin2 t2-c03 t2): the receipt names what it closed, as Windows wrote its title.
            Assert.That(response.Result?.GetProperty("title").GetString(), Is.EqualTo("Configuración"));
        });
    }

    [Test]
    public async Task AClosedWindowWithoutATitleIsNamedByNothingInTheReceipt()
    {
        // Contracaso: no title read before the close, no «title» in the receipt (nothing from the request fills it).
        var provider = new Provider(documentless: "win_settings", title: null);
        using var journal = new InMemoryInvocationJournal();
        using var engine = Engine(provider, journal);

        OperationResponse response = await engine.ExecuteAsync(Close("win_settings"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(response.Result?.TryGetProperty("title", out _), Is.False);
        });
    }

    [Test]
    public async Task ClosingAWindowThatMayHoldADocumentStillAsks()
    {
        // Contracaso: Word, Notepad or Paint (or any window not listed as documentless) keeps asking before the close.
        var provider = new Provider(documentless: "win_settings");
        using var journal = new InMemoryInvocationJournal();
        using var engine = Engine(provider, journal);

        OperationResponse response = await engine.ExecuteAsync(Close("win_word"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(provider.CloseCalls, Is.Zero);
        });
    }

    [Test]
    public void TheCatalogLabelOfTheOperationDoesNotMove()
    {
        Assert.That(ProductCatalog.GetRequired("app.close").Risk, Is.EqualTo(OperationRisks.WorkLoss));
        // Closing everything at once has no such assessment: it keeps its own declared risk.
        IOperationHandler closeAll = WindowControlHandlers.Create(new Provider(documentless: "win_settings"))
            .Single(handler => handler.Definition.Name == "window.close.all");
        Assert.That(closeAll, Is.Not.InstanceOf<IInvocationRiskAssessor>());
    }

    private static MissionEngine Engine(Provider provider, IInvocationJournal journal)
    {
        IOperationHandler close = WindowControlHandlers.Create(provider)
            .Single(handler => handler.Definition.Name == "app.close");
        return new MissionEngine(new OperationRegistry([close]), journal);
    }

    private static OperationRequest Close(string windowId) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "app.close",
        JsonDocument.Parse($$"""{"windowId":"{{windowId}}"}""").RootElement.Clone());

    private sealed class Provider(string documentless, string? title = "Configuración") : IWindowControlProvider
    {
        public int CloseCalls { get; private set; }

        public bool HoldsNoDocument(string windowId) => windowId == documentless;

        public ValueTask<WindowCloseResult> CloseAsync(string windowId, CancellationToken cancellationToken)
        {
            CloseCalls++;
            return ValueTask.FromResult(new WindowCloseResult(true, true, 4242, null, Title: title));
        }

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
