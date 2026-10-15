using System.Buffers.Binary;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The names of buttons that are only an icon (v3 point 3, CONTRATO_VISTA_ACCION.md §8.2): candidates without a name
/// (or icon-shaped regions on a window without a tree) are hovered inside a burst of the foreground lease, the tooltip
/// is read by UI Automation or, failing that, by OCR of what changed, the cursor and the front are given back and the
/// label is kept by window signature. Everything here runs on fakes: no window is read, moved or pressed.
/// </summary>
[TestFixture]
public sealed class ComputerUseTooltipTests
{
    private string _directory = string.Empty;

    [SetUp]
    public void CreateDirectory()
    {
        _directory = Path.Combine(Path.GetTempPath(), "baxy-tooltip-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_directory);
    }

    [TearDown]
    public void DeleteDirectory()
    {
        try
        {
            Directory.Delete(_directory, recursive: true);
        }
        catch (IOException)
        {
        }
    }

    // ---------------------------------------------------------------- pure readings

    [Test]
    public void AnIconShapeIsACandidateButWrittenLinesTinyDotsAndLongRulesAreNot()
    {
        var image = new Canvas(320, 200);
        image.Ring(40, 12, 20, 20);          // an icon in the top bar
        image.Ring(140, 14, 18, 18);         // the same shape inside a written line: OCR already reads it
        image.Fill(250, 100, 5, 5);          // a dot: too small
        image.Fill(20, 150, 200, 2);         // a rule: not icon-shaped
        image.Ring(200, 90, 24, 24);         // a second icon, farther from the edges
        image.Ring(190, 80, 44, 44);         // its button's outline around it: the same control
        TooltipImage decoded = TooltipImage.FromBmp(image.Bmp())!;

        IReadOnlyList<PixelBox> found = decoded.IconCandidates([new PixelBox(120, 10, 90, 26)], 6);

        Assert.That(found.Select(box => (box.CenterX / 4, box.CenterY / 4)), Is.EqualTo(new[]
        {
            (50 / 4, 22 / 4),     // nearest an edge first
            (212 / 4, 102 / 4),
        }), "the outline and its glyph are hovered once");
    }

    [Test]
    public void WhatATooltipAddedIsFoundAndTheHoveredControlsOwnHighlightIsNot()
    {
        var before = new Canvas(400, 300);
        before.Ring(100, 100, 20, 20);
        var after = new Canvas(400, 300);
        after.Ring(100, 100, 20, 20);
        after.Fill(98, 98, 24, 24, 90);      // the hover highlight on the control itself
        after.Fill(110, 130, 90, 22);        // the tooltip below the cursor
        TooltipImage first = TooltipImage.FromBmp(before.Bmp())!;
        TooltipImage second = TooltipImage.FromBmp(after.Bmp())!;
        var hovered = new PixelBox(100, 100, 20, 20);
        var strip = new PixelBox(0, 0, 400, 300);

        PixelBox? changed = TooltipImage.ChangedBox(first, second, strip, hovered);
        var highlightOnly = new Canvas(400, 300);
        highlightOnly.Ring(100, 100, 20, 20);
        highlightOnly.Fill(98, 98, 24, 24, 90);
        var pageChanged = new Canvas(400, 300);
        pageChanged.Fill(0, 0, 400, 300);

        Assert.Multiple(() =>
        {
            Assert.That(changed, Is.EqualTo(new PixelBox(110, 130, 90, 22)));
            Assert.That(TooltipImage.ChangedBox(first, TooltipImage.FromBmp(highlightOnly.Bmp())!, strip, hovered), Is.Null,
                "a control that only lights up shows no tooltip");
            Assert.That(TooltipImage.ChangedBox(first, TooltipImage.FromBmp(pageChanged.Bmp())!, strip, hovered), Is.Null,
                "a whole page that changed is not a tooltip");
            Assert.That(TooltipImage.ChangedBox(first, first, strip, hovered), Is.Null);
        });
    }

    [Test]
    public void OnlyTheLinesTheTooltipAddedAreItsText()
    {
        Assert.Multiple(() =>
        {
            Assert.That(TooltipImage.NewText(["Biblioteca", "Configuración de usuario"], ["Biblioteca"]),
                Is.EqualTo("Configuración de usuario"));
            Assert.That(TooltipImage.NewText(["Biblioteca"], ["BIBLIOTECA"]), Is.Empty, "a line already there is not new");
            Assert.That(TooltipImage.NewText(["x"], []), Is.Empty, "a single stray letter names nothing");
            Assert.That(TooltipImage.NewText(
                [("Modo_DEMlO v 12.50", new PixelBox(30, 2, 120, 16)), ("Administrar cuenta", new PixelBox(0, 40, 130, 16))],
                ["C Modo_demO v 12,50"], new PixelBox(0, 0, 24, 24)),
                Is.EqualTo("Administrar cuenta"), "the hovered row's own text, read again with other errors, is not the tooltip");
            Assert.That(TooltipImage.NewText(
                [("Administrar cuenta", new PixelBox(0, 40, 130, 16))], [], new PixelBox(0, 0, 24, 24)),
                Is.EqualTo("Administrar cuenta"), "counter-case: a line below the control is");
        });
    }

    [Test]
    public void ACropKeepsItsPixelsInTheBmpTheOcrReads()
    {
        var image = new Canvas(30, 20);
        image.Fill(12, 5, 3, 4);
        TooltipImage decoded = TooltipImage.FromBmp(image.Bmp())!;

        TooltipImage crop = TooltipImage.FromBmp(decoded.CropBmp(new PixelBox(10, 4, 8, 8)))!;

        Assert.Multiple(() =>
        {
            Assert.That((crop.Width, crop.Height), Is.EqualTo((8, 8)));
            Assert.That(crop.Bgra[((1 * 8) + 2) * 4], Is.EqualTo(0), "the dark pixel at (12,5) is at (2,1) in the crop");
            Assert.That(crop.Bgra[0], Is.EqualTo(255));
            Assert.That(TooltipImage.FromBmp([1, 2, 3]), Is.Null);
        });
    }

    [Test]
    public void ALabelIsKeptByWindowAndPlaceUntilItExpiresOrIsForgotten()
    {
        DateTime now = new(2026, 10, 7, 12, 0, 0, DateTimeKind.Utc);
        string path = Path.Combine(_directory, "computer-use", "tooltip-labels.v1.json");
        var cache = new TooltipLabelCache(path, () => now);
        string signature = TooltipLabelCache.Signature("App", "MainWindow", 1200, 800);
        string place = TooltipLabelCache.Place(new PixelBox(1101, 13, 30, 31));
        cache.Put(signature, place, "Ajustes", "tooltipUia");

        var reloaded = new TooltipLabelCache(path, () => now.AddDays(29));
        var expired = new TooltipLabelCache(path, () => now.AddDays(31));

        Assert.Multiple(() =>
        {
            Assert.That(place, Is.EqualTo("1104.16.32.32"), "rounded to 8 px");
            Assert.That(reloaded.For(signature).Select(entry => entry.Label), Is.EqualTo(new[] { "Ajustes" }));
            Assert.That(reloaded.For(TooltipLabelCache.Signature("App", "MainWindow", 600, 800)), Is.Empty,
                "another size of the window is another signature");
            Assert.That(expired.For(signature), Is.Empty);
        });
        reloaded.Forget(signature, place);
        Assert.That(new TooltipLabelCache(path, () => now).For(signature), Is.Empty);
    }

    // ---------------------------------------------------------------- the stage

    [Test]
    public async Task TheIconWhoseTooltipNamesTheLabelIsPressedAndEveryCandidateIsGivenBack()
    {
        var desktop = new FakeDesktop();
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":40,"controls":[{"kind":"Button","id":"1","rect":{"x":1100,"y":510,"w":24,"h":24}},{"kind":"Button","id":"2","rect":{"x":1140,"y":510,"w":24,"h":24}}]}""",
        };
        worker.TipAt[(1112, 522)] = "Notificaciones";
        worker.TipAt[(1152, 522)] = "Configuración de usuario";
        var press = new RecordingPress { Desktop = desktop };
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));
        var locator = new WindowsVisibleTooltipLocator(worker, desktop, cache);

        ExternalCapabilityReceipt? receipt = await locator.TryClickAsync(
            "input.visible.click", "configuración de usuario", press, CancellationToken.None);

        Assert.That(receipt, Is.Not.Null);
        JsonElement result = receipt!.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(result.GetProperty("name").GetString(), Is.EqualTo("Configuración de usuario"));
            Assert.That(result.GetProperty("nameSource").GetString(), Is.EqualTo("tooltipUia"));
            Assert.That(result.GetProperty("cascadeStage").GetString(), Is.EqualTo("tooltip"));
            Assert.That(press.Points, Is.EqualTo(new[] { (1152, 522) }), "the control the tooltip named, at its centre");
            Assert.That(press.ControlIds, Is.EqualTo(new[] { "2" }), "pressed by its identity: its pattern, not the mouse");
            Assert.That(desktop.Hovers, Is.EqualTo(new[] { (1112, 522), (1152, 522) }));
            Assert.That(desktop.Bursts, Is.EqualTo(2));
            Assert.That(desktop.Restored, Is.EqualTo(2), "the cursor and the front go back after every candidate");
            Assert.That(worker.Commands.Where(command => command.Contains("tooltips", StringComparison.Ordinal)),
                Has.All.Contains("\"pids\":[4242,5353]"), "the tooltips of the processes that draw the window");
            Assert.That(cache.For(desktop.Signature).Select(entry => entry.Label),
                Is.EquivalentTo(new[] { "Notificaciones", "Configuración de usuario" }));
        });
    }

    [Test]
    public async Task ALabelLearnedBeforeIsPressedWithoutHoveringAgain()
    {
        var desktop = new FakeDesktop();
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));
        Remember(cache, desktop, "Configuración", "tooltipOcr");
        var worker = new FakeWorker(desktop);
        var press = new RecordingPress { Desktop = desktop };
        var locator = new WindowsVisibleTooltipLocator(worker, desktop, cache);

        ExternalCapabilityReceipt? receipt = await locator.TryClickAsync(
            "input.visible.click", "Configuración", press, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt?.Verified, Is.True);
            Assert.That(receipt!.Result!.Value.GetProperty("learnedBefore").GetBoolean(), Is.True);
            Assert.That(worker.Commands, Is.Empty, "nothing is listed or hovered");
            Assert.That(desktop.Hovers, Is.Empty);
            Assert.That(press.Points, Is.EqualTo(new[] { (1000 + 144 + 12, 500 + 8 + 12) }), "the remembered place, relative to the window");
            Assert.That(press.ControlIds, Is.Empty, "counter-case: an identity of another session is not trusted");
        });
    }

    [Test]
    public async Task ARememberedPlaceThatShowsAnotherControlNowIsForgottenAndHoveredAgain()
    {
        var desktop = new FakeDesktop();
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));
        Remember(cache, desktop, "Configuración", "tooltipUia");
        // Another site of the same window: another icon at that place, whose tooltip says what it is.
        desktop.Image.Fill(140, 10, 24, 24, 255);
        desktop.Image.Fill(144, 14, 16, 6);
        desktop.Image.Fill(144, 26, 16, 4);
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":40,"controls":[{"kind":"Button","id":"9","rect":{"x":1140,"y":510,"w":24,"h":24}}]}""",
        };
        worker.TipAt[(1152, 522)] = "Eliminar";
        var press = new RecordingPress { Desktop = desktop };

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, cache)
            .TryClickAsync("input.visible.click", "Configuración", press, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Null, "nothing named «Configuración» is there now");
            Assert.That(press.Points, Is.Empty, "the remembered place is not pressed blind");
            Assert.That(desktop.Hovers, Is.EqualTo(new[] { (1152, 522) }), "its control is hovered again");
            Assert.That(cache.For(desktop.Signature).Select(entry => entry.Label), Is.EqualTo(new[] { "Eliminar" }));
        });
    }

    [Test]
    public async Task ARememberedPlaceWhereTheTreeNamesAnotherControlIsPressedNeitherByItsWayNorByThePointer()
    {
        var desktop = new FakeDesktop();
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));
        Remember(cache, desktop, "Configuración", "tooltipUia");
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":40,"controls":[]}""",
        };
        var press = new RecordingPress { Desktop = desktop, RefuseRemembered = true };

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, cache)
            .TryClickAsync("input.visible.click", "Configuración", press, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(press.Remembered, Is.EqualTo(new[] { (1156, 520, 24, 24) }), "asked with the size of the place");
            Assert.That(press.Pointer, Is.Empty, "the worker's refusal is not a «nothing there» the pointer may follow");
            Assert.That(desktop.Pressed, Is.False);
            Assert.That(receipt, Is.Null, "hovered again, nothing names it");
            Assert.That(cache.For(desktop.Signature), Is.Empty);
        });
    }

    [Test]
    public void ThePrintOfAPlaceTellsItsIconFromAnotherAndAFlatPlaceHasNone()
    {
        var one = new Canvas(100, 60);
        one.Ring(10, 10, 24, 24);
        var same = new Canvas(100, 60);
        same.Ring(10, 10, 24, 24);
        same.Fill(30, 30, 1, 1, 200);
        var other = new Canvas(100, 60);
        other.Fill(14, 14, 16, 6);
        other.Fill(14, 26, 16, 4);
        var box = new PixelBox(8, 8, 24, 24);
        string? print = TooltipImage.FromBmp(one.Bmp())!.Print(box);

        Assert.Multiple(() =>
        {
            Assert.That(print, Is.Not.Null);
            Assert.That(TooltipImage.SamePrint(print, TooltipImage.FromBmp(same.Bmp())!.Print(box)), Is.True,
                "a pixel of anti-aliasing is the same icon");
            Assert.That(TooltipImage.SamePrint(print, TooltipImage.FromBmp(other.Bmp())!.Print(box)), Is.False);
            Assert.That(TooltipImage.FromBmp(new Canvas(100, 60).Bmp())!.Print(box), Is.Null, "a flat place has no print");
            Assert.That(TooltipImage.SamePrint(null, print), Is.False, "an entry without a print is not trusted");
        });
    }

    [Test]
    public void TheWorkersRefusalOfARememberedPlaceIsNeitherAPressNorANothingThere()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.PointPressFrom(JsonDocument.Parse(
                """{"ok":false,"effectObserved":false,"error":"visible_point_named_other"}""").RootElement).Outcome,
                Is.EqualTo(PointPressOutcome.Refused));
            Assert.That(WindowsVisibleControlAdapter.PointPressFrom(JsonDocument.Parse(
                """{"ok":false,"effectObserved":false,"error":"visible_point_no_pattern"}""").RootElement).Outcome,
                Is.EqualTo(PointPressOutcome.NothingThere), "counter-case: nothing there still leaves it to the pointer");
        });
    }

    [TestCase(true, false, false)]
    [TestCase(true, true, true)]
    [TestCase(false, false, false)]
    [TestCase(false, true, true)]
    public async Task ATooltipThatShowsAgainOnThePressedIconIsNoEffect(bool remembered, bool pressChanges, bool verified)
    {
        var desktop = new FakeDesktop { ChangesAfterPress = pressChanges, TooltipAfterPress = true };
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));
        var worker = new FakeWorker(desktop);
        if (remembered)
        {
            Remember(cache, desktop, "Configuración", "tooltipOcr", new PixelBox(156, 40, 70, 18));
        }
        else
        {
            desktop.Image.Ring(140, 10, 24, 24);
            worker.Unnamed = """{"ok":true,"error":"","named":40,"controls":[{"kind":"Button","id":"2","rect":{"x":1144,"y":508,"w":24,"h":24}}]}""";
            worker.TipAt[(1156, 520)] = "Configuración";
        }

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, cache)
            .TryClickAsync("input.visible.click", "Configuración", new RecordingPress { Desktop = desktop }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Pressed, Is.True);
            Assert.That(receipt?.Verified, Is.EqualTo(verified),
                verified ? "counter-case: what the press opened away from the icon proves it" : "the tooltip and the highlight prove nothing");
            if (remembered)
                Assert.That(cache.For(desktop.Signature), verified ? Has.Count.EqualTo(1) : Is.Empty);
        });
    }

    [Test]
    public void OnlyWhatChangedOutsideTheHoversMarksIsAnEffect()
    {
        var before = new Canvas(400, 300);
        before.Ring(100, 100, 20, 20);
        var marked = new Canvas(400, 300);
        marked.Ring(100, 100, 20, 20);
        marked.Fill(98, 98, 24, 24, 90);
        marked.Fill(110, 130, 90, 22);
        var opened = new Canvas(400, 300);
        opened.Ring(100, 100, 20, 20);
        opened.Fill(100, 160, 120, 100, 60);
        PixelBox[] marks = [new PixelBox(100, 100, 20, 20).Inflate(6), new PixelBox(110, 130, 90, 22).Inflate(8)];
        TooltipImage first = TooltipImage.FromBmp(before.Bmp())!;

        Assert.Multiple(() =>
        {
            Assert.That(TooltipImage.ChangedOutside(first, TooltipImage.FromBmp(marked.Bmp())!, marks), Is.False);
            Assert.That(TooltipImage.ChangedOutside(first, TooltipImage.FromBmp(opened.Bmp())!, marks), Is.True,
                "a menu that opened below the icon is an effect");
            Assert.That(TooltipImage.ChangedOutside(first, TooltipImage.FromBmp(new Canvas(300, 300).Bmp())!, marks), Is.True,
                "a window that changed size changed");
        });
    }

    [Test]
    public async Task ALearnedPlaceWhosePressChangesNothingIsForgotten()
    {
        var desktop = new FakeDesktop { ChangesAfterPress = false };
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));
        Remember(cache, desktop, "Configuración", "tooltipUia");
        var locator = new WindowsVisibleTooltipLocator(new FakeWorker(desktop), desktop, cache);

        ExternalCapabilityReceipt? receipt = await locator.TryClickAsync(
            "input.visible.click", "Configuración", new RecordingPress { Desktop = desktop }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt?.Verified, Is.False);
            Assert.That(cache.For(desktop.Signature), Is.Empty);
        });
    }

    [Test]
    public async Task ATooltipThatNamesSomethingElseIsKeptButNothingIsPressed()
    {
        var desktop = new FakeDesktop();
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":40,"controls":[{"kind":"Button","id":"1","rect":{"x":1100,"y":510,"w":24,"h":24}}]}""",
        };
        worker.TipAt[(1112, 522)] = "Notificaciones";
        desktop.Image.Ring(100, 10, 24, 24);
        var press = new RecordingPress { Desktop = desktop };
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));
        var locator = new WindowsVisibleTooltipLocator(worker, desktop, cache);

        ExternalCapabilityReceipt? first = await locator.TryClickAsync("input.visible.click", "Descargas", press, CancellationToken.None);
        int hovered = desktop.Hovers.Count;
        ExternalCapabilityReceipt? second = await locator.TryClickAsync("input.visible.click", "Descargas", press, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.Null);
            Assert.That(second, Is.Null);
            Assert.That(press.Points, Is.Empty);
            Assert.That(hovered, Is.EqualTo(1));
            Assert.That(desktop.Hovers, Has.Count.EqualTo(1), "a place whose label is known is not hovered again");
        });
    }

    [Test]
    public async Task ATooltipShownAwayFromTheHoveredControlIsNotItsName()
    {
        var desktop = new FakeDesktop();
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":40,"controls":[{"kind":"Button","id":"1","rect":{"x":1100,"y":510,"w":24,"h":24}}]}""",
            TipsElsewhere = true,
        };
        worker.TipAt[(1112, 522)] = "Eliminar";
        var press = new RecordingPress { Desktop = desktop };
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, cache)
            .TryClickAsync("input.visible.click", "Eliminar", press, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Null, "a tooltip far from the cursor is another control's (the person's, a late one)");
            Assert.That(press.Points, Is.Empty);
            Assert.That(cache.For(desktop.Signature), Is.Empty, "nothing is kept under the candidate's place");
            Assert.That(desktop.Hovers, Has.Count.EqualTo(1), "counter-case below: the same tooltip next to it names it");
        });
    }

    [Test]
    public async Task TheListingAndEveryPollFitInTheClicksBudgetOnTheRealClock()
    {
        var desktop = new FakeDesktop();
        string controls = string.Join(',', Enumerable.Range(0, 6).Select(index =>
            "{\"kind\":\"Button\",\"id\":\"" + index + "\",\"rect\":{\"x\":" + (1020 + index * 40) + ",\"y\":510,\"w\":24,\"h\":24}}"));
        var worker = new FakeWorker(desktop)
        {
            Unnamed = "{\"ok\":true,\"error\":\"\",\"named\":40,\"controls\":[" + controls + "]}",
            TipsCostMs = 1500,
        };

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, new TooltipLabelCache(null))
            .TryClickAsync("input.visible.click", "Ajustes", new RecordingPress { Desktop = desktop }, CancellationToken.None);

        var stop = WindowsVisibleTooltipLocator.BudgetMs;
        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Null);
            Assert.That(worker.Timeouts.Single(sent => sent.Command == "unnamed").Timeout.TotalMilliseconds,
                Is.LessThanOrEqualTo(stop), "the listing is part of the click's budget");
            Assert.That(worker.Timeouts.Where(sent => sent.Command == "tooltips"),
                Has.All.Matches<(string Command, TimeSpan Timeout, long At)>(sent => sent.At + sent.Timeout.TotalMilliseconds <= stop + WindowsVisibleTooltipLocator.PollMs),
                "no poll is allowed past the budget");
            Assert.That(desktop.NowMs, Is.LessThanOrEqualTo(stop + WindowsVisibleTooltipLocator.PollMs));
            Assert.That(desktop.Hovers, Has.Count.LessThan(6), "slow polls leave candidates unhovered");
            Assert.That(desktop.Restored, Is.EqualTo(desktop.Hovers.Count));
        });
    }

    [Test]
    public async Task AWorkerTooSlowToPollIsNotAskedAgainWhileTheCursorIsHeld()
    {
        var desktop = new FakeDesktop { DrawsTooltip = true };
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":40,"controls":[{"kind":"Button","id":"1","rect":{"x":1040,"y":512,"w":20,"h":20}}]}""",
        };
        var locator = new WindowsVisibleTooltipLocator(worker, desktop, new TooltipLabelCache(null));
        worker.TipsSilent = true;

        ExternalCapabilityReceipt? receipt = await locator.TryClickAsync(
            "input.visible.click", "ajustes", new RecordingPress { Desktop = desktop }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(worker.Commands.Count(command => command.Contains("tooltips", StringComparison.Ordinal)), Is.EqualTo(1),
                "the first silence ends the polling");
            Assert.That(receipt?.Result?.GetProperty("nameSource").GetString(), Is.EqualTo("tooltipOcr"),
                "the capture still reads the drawn tooltip");
            Assert.That(desktop.OcrWhileHovering, Is.Zero, "the OCR runs after the cursor and the front are given back");
        });
    }

    [Test]
    public async Task WithoutTheMissionsWindowOrOnAProtectedWindowNothingIsHovered()
    {
        var unbound = new FakeDesktop { Window = 0 };
        var protectedWindow = new FakeDesktop { ProcessName = "Code" };
        var unboundWorker = new FakeWorker(unbound);
        var protectedWorker = new FakeWorker(protectedWindow);

        ExternalCapabilityReceipt? none = await new WindowsVisibleTooltipLocator(unboundWorker, unbound, new TooltipLabelCache(null))
            .TryClickAsync("input.visible.click", "Ajustes", new RecordingPress(), CancellationToken.None);
        ExternalCapabilityReceipt? editor = await new WindowsVisibleTooltipLocator(protectedWorker, protectedWindow, new TooltipLabelCache(null))
            .TryClickAsync("input.visible.click", "Ajustes", new RecordingPress(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(none, Is.Null);
            Assert.That(editor, Is.Null);
            Assert.That(unboundWorker.Commands, Is.Empty);
            Assert.That(protectedWorker.Commands, Is.Empty);
            Assert.That(unbound.Bursts + protectedWindow.Bursts, Is.EqualTo(0));
        });
    }

    [Test]
    public async Task APersonWhoMovesDuringTheHoverStopsItAndNothingIsLearned()
    {
        var desktop = new FakeDesktop { PersonActsAfterHover = true };
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":40,"controls":[{"kind":"Button","id":"1","rect":{"x":1100,"y":510,"w":24,"h":24}},{"kind":"Button","id":"2","rect":{"x":1140,"y":510,"w":24,"h":24}}]}""",
        };
        worker.TipAt[(1112, 522)] = "Ajustes";
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, cache)
            .TryClickAsync("input.visible.click", "Ajustes", new RecordingPress { Desktop = desktop }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Null);
            Assert.That(desktop.Hovers, Has.Count.EqualTo(1), "the second candidate is not hovered");
            Assert.That(desktop.Restored, Is.EqualTo(1));
            Assert.That(cache.For(desktop.Signature), Is.Empty);
        });
    }

    [Test]
    public async Task APersonWhoDoesNotPauseIsNeverHovered()
    {
        var desktop = new FakeDesktop { Refusal = "input_user_not_paused" };
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":40,"controls":[{"kind":"Button","id":"1","rect":{"x":1100,"y":510,"w":24,"h":24}}]}""",
        };

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, new TooltipLabelCache(null))
            .TryClickAsync("input.visible.click", "Ajustes", new RecordingPress { Desktop = desktop }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Null);
            Assert.That(desktop.Hovers, Is.Empty);
        });
    }

    [Test]
    public async Task OnAWindowWithoutATreeTheIconRegionsAreHoveredAndADrawnTooltipIsReadByOcr()
    {
        var desktop = new FakeDesktop { DrawsTooltip = true };
        desktop.Image.Ring(40, 12, 20, 20);
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":0,"controls":[]}""",
        };
        var cache = new TooltipLabelCache(Path.Combine(_directory, "labels.json"));
        var press = new RecordingPress { Desktop = desktop };

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, cache)
            .TryClickAsync("input.visible.click", "ajustes", press, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt?.Verified, Is.True);
            Assert.That(receipt!.Result!.Value.GetProperty("nameSource").GetString(), Is.EqualTo("tooltipOcr"));
            Assert.That(desktop.Hovers, Is.EqualTo(new[] { (1000 + 50, 500 + 22) }), "the icon's centre on the screen");
            Assert.That(press.Points, Is.EqualTo(new[] { (1050, 522) }));
            Assert.That(press.ControlIds, Is.Empty, "a drawn region has no identity");
            Assert.That(desktop.OcrWhileHovering, Is.Zero, "the tooltip is read after the cursor is given back");
        });
    }

    [Test]
    public async Task AWorkerThatDoesNotAnswerIsNoWindowWithoutATree()
    {
        var desktop = new FakeDesktop();
        desktop.Image.Ring(40, 12, 20, 20);
        var worker = new FakeWorker(desktop) { Unnamed = """{"ok":false,"error":"visible_controls_uia_failed"}""" };

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, new TooltipLabelCache(null))
            .TryClickAsync("input.visible.click", "ajustes", new RecordingPress { Desktop = desktop }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Null);
            Assert.That(desktop.Hovers, Is.Empty, "the tree was not read: its icons are not guessed from the image");
        });
    }

    [Test]
    public async Task ATreeWithNamesButNoUnnamedControlsIsNotSearchedForDrawnIcons()
    {
        var desktop = new FakeDesktop();
        desktop.Image.Ring(40, 12, 20, 20);
        var worker = new FakeWorker(desktop)
        {
            Unnamed = """{"ok":true,"error":"","named":30,"controls":[]}""",
        };

        ExternalCapabilityReceipt? receipt = await new WindowsVisibleTooltipLocator(worker, desktop, new TooltipLabelCache(null))
            .TryClickAsync("input.visible.click", "ajustes", new RecordingPress { Desktop = desktop }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Null);
            Assert.That(desktop.Hovers, Is.Empty);
            Assert.That(desktop.OcrReads, Is.EqualTo(0));
        });
    }

    [Test]
    public void TheWorkerListsOnlyActionableIconSizedControlsWithoutAnyNameAndReadsTooltipText()
    {
        string worker = File.ReadAllText(WorkerPath());
        Assert.Multiple(() =>
        {
            Assert.That(worker, Does.Contain("elseif($cmd -eq 'unnamed'){ Send-Line (Do-Unnamed $request) }"));
            Assert.That(worker, Does.Contain("elseif($cmd -eq 'tooltips'){ Send-Line (Do-Tooltips $request) }"));
        });
        JsonElement answer = ComputerUseTooltipWorker.Run("""
            $Actionable=@('Button','MenuItem','ListItem','TabItem','Hyperlink','CheckBox','RadioButton','Edit','ComboBox','TreeItem','SplitButton','Slider','Document')
            $icon=@{ x=10; y=10; w=24; h=24 }
            $zone=@{ x=0; y=0; w=600; h=300 }
            $out=@(
              (Test-HoverCandidate 'Button' '' $icon),
              (Test-HoverCandidate 'Button' 'Ajustes' $icon),
              (Test-HoverCandidate 'Edit' '' $icon),
              (Test-HoverCandidate 'Pane' '' $icon),
              (Test-HoverCandidate 'Button' '' $zone),
              (Test-HoverCandidate 'Button' '' $null),
              (Get-TipName 'ToolTip' 'Configuración' '' ''),
              (Get-TipName 'Window' '' 'Popup' 'Silenciar'),
              (Get-TipName 'Pane' 'Ajustes' 'tooltips_class32' ''),
              (Get-TipName 'Pane' 'Ajustes' 'MainWindow' ''))
            [Console]::Out.Write((ConvertTo-Json -Compress $out))
            """, WorkerPath());

        Assert.That(answer.EnumerateArray().Select(item => item.ToString()), Is.EqualTo(new[]
        {
            "True",           // an icon-sized button without a name
            "False",          // counter-case: one with a name is in the view already
            "False",          // a field is told by its value
            "False",          // a pane is not actionable
            "False",          // a zone-sized control is not an icon
            "False",          // without a rectangle there is nothing to hover
            "Configuración",  // a ToolTip's name
            "Silenciar",      // a ToolTip inside a pop-up
            "Ajustes",        // a window whose class says tooltip
            "",               // counter-case: any other small window of the process is not a tooltip
        }));
    }

    [Test]
    public void TheWorkerRefusesARememberedPlaceOnlyForAControlOfItsSizeWithAnotherName()
    {
        JsonElement answer = ComputerUseTooltipWorker.Run("""
            function Entry($area,$names){ return [pscustomobject]@{ area=$area; names=@($names) } }
            $out=@(
              (Test-NamedOther @((Entry 576 @('Eliminar'))) 2304),
              (Test-NamedOther @((Entry 576 @(''))) 2304),
              (Test-NamedOther @((Entry 576 @('3'))) 2304),
              (Test-NamedOther @((Entry 60000 @('Barra de herramientas'))) 2304),
              (Test-NamedOther @((Entry 576 @('Eliminar'))) 0))
            [Console]::Out.Write((ConvertTo-Json -Compress $out))
            """, WorkerPath());

        Assert.That(answer.EnumerateArray().Select(item => item.GetBoolean()), Is.EqualTo(new[]
        {
            true,   // a control of the icon's size named otherwise is another control
            false,  // counter-case: one without a name is the remembered icon
            false,  // a badge's number names nothing
            false,  // the toolbar around the place is not the control there
            false,  // without the place's size nothing is refused
        }));
    }

    // Changed by the review of fable/cu-v3-tooltip: the stage ran on the first look, while a page still drawing could
    // show the label to a later look (UI1731), and its time came out of the label's wait. It runs on the last look now.
    [Test]
    public async Task TheClickAsksTheTooltipStageOnceOnItsLastLookOnlyOnTheMissionsWindow()
    {
        var order = new List<string>();
        var timing = VisibleClickTiming.Default with
        {
            SettledLabel = TimeSpan.FromMilliseconds(300),
            Interval = TimeSpan.FromMilliseconds(40),
        };
        WindowsVisibleControlAdapter Adapter() => new(
            new ComputerUsePerceptionTests.ScriptedUiaWorker("""{"ok":false,"error":"visible_button_not_found"}"""),
            new OrderedLocator("ocr", order),
            new OrderedLocator("vision", order),
            timing: timing,
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null),
            tooltip: new OrderedLocator("tooltip", order));
        using var bound = Adapter();
        using var unbound = Adapter();
        using var cancel = new CancellationTokenSource(TimeSpan.FromSeconds(30));

        await bound.InvokeAsync("input.visible.click",
            JsonDocument.Parse("""{"label":"Ajustes","window":4660}""").RootElement, cancel.Token);
        List<string> boundOrder = [.. order];
        order.Clear();
        await unbound.InvokeAsync("input.visible.click",
            JsonDocument.Parse("""{"label":"Ajustes"}""").RootElement, cancel.Token);

        int hover = boundOrder.IndexOf("tooltip");
        Assert.Multiple(() =>
        {
            Assert.That(boundOrder.Count(stage => stage == "tooltip"), Is.EqualTo(1), "once per click, not per look");
            Assert.That(boundOrder.Take(hover).Count(stage => stage == "ocr"), Is.GreaterThan(1),
                "the click looked more than once before hovering");
            Assert.That(boundOrder.Skip(hover), Does.Not.Contain("ocr"), "after the last look");
            Assert.That(order, Does.Not.Contain("tooltip"), "never on the window a person has in front outside a mission");
        });
    }

    [Test]
    public async Task ALabelALaterLookFindsIsNeverLookedForByHovering()
    {
        var order = new List<string>();
        var timing = VisibleClickTiming.Default with
        {
            SettledLabel = TimeSpan.FromMilliseconds(300),
            Interval = TimeSpan.FromMilliseconds(40),
        };
        using var adapter = new WindowsVisibleControlAdapter(
            new ComputerUsePerceptionTests.ScriptedUiaWorker("""{"ok":false,"error":"visible_button_not_found"}"""),
            new SecondLookLocator("ocr", order),
            new OrderedLocator("vision", order),
            timing: timing,
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null),
            tooltip: new OrderedLocator("tooltip", order));
        using var cancel = new CancellationTokenSource(TimeSpan.FromSeconds(30));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("input.visible.click",
            JsonDocument.Parse("""{"label":"Biblioteca","window":4660}""").RootElement, cancel.Token);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, "the page finished drawing and OCR read the label");
            Assert.That(order, Does.Not.Contain("tooltip"), "no control of a page still drawing was hovered");
        });
    }

    [Test]
    public async Task OnAWindowThatHoldsStillTheTooltipStageRunsWhenTheWaitEnds()
    {
        var order = new List<string>();
        var timing = VisibleClickTiming.Default with
        {
            SettledLabel = TimeSpan.FromSeconds(20),
            Interval = TimeSpan.FromMilliseconds(200),
            StillSample = TimeSpan.FromMilliseconds(20),
            StillFor = TimeSpan.FromMilliseconds(60),
        };
        using var adapter = new WindowsVisibleControlAdapter(
            new ComputerUsePerceptionTests.ScriptedUiaWorker("""{"ok":false,"error":"visible_button_not_found"}"""),
            new OrderedLocator("ocr", order),
            new OrderedLocator("vision", order),
            timing: timing,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"),
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null),
            tooltip: new OrderedLocator("tooltip", order));
        using var cancel = new CancellationTokenSource(TimeSpan.FromSeconds(15));

        await adapter.InvokeAsync("input.visible.click",
            JsonDocument.Parse("""{"label":"Ajustes","window":4660}""").RootElement, cancel.Token);

        Assert.That(order, Is.EqualTo(new[] { "ocr", "vision", "tooltip" }),
            "a still window ends the wait after one look; the hover comes then, once");
    }

    private sealed class SecondLookLocator(string stage, List<string> order) : IVisibleControlLocator
    {
        private int _looks;

        public string Stage => stage;

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken)
        {
            order.Add(stage);
            if (++_looks < 2)
                return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteBoolean("ok", true);
                writer.WriteString("name", label);
                writer.WriteEndObject();
            });
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(ExternalJson.Success(operation, result, true));
        }
    }

    private sealed class OrderedLocator(string stage, List<string> order) : IVisibleControlLocator
    {
        public string Stage => stage;

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken)
        {
            order.Add(stage);
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
        }
    }

    /// <summary>A label remembered at the place (140,10) of the fake window, with the print of the icon drawn there.</summary>
    private static void Remember(TooltipLabelCache cache, FakeDesktop desktop, string label, string source, PixelBox? tip = null)
    {
        desktop.Image.Ring(140, 10, 24, 24);
        string place = TooltipLabelCache.Place(new PixelBox(140, 10, 24, 24));
        cache.Put(desktop.Signature, place, label, source,
            TooltipImage.FromBmp(desktop.Image.Bmp())!.Print(TooltipLabelCache.FromPlace(place)!.Value), tip);
    }

    private static string WorkerPath()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    // ---------------------------------------------------------------- fakes

    /// <summary>A white 32-bit canvas drawn with dark shapes, kept as the bottom-up BMP the captures use.</summary>
    internal sealed class Canvas(int width, int height)
    {
        private readonly byte[] _pixels = Enumerable.Repeat((byte)255, width * height * 4).ToArray();

        internal void Fill(int x, int y, int w, int h, byte value = 0)
        {
            for (int row = y; row < y + h; row++)
            {
                for (int column = x; column < x + w; column++)
                {
                    int at = (row * width + column) * 4;
                    _pixels[at] = value;
                    _pixels[at + 1] = value;
                    _pixels[at + 2] = value;
                }
            }
        }

        internal void Ring(int x, int y, int w, int h)
        {
            Fill(x, y, w, 2);
            Fill(x, y + h - 2, w, 2);
            Fill(x, y, 2, h);
            Fill(x + w - 2, y, 2, h);
            Fill(x + w / 2 - 1, y + 4, 2, h - 8);
        }

        internal byte[] Bmp()
        {
            const int header = 54;
            int stride = width * 4;
            byte[] result = new byte[header + stride * height];
            result[0] = (byte)'B';
            result[1] = (byte)'M';
            BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(10), header);
            BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(14), 40);
            BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(18), width);
            BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(22), height);
            BinaryPrimitives.WriteInt16LittleEndian(result.AsSpan(26), 1);
            BinaryPrimitives.WriteInt16LittleEndian(result.AsSpan(28), 32);
            for (int row = 0; row < height; row++)
                Buffer.BlockCopy(_pixels, row * stride, result, header + (height - 1 - row) * stride, stride);
            return result;
        }
    }

    private sealed class FakeBurst(FakeDesktop desktop, string? refusal) : IInputBurst
    {
        private bool? _restored;

        public string? Refusal { get; } = refusal;

        public long WaitedMs => 0;

        public bool UserActed => desktop.PersonActsAfterHover && desktop.Hovers.Count > 0;

        public bool Restore()
        {
            if (_restored is null && Refusal is null)
                desktop.Restored++;
            _restored ??= true;
            return true;
        }
    }

    internal sealed class FakeDesktop : ITooltipDesktop
    {
        internal nint Window { get; set; } = 77;

        internal string ProcessName { get; set; } = "App";

        internal string? Refusal { get; set; }

        internal bool PersonActsAfterHover { get; set; }

        internal bool DrawsTooltip { get; set; }

        internal bool ChangesAfterPress { get; set; } = true;

        /// <summary>The press is the pointer's: the cursor stays on the icon and its tooltip shows again.</summary>
        internal bool TooltipAfterPress { get; set; }

        internal (int X, int Y)? PressPoint { get; set; }

        internal Canvas Image { get; } = new(400, 300);

        internal List<(int X, int Y)> Hovers { get; } = [];

        internal (int X, int Y)? Cursor { get; private set; }

        internal int Bursts { get; private set; }

        internal int Restored { get; set; }

        internal int OcrReads { get; private set; }

        internal bool Pressed { get; set; }

        internal string Signature => TooltipLabelCache.Signature(ProcessName, "MainWindow", 400, 300);

        private long _now;

        /// <summary>OCR reads made while a candidate was hovered (the cursor not given back yet).</summary>
        internal int OcrWhileHovering { get; private set; }

        internal void Advance(int milliseconds) => _now += milliseconds;

        public nint BoundWindow() => Window;

        public (int ProcessId, string ProcessName) Process(nint window) => (4242, ProcessName);

        public IReadOnlyList<int> DrawingProcesses(nint window) => [4242, 5353];

        public string ClassName(nint window) => "MainWindow";

        public ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(
            nint window, bool? selfDrawn, CancellationToken cancellationToken)
        {
            byte[] bmp;
            string sha;
            if (DrawsTooltip && Cursor is { } cursor && Restored < Hovers.Count)
            {
                var drawn = new Canvas(400, 300);
                byte[] copy = Image.Bmp();
                // The tooltip appears below the cursor, inside the window.
                bmp = WithTooltip(copy, cursor.X - 1000, cursor.Y - 500 + 20);
                sha = "tooltip";
                _ = drawn;
            }
            else
            {
                bmp = Image.Bmp();
                sha = "before";
                if (Pressed && ChangesAfterPress)
                {
                    // What the press opened: a panel away from the icon.
                    bmp = WithPanel(bmp);
                    sha = "after";
                }

                if (Pressed && TooltipAfterPress && PressPoint is { } point)
                {
                    // The cursor left on the icon brings its tooltip back, whatever the press did.
                    bmp = WithTooltip(bmp, point.X - 1000, point.Y - 500 + 20);
                    sha += "+tooltip";
                }
            }

            return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, bmp, 1000, 500, 400, 300, sha));
        }

        private static byte[] WithPanel(byte[] bmp)
        {
            TooltipImage image = TooltipImage.FromBmp(bmp)!;
            var canvas = new Canvas(image.Width, image.Height);
            for (int row = 0; row < image.Height; row++)
            {
                for (int column = 0; column < image.Width; column++)
                {
                    if (image.Bgra[(row * image.Width + column) * 4] < 128)
                        canvas.Fill(column, row, 1, 1);
                }
            }

            canvas.Fill(250, 200, 100, 60, 60);
            return canvas.Bmp();
        }

        private static byte[] WithTooltip(byte[] bmp, int x, int y)
        {
            TooltipImage image = TooltipImage.FromBmp(bmp)!;
            var canvas = new Canvas(image.Width, image.Height);
            for (int row = 0; row < image.Height; row++)
            {
                for (int column = 0; column < image.Width; column++)
                {
                    int at = (row * image.Width + column) * 4;
                    if (image.Bgra[at] < 128)
                        canvas.Fill(column, row, 1, 1);
                }
            }

            canvas.Fill(x, y, 70, 18);
            return canvas.Bmp();
        }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken)
        {
            if (Refusal is null)
                Bursts++;
            return ValueTask.FromResult<IInputBurst>(new FakeBurst(this, Refusal));
        }

        public bool HoldsPoint(nint window, int screenX, int screenY) => true;

        public bool Hover(IInputBurst burst, int screenX, int screenY)
        {
            if (!burst.MayAct)
                return false;
            Hovers.Add((screenX, screenY));
            Cursor = (screenX, screenY);
            return true;
        }

        public ValueTask<IReadOnlyList<(string Text, PixelBox Box)>> ReadLinesAsync(byte[] bmp, CancellationToken cancellationToken)
        {
            OcrReads++;
            if (Restored < Hovers.Count)
                OcrWhileHovering++;
            TooltipImage image = TooltipImage.FromBmp(bmp)!;
            // A crop that is mostly dark is the drawn tooltip.
            int dark = 0;
            for (int at = 0; at < image.Bgra.Length; at += 4)
            {
                if (image.Bgra[at] < 128)
                    dark++;
            }

            bool tooltip = image.Width < 200 && dark * 2 > image.Width * image.Height;
            return ValueTask.FromResult<IReadOnlyList<(string Text, PixelBox Box)>>(
                tooltip ? [("Ajustes", new PixelBox(0, 0, image.Width, image.Height))] : []);
        }

        public long NowMs => _now;

        public ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken)
        {
            _now += milliseconds;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class FakeWorker(FakeDesktop desktop) : IUiaWorker
    {
        internal string Unnamed { get; set; } = """{"ok":true,"error":"","named":0,"controls":[]}""";

        internal Dictionary<(int X, int Y), string> TipAt { get; } = [];

        /// <summary>Where the tooltip shows: below the cursor by default; far from it for another control's.</summary>
        internal bool TipsElsewhere { get; set; }

        internal List<string> Commands { get; } = [];

        /// <summary>The budget each command was sent with, by command.</summary>
        internal List<(string Command, TimeSpan Timeout, long At)> Timeouts { get; } = [];

        /// <summary>How long each «tooltips» poll takes on the desktop's clock (a large tree is slow to search).</summary>
        internal int TipsCostMs { get; set; }

        /// <summary>The worker does not answer «tooltips» in time (null, as the host answers a timeout).</summary>
        internal bool TipsSilent { get; set; }

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Commands.Add(commandJson);
            string command = (string)JsonNode.Parse(commandJson)!["cmd"]!;
            Timeouts.Add((command, timeout, desktop.NowMs));
            if (command == "tooltips")
            {
                desktop.Advance(Math.Min(TipsCostMs, (int)timeout.TotalMilliseconds));
                if (TipsSilent)
                    return ValueTask.FromResult<JsonDocument?>(null);
            }
            string answer = command switch
            {
                "unnamed" => Unnamed,
                "tooltips" => desktop.Cursor is { } cursor && desktop.Restored < desktop.Hovers.Count
                    && TipAt.TryGetValue(cursor, out string? tip)
                    ? new JsonObject
                    {
                        ["ok"] = true,
                        ["tips"] = new JsonArray(new JsonObject
                        {
                            ["name"] = tip,
                            ["rect"] = TipsElsewhere
                                ? new JsonObject { ["x"] = cursor.X + 900, ["y"] = cursor.Y + 700, ["w"] = 140, ["h"] = 22 }
                                : new JsonObject { ["x"] = cursor.X - 20, ["y"] = cursor.Y + 18, ["w"] = 140, ["h"] = 22 },
                        }),
                    }.ToJsonString()
                    : """{"ok":true,"tips":[]}""",
                _ => """{"ok":false,"error":"uia_worker_unknown_command"}""",
            };
            return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));
        }
    }

    private sealed class RecordingPress : IPointPress
    {
        internal List<(int X, int Y)> Points { get; } = [];

        internal List<string> ControlIds { get; } = [];

        internal List<(int X, int Y, int W, int H)> Remembered { get; } = [];

        internal List<(int X, int Y)> Pointer { get; } = [];

        /// <summary>The worker finds a control with another name at a remembered place.</summary>
        internal bool RefuseRemembered { get; set; }

        public ValueTask<PointPressed> PressRememberedAtAsync(
            nint window, int screenX, int screenY, int width, int height, string label, CancellationToken cancellationToken)
        {
            Remembered.Add((screenX, screenY, width, height));
            return RefuseRemembered
                ? ValueTask.FromResult(PointPressed.Refused)
                : PressAtAsync(window, screenX, screenY, label, cancellationToken);
        }

        public ValueTask<PointPressed> PressControlAtAsync(
            nint window, int screenX, int screenY, string label, string controlId, CancellationToken cancellationToken)
        {
            ControlIds.Add(controlId);
            return PressAtAsync(window, screenX, screenY, label, cancellationToken);
        }

        internal FakeDesktop? Desktop { get; set; }

        public ValueTask<PointPressed> PressAtAsync(
            nint window, int screenX, int screenY, string label, CancellationToken cancellationToken)
        {
            Points.Add((screenX, screenY));
            if (Desktop is not null)
            {
                Desktop.Pressed = true;
                Desktop.PressPoint = (screenX, screenY);
            }
            return ValueTask.FromResult(new PointPressed(PointPressOutcome.Pressed, "invoke"));
        }

        public ValueTask<PointerPressed> PointerAtAsync(
            nint window,
            int screenX,
            int screenY,
            VisibleControlSurface.CapturedWindow? located,
            PointRelocator? relocate,
            CancellationToken cancellationToken)
        {
            Pointer.Add((screenX, screenY));
            return ValueTask.FromResult(new PointerPressed(false, null, "unused"));
        }
    }
}

/// <summary>The worker's own functions, taken from the script by its syntax tree and run on plain values.</summary>
internal static class ComputerUseTooltipWorker
{
    internal static JsonElement Run(string body, string workerPath)
    {
        string script = """
            $ErrorActionPreference='Stop'
            [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_TOOLTIP_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Format-Name','Get-Cut','Test-HoverCandidate','Get-TipName','Test-NamedOther')
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne $wanted.Count){ throw 'worker functions missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }

            """ + body;
        var start = new System.Diagnostics.ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = System.Text.Encoding.UTF8,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(System.Text.Encoding.Unicode.GetBytes(script)));
        start.Environment["BAXY_TOOLTIP_WORKER"] = workerPath;
        using System.Diagnostics.Process process = System.Diagnostics.Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the worker functions answer");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return JsonDocument.Parse(output).RootElement.Clone();
    }
}
