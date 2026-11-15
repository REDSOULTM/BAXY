using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// RUT2: display.status and display.monitor.set against a fake display topology: no test turns a real screen off. A
/// monitor is chosen by its position among the ones on or by being the primary one; the only monitor on is never turned
/// off; an unclear choice changes nothing; the topology is read back, and turning one back on says whether it came back
/// as it was.
/// </summary>
[TestFixture]
public sealed class MonitorAdapterTests
{
    private static MonitorState Left => new("m-left", "Corvia 24", true, false, -1920, 0, 1920, 1080, 60);

    private static MonitorState Main => new("m-main", "Lumo 27", true, true, 0, 0, 2560, 1440, 144);

    // Connected and off the desktop (a TV on HDMI with Windows set to «PC screen only»).
    private static MonitorState Tv => new("m-tv", "Vexa TV", false, false, 0, 0, 0, 0, 0);

    private static Task<ExternalCapabilityReceipt> Invoke(WindowsMonitorAdapter adapter, string operation, object arguments) =>
        adapter.InvokeAsync(operation, JsonSerializer.SerializeToElement(arguments), CancellationToken.None).AsTask();

    [Test]
    public async Task TheStatusSaysWhereEachMonitorIsAndWhichIsTheMainOne()
    {
        var display = new FakeTopology(Left, Main, new MonitorState("m-off", "Strato 22", false, false, 0, 0, 0, 0, 0));

        ExternalCapabilityReceipt receipt = await Invoke(new WindowsMonitorAdapter(display), "display.status", new { });

        JsonElement monitors = receipt.Result!.Value.GetProperty("monitors");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("monitorCount").GetInt32(), Is.EqualTo(2));
            Assert.That(monitors[0].GetProperty("position").GetString(), Is.EqualTo("left"));
            Assert.That(monitors[1].GetProperty("position").GetString(), Is.EqualTo("right"));
            Assert.That(monitors[1].GetProperty("primary").GetBoolean(), Is.True);
            Assert.That(monitors[2].GetProperty("active").GetBoolean(), Is.False);
        });
    }

    [TestCase("left")]
    [TestCase("secondary")]
    public async Task TheMonitorNamedByPlaceIsTurnedOffAndReadBack(string which)
    {
        var display = new FakeTopology(Left, Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = which });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(display.Calls, Is.EqualTo(new[] { ("m-left", false) }));
            Assert.That(receipt.Result!.Value.GetProperty("monitor").GetString(), Is.EqualTo("Corvia 24"));
            Assert.That(receipt.Result!.Value.GetProperty("position").GetString(), Is.EqualTo("left"));
            Assert.That(receipt.Result!.Value.TryGetProperty("baxyWindowThere", out _), Is.False);
        });
    }

    // PAN2: «apaga la pantalla» with one monitor went to system.power lock (30 of 40): the only monitor on is never taken
    // off the desktop, and the screen goes dark instead, as Windows darkens it when idle; nothing locks.
    [TestCase("primary")]
    [TestCase(null)]
    public async Task TheOnlyMonitorOnGoesDarkAndIsNeverTakenOff(string? which)
    {
        var display = new FakeTopology(Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = which });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(display.Calls, Is.Empty);
            Assert.That(display.Darkened, Is.EqualTo(1));
            Assert.That(receipt.Result!.Value.GetProperty("screenOff").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("active").GetBoolean(), Is.False);
            // INT36B (BAN2 b2p-06, b2p-13): who asked it, and that it was now, not an idle timer.
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.StartWith("BAXY asked Windows"));
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Not.Contain("idle"));
        });
    }

    // PAN4 (puerta INT34, c129-V4: «…sigue ahí abajo con el iconito, apágalo completo» about a tray app → monitor below
    // 9 of 10, the screen went dark): with one monitor on, a place or secondary names no monitor; nothing goes dark.
    [TestCase("below")]
    [TestCase("left")]
    [TestCase("secondary")]
    public async Task WithOneMonitorAPlaceThatNamesNoneChangesNothing(string which)
    {
        var display = new FakeTopology(Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = which });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.NotFound));
            Assert.That(display.Darkened, Is.Zero);
            Assert.That(display.Calls, Is.Empty);
            Assert.That(receipt.Result!.Value.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("monitors").GetArrayLength(), Is.EqualTo(1));
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("the only monitor on"));
            // INT36B (BAN2 b2p-13): which one it is, by name, and that it stays on.
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("is still on"));
        });
    }

    // PAN2 (banco, «Apaga la pantalla.» + «No.»: after the screen went dark the model read display.status, saw the monitor
    // active and said «sigue encendida, la herramienta no pudo apagarla» 7 of 10): what darkens lists no monitor as
    // active, and the status says BAXY turned the screen off.
    [Test]
    public async Task AfterTheScreenWentDarkNothingReadsItAsStillOn()
    {
        var display = new FakeTopology(Main);
        var adapter = new WindowsMonitorAdapter(display);

        ExternalCapabilityReceipt dark = await Invoke(adapter, "display.monitor.set", new { active = false });
        ExternalCapabilityReceipt status = await Invoke(adapter, "display.status", new { });

        Assert.Multiple(() =>
        {
            Assert.That(dark.Result!.Value.TryGetProperty("monitors", out _), Is.False);
            Assert.That(status.Result!.Value.GetProperty("screenTurnedOffByBaxy").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task TurningOnAfterTheScreenWentDarkWakesIt()
    {
        var display = new FakeTopology(Main);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });

        ExternalCapabilityReceipt receipt = await Invoke(adapter, "display.monitor.set", new { active = true });

        Assert.Multiple(() =>
        {
            Assert.That(display.Woken, Is.EqualTo(1));
            Assert.That(receipt.Result!.Value.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(display.Calls, Is.Empty);
        });
    }

    // REV19 P-2: a TV connected but off the desktop (or a monitor BAXY took off) and the only one on darkened: «vuelve a
    // encender la pantalla» put the TV on the desktop (its windows moved), said it turned it on, and the dark one stayed
    // dark. What BAXY darkened wakes first; the topology is not touched.
    [TestCase(null)]
    [TestCase("primary")]
    public async Task TurningOnAfterTheScreenWentDarkWakesItAndPutsNoOtherMonitorOn(string? which)
    {
        var display = new FakeTopology(Main, Tv);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });

        ExternalCapabilityReceipt receipt = await Invoke(
            adapter, "display.monitor.set", new { active = true, monitor = which });

        Assert.Multiple(() =>
        {
            Assert.That(display.Calls, Is.Empty);
            Assert.That(display.Woken, Is.EqualTo(1));
            Assert.That(receipt.Result!.Value.GetProperty("screenOff").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.StartWith("BAXY asked Windows"));
        });
    }

    // Control of P-2: the monitor off named while the screen is dark is still the one put back on the desktop.
    [Test]
    public async Task TheMonitorOffNamedWhileTheScreenIsDarkIsStillPutOn()
    {
        var display = new FakeTopology(Main, Tv);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });

        ExternalCapabilityReceipt receipt = await Invoke(
            adapter, "display.monitor.set", new { active = true, monitor = "secondary" });

        Assert.Multiple(() =>
        {
            Assert.That(display.Calls, Is.EqualTo(new[] { ("m-tv", true) }));
            Assert.That(display.Woken, Is.Zero);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("monitor").GetString(), Is.EqualTo("Vexa TV"));
            // Blind review of PAN5 (3): whether putting a monitor on lights the dark one is not read; it is still said.
            Assert.That(receipt.Result!.Value.GetProperty("darkenedMonitor").GetString(), Is.EqualTo("Lumo 27"));
        });
    }

    // Blind review of PAN5 (5): a wake Windows did not take keeps the screen as BAXY darkened it.
    [Test]
    public async Task AWakeNotPostedKeepsTheDarkScreen()
    {
        var display = new FakeTopology(Main) { WakeIgnores = true };
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });

        ExternalCapabilityReceipt receipt = await Invoke(adapter, "display.monitor.set", new { active = true });
        ExternalCapabilityReceipt status = await Invoke(adapter, "display.status", new { });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.NotVerified));
            Assert.That(status.Result!.Value.GetProperty("screenTurnedOffByBaxy").GetBoolean(), Is.True);
        });
    }

    // REV19 P-4: «apaga la tele» with the TV connected off the desktop darkens the monitor, and the receipt did not say
    // which one went dark (nothing kept the model from «apagué la tele»); waking says the same one.
    [Test]
    public async Task WhatGoesDarkAndWakesIsSaidByName()
    {
        var display = new FakeTopology(Main, Tv);
        var adapter = new WindowsMonitorAdapter(display);

        ExternalCapabilityReceipt dark = await Invoke(adapter, "display.monitor.set", new { active = false });
        ExternalCapabilityReceipt woke = await Invoke(adapter, "display.monitor.set", new { active = true });

        Assert.Multiple(() =>
        {
            Assert.That(dark.Result!.Value.TryGetProperty("monitor", out JsonElement darkened), Is.True);
            Assert.That(darkened.ValueKind == JsonValueKind.String ? darkened.GetString() : null, Is.EqualTo("Lumo 27"));
            Assert.That(woke.Result!.Value.TryGetProperty("monitor", out JsonElement woken), Is.True);
            Assert.That(woken.ValueKind == JsonValueKind.String ? woken.GetString() : null, Is.EqualTo("Lumo 27"));
        });
    }

    // REV19 P-3: darkening is a request posted to Windows and never read back (effectReadBack false; the App says
    // delivered_only), and the receipt said «done: the screen is off now» (in a remote session, or with the message
    // ignored, the screen would not be off).
    [Test]
    public async Task WhatGoesDarkIsSaidAsAskedOfWindows()
    {
        var display = new FakeTopology(Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false });

        string next = receipt.Result!.Value.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("effectReadBack").GetBoolean(), Is.False);
            Assert.That(next, Does.Not.Contain("done"));
            Assert.That(next, Does.Not.Contain("is off now"));
            Assert.That(next, Does.Contain("BAXY cannot see whether it did"));
            // REV20 P5-2: with Modern Standby, Screen Off leads to sleep in S0 and waking asks for the password; BAXY
            // never reads whether the session locked, so the receipt does not say it did not.
            Assert.That(next, Does.Not.Contain("locked"));
        });
    }

    // PAN7 (VIVO21: on the notebook, a Modern Standby PC, SC_MONITORPOWER put the whole PC on standby and BAXY stopped
    // hearing): there the display is never turned off; a black window and the brightness at its minimum darken it, and
    // the receipt says so: the PC stays on and BAXY keeps listening. Unknown (Windows does not say) is taken as standby.
    [TestCase(true)]
    [TestCase(null)]
    public async Task OnAModernStandbyPcTheScreenGoesBlackAndThePcStaysOn(bool? standby)
    {
        var display = new FakeTopology(Main) { Standby = standby };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false });

        JsonElement result = receipt.Result!.Value;
        string next = result.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(display.Darkened, Is.Zero);
            Assert.That(display.BlackedOut, Is.EqualTo(1));
            Assert.That(display.Calls, Is.Empty);
            Assert.That(result.GetProperty("screenBlack").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("displayPoweredOff").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("pcStaysOn").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("brightnessLowered").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("authority").GetString(), Is.Not.EqualTo("windows_sc_monitorpower_request"));
            Assert.That(next, Does.Contain("keeps listening"));
            Assert.That(next, Does.Contain("standby"));
        });
    }

    // PAN7: with no brightness Windows lets BAXY change (a desktop monitor), the receipt does not say it was lowered.
    [Test]
    public async Task ABlackScreenWithNoBrightnessToLowerSaysOnlyTheBlack()
    {
        var display = new FakeTopology(Main) { Standby = true, Black = new(BrightnessBefore: null) };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("brightnessLowered").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Not.Contain("brightness to its minimum"));
        });
    }

    // PAN7 (b): where no black window could be shown, nothing is done (posting SC_MONITORPOWER would put the PC on
    // standby): the result says why and what BAXY can do instead.
    [Test]
    public async Task WhereTheScreenCannotGoBlackNothingIsTurnedOff()
    {
        var display = new FakeTopology(Main) { Standby = true, Black = null };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("screen_off_would_sleep"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(display.Darkened, Is.Zero);
            Assert.That(receipt.Result!.Value.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("stop hearing"));
        });
    }

    // PAN7: «enciende la pantalla» takes the black window off and gives the brightness back; it posts nothing to Windows.
    [Test]
    public async Task TurningTheScreenOnTakesTheBlackOffAndGivesTheBrightnessBack()
    {
        var display = new FakeTopology(Main) { Standby = true };
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });
        ExternalCapabilityReceipt status = await Invoke(adapter, "display.status", new { });

        ExternalCapabilityReceipt on = await Invoke(adapter, "display.monitor.set", new { active = true });

        Assert.Multiple(() =>
        {
            Assert.That(status.Result!.Value.GetProperty("screenTurnedOffByBaxy").GetBoolean(), Is.True);
            Assert.That(status.Result!.Value.GetProperty("note").GetString(), Does.Contain("black"));
            Assert.That(on.ErrorCode, Is.Null);
            Assert.That(display.Unblacked, Is.EqualTo(1));
            Assert.That(display.Woken, Is.Zero);
            Assert.That(on.Result!.Value.GetProperty("screenBlack").GetBoolean(), Is.False);
            Assert.That(on.Result!.Value.GetProperty("next").GetString(), Does.Contain("brightness back"));
        });
    }

    // PAN7: a key or a mouse move takes the black window off by itself; the status no longer says it is dark.
    [Test]
    public async Task InputAfterTheScreenWentBlackEndsIt()
    {
        var display = new FakeTopology(Main) { Standby = true };
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });
        display.LastInputTick += 5000;

        ExternalCapabilityReceipt status = await Invoke(adapter, "display.status", new { });

        Assert.That(status.Result!.Value.TryGetProperty("screenTurnedOffByBaxy", out _), Is.False);
    }

    // Revisión ciega PAN7 (5): with the black window no longer up, turning the screen on says nothing changed.
    [Test]
    public async Task TurningTheScreenOnWithTheBlackAlreadyGoneSaysNothingChanged()
    {
        var display = new FakeTopology(Main) { Standby = true, Ended = false };
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });

        ExternalCapabilityReceipt on = await Invoke(adapter, "display.monitor.set", new { active = true });

        Assert.Multiple(() =>
        {
            Assert.That(on.Result!.Value.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(on.Result!.Value.GetProperty("next").GetString(), Does.Not.Contain("brightness back"));
        });
    }

    // Revisión ciega PAN7 (4): a key pressed while the window was coming up (after the input it started from) took it off.
    [Test]
    public async Task InputSinceTheWindowCameUpIsReadFromWhereItStarted()
    {
        var display = new FakeTopology(Main) { Standby = true, Black = new(70, InputAtStart: 500) };
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });

        ExternalCapabilityReceipt status = await Invoke(adapter, "display.status", new { });

        Assert.That(status.Result!.Value.TryGetProperty("screenTurnedOffByBaxy", out _), Is.False);
    }

    // PAN7 control: on a PC with no Modern Standby (S3), the display is turned off as before PAN7 and nothing goes black.
    [Test]
    public async Task WithoutModernStandbyTheDisplayIsTurnedOffAsBefore()
    {
        var display = new FakeTopology(Main) { Standby = false };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false });

        Assert.Multiple(() =>
        {
            Assert.That(display.Darkened, Is.EqualTo(1));
            Assert.That(display.BlackedOut, Is.Zero);
            Assert.That(receipt.Result!.Value.GetProperty("authority").GetString(),
                Is.EqualTo("windows_sc_monitorpower_request"));
        });
    }

    // PAN7 control: taking one monitor of several off the desktop (SetDisplayConfig) is no display power-off: it works on
    // a Modern Standby PC as before.
    [Test]
    public async Task OnAModernStandbyPcOneMonitorOfSeveralStillGoesOff()
    {
        var display = new FakeTopology(Left, Main) { Standby = true };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(display.Calls, Is.EqualTo(new[] { ("m-left", false) }));
            Assert.That(display.BlackedOut, Is.Zero);
        });
    }

    // REV19 P-5: the screen darkened at 10:00, the person moved the mouse (it lit), and at 18:00 display.status still said
    // screenTurnedOffByBaxy. Input after darkening (GetLastInputInfo) means it is no longer BAXY's dark screen.
    [Test]
    public async Task InputAfterTheScreenWentDarkEndsWhatBaxyDarkened()
    {
        var display = new FakeTopology(Main);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });
        ExternalCapabilityReceipt still = await Invoke(adapter, "display.status", new { });
        display.LastInputTick += 5000;

        ExternalCapabilityReceipt status = await Invoke(adapter, "display.status", new { });
        ExternalCapabilityReceipt on = await Invoke(adapter, "display.monitor.set", new { active = true });

        Assert.Multiple(() =>
        {
            Assert.That(still.Result!.Value.GetProperty("screenTurnedOffByBaxy").GetBoolean(), Is.True);
            Assert.That(status.Result!.Value.TryGetProperty("screenTurnedOffByBaxy", out _), Is.False);
            Assert.That(display.Woken, Is.Zero);
            Assert.That(on.StateAlreadyReached, Is.True);
        });
    }

    // Control of P-5: when Windows gives no last input, nothing is known to have lit the screen.
    [Test]
    public async Task WithNoLastInputTheDarkScreenIsStillSaid()
    {
        var display = new FakeTopology(Main);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });
        display.InputUnknown = true;

        ExternalCapabilityReceipt status = await Invoke(adapter, "display.status", new { });

        Assert.Multiple(() =>
        {
            Assert.That(status.Result!.Value.GetProperty("screenTurnedOffByBaxy").GetBoolean(), Is.True);
            Assert.That(status.Result!.Value.GetProperty("darkenedMonitor").GetString(), Is.EqualTo("Lumo 27"));
        });
    }

    // Blind review of PAN5 (1): with no last input from Windows when it went dark, nothing says no key came since.
    [Test]
    public async Task WithNoLastInputWhenItWentDarkTheStatusSaysItCannotTell()
    {
        var display = new FakeTopology(Main) { InputUnknown = true };
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false });

        ExternalCapabilityReceipt status = await Invoke(adapter, "display.status", new { });

        string note = status.Result!.Value.GetProperty("note").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(note, Does.Contain("cannot tell"));
            Assert.That(note, Does.Not.Contain("no key or mouse move came"));
        });
    }

    [Test]
    public async Task AScreenThatCouldNotGoDarkSaysNothingChanged()
    {
        var display = new FakeTopology(Main) { Ignores = true };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.OnlyMonitor));
            Assert.That(display.Calls, Is.Empty);
        });
    }

    [Test]
    public async Task AnUnclearChoiceChangesNothingAndListsTheMonitors()
    {
        var right = new MonitorState("m-right", "Corvia 24", true, false, 2560, 0, 1920, 1080, 60);
        var display = new FakeTopology(Left, Main, right);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "secondary" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.Ambiguous));
            Assert.That(display.Calls, Is.Empty);
            Assert.That(receipt.Result!.Value.GetProperty("monitors").GetArrayLength(), Is.EqualTo(3));
            Assert.That(receipt.Result!.Value.GetProperty("monitors")[1].GetProperty("position").GetString(), Is.EqualTo("middle"));
        });
    }

    [Test]
    public async Task BaxysWindowOnTheMonitorTurnedOffIsSaid()
    {
        var display = new FakeTopology(Left, Main) { Windows = [(-1500, 100, 800, 600)] };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "left" });

        Assert.That(receipt.Result!.Value.GetProperty("baxyWindowThere").GetBoolean(), Is.True);
    }

    [Test]
    public async Task TurnedBackOnItSaysWhetherItCameBackAsItWas()
    {
        var display = new FakeTopology(Left, Main);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false, monitor = "left" });

        ExternalCapabilityReceipt receipt = await Invoke(adapter, "display.monitor.set", new { active = true });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(display.Calls, Is.EqualTo(new[] { ("m-left", false), ("m-left", true) }));
            Assert.That(receipt.Result!.Value.GetProperty("asBefore").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("position").GetString(), Is.EqualTo("left"));
        });
    }

    [Test]
    public async Task ATopologyThatDidNotChangeIsNoSuccess()
    {
        var display = new FakeTopology(Left, Main) { Ignores = true };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.NotVerified));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task AllOnAlreadyIsTheStateReached()
    {
        var display = new FakeTopology(Left, Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = true, monitor = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(display.Calls, Is.Empty);
        });
    }

    // Revisión ciega RUT2 (1): the one monitor off is turned back on only when what was asked does not contradict
    // where it was when BAXY turned it off.
    [Test]
    public async Task TurningOnTheOtherSideThanTheOneOffChangesNothing()
    {
        var display = new FakeTopology(Left, Main);
        var adapter = new WindowsMonitorAdapter(display);
        _ = await Invoke(adapter, "display.monitor.set", new { active = false, monitor = "left" });

        ExternalCapabilityReceipt receipt = await Invoke(adapter, "display.monitor.set", new { active = true, monitor = "right" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.NotFound));
            Assert.That(display.Calls, Is.EqualTo(new[] { ("m-left", false) }));
        });
    }

    // Revisión ciega RUT2 (6): with no monitor named and more than one it could be, the choice is unclear.
    [Test]
    public async Task TurningOffWithNoMonitorNamedIsAmbiguous()
    {
        var display = new FakeTopology(Left, Main);

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.Ambiguous));
            Assert.That(display.Calls, Is.Empty);
        });
    }

    // Revisión ciega RUT2 (3): a monitor the read-back does not find is not «turned off».
    [Test]
    public async Task AMonitorMissingFromTheReadBackIsNoSuccess()
    {
        var display = new FakeTopology(Left, Main) { Vanishes = true };

        ExternalCapabilityReceipt receipt = await Invoke(
            new WindowsMonitorAdapter(display), "display.monitor.set", new { active = false, monitor = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsMonitorAdapter.NotVerified));
        });
    }

    [Test]
    public void StackedMonitorsAreAboveAndBelow()
    {
        var top = new MonitorState("a", "A", true, false, 0, -1080, 1920, 1080, 60);
        var bottom = new MonitorState("b", "B", true, true, 0, 0, 1920, 1080, 60);

        Assert.Multiple(() =>
        {
            Assert.That(WindowsMonitorAdapter.Position(top, [top, bottom]), Is.EqualTo("above"));
            Assert.That(WindowsMonitorAdapter.Position(bottom, [top, bottom]), Is.EqualTo("below"));
            Assert.That(WindowsMonitorAdapter.Position(bottom, [bottom]), Is.EqualTo("only"));
        });
    }

    [Test]
    public void ARowWithOneUnderItIsLeftRightAndBelow()
    {
        var left = new MonitorState("l", "L", true, false, -1920, 0, 1920, 1080, 60);
        var main = new MonitorState("m", "M", true, true, 0, 0, 1920, 1080, 60);
        var under = new MonitorState("u", "U", true, false, -1000, 1080, 1920, 1080, 60);
        MonitorState[] on = [left, main, under];

        Assert.Multiple(() =>
        {
            Assert.That(WindowsMonitorAdapter.Position(left, on), Is.EqualTo("left"));
            Assert.That(WindowsMonitorAdapter.Position(main, on), Is.EqualTo("right"));
            Assert.That(WindowsMonitorAdapter.Position(under, on), Is.EqualTo("below"));
        });
    }

    private sealed class FakeTopology(params MonitorState[] monitors) : IMonitorPlatform
    {
        private readonly List<MonitorState> _monitors = [.. monitors];

        public List<(string, bool)> Calls { get; } = [];

        public bool Ignores { get; init; }

        public bool Vanishes { get; init; }

        public IReadOnlyList<(int X, int Y, int Width, int Height)> Windows { get; init; } = [];

        public IReadOnlyList<MonitorState> Monitors() => [.. _monitors];

        public int SetActive(string key, bool active)
        {
            Calls.Add((key, active));
            if (Vanishes)
            {
                _monitors.RemoveAll(monitor => monitor.Key == key);
                return 0;
            }

            if (!Ignores)
            {
                int index = _monitors.FindIndex(monitor => monitor.Key == key);
                MonitorState first = monitors.First(monitor => monitor.Key == key);
                _monitors[index] = active
                    ? first.Active ? first : first with { Active = true, X = 2560, Width = 1920, Height = 1080, RefreshHz = 60 }
                    : _monitors[index] with { Active = false, Primary = false, X = 0, Y = 0, Width = 0, Height = 0 };
            }

            return 0;
        }

        public IReadOnlyList<(int X, int Y, int Width, int Height)> ProductWindows() => Windows;

        public int Darkened { get; private set; }

        public int Woken { get; private set; }

        public bool Darken()
        {
            Darkened++;
            return !Ignores;
        }

        public bool WakeIgnores { get; init; }

        public bool Wake()
        {
            Woken++;
            return !Ignores && !WakeIgnores;
        }

        public uint LastInputTick { get; set; } = 1000;

        public bool InputUnknown { get; set; }

        public uint? LastInput() => InputUnknown ? null : LastInputTick;

        // PAN7: a desktop PC by default (S3, no Modern Standby), as every test before PAN7 assumed.
        public bool? Standby { get; init; } = false;

        public ScreenBlackout? Black { get; init; } = new(BrightnessBefore: 70);

        public int BlackedOut { get; private set; }

        public int Unblacked { get; private set; }

        public bool? ModernStandby() => Standby;

        public ScreenBlackout? Blackout()
        {
            BlackedOut++;
            return Black;
        }

        public bool Ended { get; init; } = true;

        public bool EndBlackout()
        {
            Unblacked++;
            return Ended;
        }
    }
}
