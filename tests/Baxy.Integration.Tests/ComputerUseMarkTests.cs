using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// v3 punto 5 (live 2026-10-07 v2-s12, v2-c17): Steam already on its library was told «Parece que ya estabas…». The
/// check atom mark:X (CONTRATO_VISTA_ACCION.md §1.7, §4.3) reads the row of navigation labels a window drawn without an
/// accessible tree marks by its ink. The views are the bench's own captures (tests/data/cu_text_marks.json).
/// </summary>
[TestFixture]
public sealed class ComputerUseMarkTests
{
    // The views are the named application's own window (the adapter's «requested»), as the loop reads them.
    internal static JsonObject Capture(string name, string? coveredBy = null, bool requested = true)
    {
        var fixture = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            FindRepositoryRoot(), "tests", "data", "cu_text_marks.json")))!;
        var captured = (JsonObject)fixture["views"]![name]!;
        var view = new JsonObject
        {
            ["window"] = captured["window"]!.DeepClone(),
            ["controls"] = new JsonArray(new JsonObject { ["i"] = 0, ["kind"] = "Document", ["name"] = "Steam" }),
            ["text"] = captured["text"]!.DeepClone(),
            ["textMarks"] = captured["textMarks"]!.DeepClone(),
            ["authority"] = "windows_media_ocr_lines",
        };
        view["window"]!["requested"] = requested;
        if (coveredBy is not null)
        {
            view["window"]!["coveredBy"] = new JsonObject { ["title"] = coveredBy, ["process"] = "CalculatorApp" };
        }

        return view;
    }

    private static JsonArray Click(string label) =>
    [
        new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = label, ["name"] = label.ToUpperInvariant() },
    ];

    private static JsonArray Clicks(params string[] labels) =>
        new(labels.Select((label, index) => (JsonNode?)new JsonObject
        {
            ["step"] = index + 1,
            ["operation"] = "input.visible.click",
            ["ok"] = true,
            ["label"] = label,
            ["name"] = label.ToUpperInvariant(),
        }).ToArray());

    private static JsonArray Unverified(string label) =>
    [
        new JsonObject
        {
            ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = label,
            ["error"] = "visible_click_postread_invalid", ["effectUncertain"] = true,
        },
    ];

    private static JsonArray NotFound(string label) =>
    [
        new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = label, ["error"] = "visible_button_not_found" },
    ];

    [Test]
    public void OnTheLibraryTheLibraryLabelIsTheMarkedOne()
    {
        JsonObject library = Capture("library");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca|mark:biblioteca", library, [], out string? by), Is.True);
            Assert.That(by, Is.EqualTo("mark:biblioteca"));
            Assert.That(ComputerUseSuccessCheck.Atom("mark:BIBLIOTECA", library, []), Is.True, "folded");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:tienda", library, []), Is.False, "written like its neighbours");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:comunidad", library, []), Is.False);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:library", library, []), Is.False, "not written on this window");
        });
    }

    [Test]
    public void OnTheStoreTheLibraryLabelIsNeverMarked()
    {
        // Contracase: the same row on the store marks «TIENDA»; «BIBLIOTECA», written like its neighbours, never passes.
        JsonObject store = Capture("store");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", store, []), Is.False);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:tienda", store, []), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "control:biblioteca:current|title:biblioteca|page:biblioteca|mark:biblioteca", store, Click("biblioteca"), out _),
                Is.False, "a click that only opened the menu on another page");
        });
    }

    [Test]
    public void ACoveredWindowIsJudgedByItsOwnDrawing()
    {
        // Rewritten for banco r23b x10 (it fixed that a covered window never passes): since v3 point 0 a window another
        // one covers is captured as it draws itself, so its inks are its own. Steam's library under Spotify passes as
        // uncovered; the contracase keeps: on its store, covered, «BIBLIOTECA» never passes and «TIENDA» does.
        JsonObject store = Capture("store", coveredBy: "Spotify Premium");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", Capture("library", coveredBy: "Spotify Premium"), []), Is.True);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", store, []), Is.False);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:tienda", store, []), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "page:biblioteca|mark:biblioteca", store, Click("biblioteca"), out _), Is.False, "a click that only opened the menu");
        });
    }

    [Test]
    public void AnotherApplicationsWindowInFrontNeverPasses()
    {
        // Review 2026-10-07: «abre Epic Games y andá a la biblioteca» with Epic closed reads the window in front (the
        // adapter's requested=false); Steam's library marked there is not Epic's. With no application named, the window
        // in front is the mission's own (the loop's onTheApplication).
        JsonObject front = Capture("library", requested: false);
        JsonObject frontNamed = Capture("library", requested: false);
        frontNamed["onTheApplication"] = false;
        JsonObject frontUnnamed = Capture("library", requested: false);
        frontUnnamed["onTheApplication"] = true;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", front, []), Is.False, "not known to be the mission's window");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", frontNamed, []), Is.False, "another application's window");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", frontUnnamed, []), Is.True, "no application named");
        });
    }

    [Test]
    public void ARowWithOneOtherLabelOrNeighboursOfMixedInksTellsNothing()
    {
        JsonObject pair = Capture("library");
        var marks = (JsonArray)pair["textMarks"]!;
        marks.RemoveAt(3);
        marks.RemoveAt(2);
        JsonObject mixed = Capture("library");
        mixed["textMarks"]![2]!["ink"] = "green";
        JsonObject alone = Capture("library");
        // The other labels of another row (rows apart by more than half the label's height) are not its neighbours.
        foreach (JsonNode? mark in (JsonArray)alone["textMarks"]!)
        {
            if ((string?)mark!["text"] != "BIBLIOTECA")
            {
                mark["rect"]!["y"] = 60;
            }
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", pair, []), Is.False, "a single other label");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", mixed, []), Is.False, "neighbours of mixed inks");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", alone, []), Is.False, "alone in its row");
        });
    }

    [Test]
    public void TwoColourlessInksAreTheSameWithinTheirBrightness()
    {
        // The launcher's white (V 0.87) sits on §1.5's white/gray cut: one label read «gray» is still its neighbours'
        // ink; a white label among gray ones far darker is marked.
        JsonObject library = Capture("library");
        library["textMarks"]![2]!["ink"] = "gray";
        library["textMarks"]![2]!["inkV"] = 214;
        JsonObject whiteOnGray = Capture("store");
        foreach (JsonNode? mark in (JsonArray)whiteOnGray["textMarks"]!)
        {
            (mark!["ink"], mark["inkV"]) = (string?)mark["text"] == "BIBLIOTECA" ? ("white", 240) : ("gray", 140);
        }

        JsonObject nearlyAlike = Capture("store");
        nearlyAlike["textMarks"]![0]!["ink"] = "white";
        nearlyAlike["textMarks"]![0]!["inkV"] = 250;

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", library, []), Is.True);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:comunidad", library, []), Is.False);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", whiteOnGray, []), Is.True);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:tienda", nearlyAlike, []), Is.False, "27 of brightness is no other ink");
        });
    }

    [Test]
    public void AColourlessLabelDimmerThanItsRowIsNeverTheMarkedOne()
    {
        // Review 2026-10-07: in a row without a tree the darker, greyed-out label is the disabled or unavailable one.
        // A colourless label is marked only when it stands out from the background (bgV) more than its neighbours.
        JsonObject dimmed = Capture("store");
        foreach (JsonNode? mark in (JsonArray)dimmed["textMarks"]!)
        {
            (mark!["ink"], mark["inkV"]) = (string?)mark["text"] == "BIBLIOTECA" ? ("gray", 110) : ("white", 223);
        }

        JsonObject grayAmongBlue = Capture("store");
        foreach (JsonNode? mark in (JsonArray)grayAmongBlue["textMarks"]!)
        {
            (mark!["ink"], mark["inkV"]) = (string?)mark["text"] == "BIBLIOTECA" ? ("gray", 110) : ("blue", 255);
        }

        JsonObject noBackground = Capture("store");
        foreach (JsonNode? mark in (JsonArray)noBackground["textMarks"]!)
        {
            (mark!["ink"], mark["inkV"]) = (string?)mark["text"] == "BIBLIOTECA" ? ("white", 240) : ("gray", 140);
            ((JsonObject)mark).Remove("bgV");
        }

        // On a light page the chosen label is the darker one: it stands out from the white more than its neighbours.
        JsonObject darkOnLight = Capture("store");
        foreach (JsonNode? mark in (JsonArray)darkOnLight["textMarks"]!)
        {
            (mark!["ink"], mark["inkV"], mark["bgV"]) = (string?)mark["text"] == "BIBLIOTECA" ? ("black", 20, 250) : ("gray", 130, 250);
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", dimmed, []), Is.False, "dimmer than its row");
            Assert.That(ComputerUseMission.ScreenExcerpt(dimmed).ToJsonString(), Does.Not.Contain("BIBLIOTECA\",\"state\":\"selected"));
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", grayAmongBlue, []), Is.False, "a gray label among coloured ones");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", noBackground, []), Is.False, "no background to tell");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", darkOnLight, []), Is.True, "darker on a light page");
        });
    }

    [Test]
    public void TheLabelTheSubgoalJustClickedIsNotJudgedByItsInk()
    {
        // The pointer resting on the label it clicked may light it: that arrival is page:'s to judge.
        JsonObject library = Capture("library");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", library, Click("biblioteca")), Is.False);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", library, Click("tienda")), Is.True);
            // Review 2026-10-07: a press whose post-read did not hold may have lit it too, and an earlier click on it
            // as well; a click refused before any press (the label not found) did not touch it.
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", library, Unverified("biblioteca")), Is.False, "pressed, unverified");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", library, Clicks("biblioteca", "tienda")), Is.False,
                "an earlier click on it");
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", library, NotFound("biblioteca")), Is.True, "never pressed");
        });
    }

    [Test]
    public void AWindowWithAnAccessibleTreeIsNotJudgedByItsInk()
    {
        JsonObject tree = Capture("library");
        tree["controls"] = new JsonArray(
            new JsonObject { ["i"] = 0, ["kind"] = "Button", ["name"] = "Biblioteca" },
            new JsonObject { ["i"] = 1, ["kind"] = "Button", ["name"] = "Tienda" });
        Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", tree, []), Is.False);
    }

    [TestCase(null)]
    [TestCase("Spotify Premium")]
    public void TheBackupStopIsNeverSaidWhereTheRowMarksAnotherPage(string? coveredBy)
    {
        // The click on «BIBLIOTECA» on the store only opened its menu and left the text as it was: the row still marks
        // «TIENDA», so «parece que ya estabas en Biblioteca» would be false. Banco r23b x10: covered too (its own drawing).
        JsonObject store = Capture("store", coveredBy);
        var state = new JsonObject { ["textBeforeClick"] = new JsonObject { ["1"] = ComputerUseSuccessCheck.TextLines(store) } };
        JsonObject library = Capture("library", coveredBy);
        var libraryState = new JsonObject { ["textBeforeClick"] = new JsonObject { ["1"] = ComputerUseSuccessCheck.TextLines(library) } };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), store, state), Is.False);
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), library, libraryState), Is.True,
                "the backup stays where the row marks the place itself");
        });
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found.");
    }
}
