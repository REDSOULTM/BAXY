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

    // FT/proveedores goal (live W1): the refusal names the program whose window it was, so the reply does not blame
    // another application.
    [Test]
    public async Task AProtectedWindowRefusalNamesItsProgram()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "WindowsTerminal",
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(receipt.Result?.GetProperty("refusedProcess").GetString(), Is.EqualTo("WindowsTerminal"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(adapter.Calls, Is.Zero);
        });
    }

    // BAXY Renew cu (C18): with the aid on, the refusal says nothing was sent and how another application's window is
    // reached; with the aids off it reads as before.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AProtectedWindowRefusalSaysHowAnotherWindowIsReached(string aids, bool next)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("clipboard.paste", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "Code",
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync("clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(receipt.Result?.TryGetProperty("next", out _), Is.EqualTo(next));
            if (next)
            {
                Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("belongs to Code").And.Contain("app_open"));
            }
        });
    }

    // Renew al máximo (w5): an act stopped by the person's input says why and that the window was not looked at, beside
    // the code, which stays; whether anything was sent is as the receipt says. With the aids off it reads as before.
    [TestCase("all", false, "nothing of the act was sent")]
    [TestCase("all", true, "whether it landed was not looked at")]
    [TestCase("none", true, null)]
    public void AnActStoppedByThePersonsInputSaysWhyItStopped(string aids, bool mayHaveSent, string? next)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        ExternalCapabilityReceipt stopped = mayHaveSent
            ? ExternalJson.FailureAfterEffect("input.visible.click", "input_user_interrupted", effectObserved: true)
            : ExternalJson.FailureBeforeEffect("input.visible.click", "input_user_interrupted");

        ExternalCapabilityReceipt told = WindowsExternalCapabilityProvider.Interrupted(stopped);

        Assert.Multiple(() =>
        {
            Assert.That(told.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(told.Verified, Is.False);
            if (next is null)
            {
                Assert.That(told.Result, Is.Null);
                return;
            }

            Assert.That(told.Result?.GetProperty("reason").GetString(), Does.Contain("the person's mouse or keys"));
            Assert.That(told.Result?.GetProperty("next").GetString(), Does.Contain(next).And.Contain("input_visible_controls"));
            Assert.That(told.Result?.GetProperty("next").GetString(), Does.Not.Contain("closed"));
        });
        Assert.That(WindowsExternalCapabilityProvider.Interrupted(
            ExternalJson.FailureBeforeEffect("input.visible.click", "input_window_changed")).Result, Is.Null);
    }

    // CU4 (auditoría final 2): an act that would reach a developer's or BAXY's own window no look named is never sent,
    // and no front is taken for it.
    [Test]
    public async Task AnActOnAProtectedWindowIsNeverSent()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(lease.Taken, Is.Empty);
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
