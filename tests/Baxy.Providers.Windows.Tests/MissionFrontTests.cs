using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Estabilización D (the owner's decision of 2026-10-10, «no molestar» in its simple form): an act of a computer-use
/// mission (its «window» argument, the catalog's mark of a mission's act) is done with the mission's window in front:
/// the provider asks the lease to take that front before the act (IForegroundLease.TakeForMissionAsync, its rules in
/// ForegroundSequenceTests) and sends nothing when it is refused. A look, an opening and an act of no mission ask nothing.
/// </summary>
[TestFixture]
public sealed class MissionFrontTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    [TestCase("input.visible.click", """{"label":"Buscar","window":18016}""")]
    [TestCase("input.key.press", """{"key":"enter","window":18016}""")]
    [TestCase("input.text.type", """{"text":"hola","window":18016}""")]
    [TestCase("input.scroll", """{"amount":3,"direction":"down","window":18016}""")]
    [TestCase("input.pointer.drag", """{"from":1,"label":"a","window":18016}""")]
    public async Task AMissionsActTakesItsWindowsFrontBeforeItIsSent(string operation, string arguments)
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter(operation, lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(lease.Taken, Is.EqualTo(new nint[] { 18016 }));
            Assert.That(adapter.FrontTakenWhenSent, Is.True, "taken before the act, never after");
            Assert.That(lease.Ended, Is.EqualTo(new[] { operation }), "the lease is told the act ended");
        });
    }

    // Nothing is sent when the person does not pause or the window does not come to the front: never behind them.
    [TestCase("input_user_not_paused")]
    [TestCase("input_window_not_in_front")]
    [TestCase("input_mission_ended")]
    public async Task AnActWhoseFrontIsRefusedIsNeverSent(string refusal)
    {
        var lease = new TakingLease { Refusal = refusal };
        var adapter = new RecordingAdapter("input.visible.click", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.visible.click", Json("""{"label":"Buscar","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(refusal));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(lease.Ended, Is.Empty);
        });
    }

    // Contracases: a look (it reads its windows, «windows», and brings nothing up), an opening, and an act outside a
    // mission (no «window»: the window in front, the person's own order) never ask for the front.
    [TestCase("input.visible.controls", """{"windows":[18016]}""")]
    [TestCase("app.open", """{"appId":"spotify"}""")]
    [TestCase("input.key.press", """{"key":"enter"}""")]
    [TestCase("input.visible.click", """{"label":"Buscar","window":null}""")]
    public async Task ALookAnOpeningOrAnActOfNoMissionTakesNothing(string operation, string arguments)
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter(operation, lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease);

        _ = await provider.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(adapter.Calls, Is.EqualTo(1));
        });
    }

    private sealed class TakingLease : IForegroundLease
    {
        internal List<nint> Taken { get; } = [];

        internal string? Refusal { get; init; }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
            throw new AssertionException("the provider acquires no burst");

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("the provider runs no helper");

        internal List<string> Ended { get; } = [];

        public ValueTask<string?> TakeForMissionAsync(nint window, CancellationToken cancellationToken)
        {
            Taken.Add(window);
            return ValueTask.FromResult(Refusal);
        }

        public void MissionActEnded(string operation) => Ended.Add(operation);
    }

    private sealed class RecordingAdapter(string operation, TakingLease lease) : IExternalOperationAdapter
    {
        internal int Calls { get; private set; }

        internal bool FrontTakenWhenSent { get; private set; }

        public bool CanHandle(string name) => name == operation;

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string name, JsonElement arguments, CancellationToken cancellationToken)
        {
            Calls++;
            FrontTakenWhenSent = lease.Taken.Count > 0;
            return ValueTask.FromResult(new ExternalCapabilityReceipt(name, true, true, Json("""{"ok":true}"""), null));
        }
    }
}
