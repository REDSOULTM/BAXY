using System.Reflection;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Held-out: a click whose label is not the name of its index's control looks for the label in the tree. When the tree
/// answers not found and its candidates hold that control's name, the cascade ends there: nothing is pressed, no later
/// locator runs, and the receipt carries those candidates and no «next». Anything else keeps its cascade. Every effect
/// goes to fakes: no window is touched.
/// </summary>
[TestFixture]
public sealed class HeldOutIndexCandidatesTests
{
    private const nint Window = 4660;
    private const int Index = 7;
    private const string NotFoundError = "visible_button_not_found";
    private const string SaveAs = "Guardar como";

    private const string NotFound =
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"," +
        "\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false}";

    // The label need not resemble the name: what ends the cascade is the tree offering the index's control.
    [TestCase("Aceptar", SaveAs, """["Guardar como"]""", TestName = "ALoneCandidateOfTheIndexEndsTheCascadeWhateverTheLabel")]
    [TestCase("Cerámica", "Cerámica Inicial", """["CERAMICA inicial","Inicio","Ajustes"]""", TestName = "FirstCandidateFoldsCaseAndAnAccentOnlyInTheName")]
    [TestCase("Facturas", "FACTURACION DE MARZO", """["Inicio","Ajustes","  Facturación   de  marzo "]""", TestName = "LastCandidateFoldsAnAccentOnlyInItAndItsSpaces")]
    [TestCase("Archivo", "Archivo \"final\" \\ copia (2) | ¿seguro?", """["Inicio","Archivo \"final\" \\ copia (2) | ¿seguro?","Ajustes"]""", TestName = "MiddleCandidateWithSignsAndJsonEscapes")]
    public async Task CandidatesWithTheIndexsNameEndTheCascadeAsTheyCame(string label, string name, string candidates)
    {
        var (adapter, worker, locator) = Build(Tree(candidates), Look((2, "Otro control"), (Index, name)));

        ExternalCapabilityReceipt receipt = await Click(adapter, label, Index, Window);

        string?[] given = [.. JsonDocument.Parse(candidates).RootElement.EnumerateArray().Select(static item => item.GetString())
            .OrderBy(item => WindowsVisibleControlAdapter.SameLabel(item!, name) ? 0 : 1)];
        AssertEnded(receipt, worker, locator);
        Assert.That(
            receipt.Result?.GetProperty("candidates").EnumerateArray().Select(static item => item.GetString()),
            Is.EqualTo(given), "the candidates as the tree gave them, the index's name first");
    }

    // Which of the entries that are no text the receipt keeps is not said; that they do not break the reading is.
    [Test]
    public async Task EntriesThatAreNoTextDoNotHideTheIndexsName()
    {
        var (adapter, worker, locator) = Build(
            Tree("""[null,44,true,{"name":"x"},["y"],"Guardar como"]"""), Look((2, "Inicio"), (Index, SaveAs)));

        ExternalCapabilityReceipt receipt = await Click(adapter, "Aceptar", Index, Window);

        AssertEnded(receipt, worker, locator);
        Assert.That(
            receipt.Result?.GetProperty("candidates").EnumerateArray()
                .Where(static item => item.ValueKind == JsonValueKind.String).Select(static item => item.GetString()),
            Does.Contain(SaveAs));
    }

    [TestCase("Guardar", SaveAs, """["Inicio","Guardar como plantilla","Guardar"]""", TestName = "CandidatesOfOtherControlsAndSimilarNamesLeaveTheCascade")]
    [TestCase("Pedido", "44", """[null,44,true,{"name":"44"},["44"]]""", TestName = "ANameOnlyInsideEntriesThatAreNoTextLeavesTheCascade")]
    [TestCase("Guardar", SaveAs, "\"Guardar como\"", TestName = "ACandidatesStringThatIsNoListLeavesTheCascade")]
    [TestCase("Guardar", SaveAs, """{"name":"Guardar como"}""", TestName = "ACandidatesObjectThatIsNoListLeavesTheCascade")]
    public async Task CandidatesWithoutTheIndexsNameLeaveTheCascade(string label, string name, string candidates)
    {
        var (adapter, worker, locator) = Build(Tree(candidates), Look((2, "Inicio"), (Index, name)));

        ExternalCapabilityReceipt receipt = await Click(adapter, label, Index, Window);

        AssertCascaded(receipt, worker, locator);
    }

    [Test]
    public async Task ATreeAnswerWithNoCandidatesLeavesTheCascade()
    {
        var (adapter, worker, locator) = Build(NotFound, Look((2, "Inicio"), (Index, SaveAs)));

        ExternalCapabilityReceipt receipt = await Click(adapter, "Guardar", Index, Window);

        AssertCascaded(receipt, worker, locator);
    }

    [Test]
    public async Task AnIndexTheLookDoesNotHaveLeavesTheCascade()
    {
        var (adapter, worker, locator) = Build(Tree("""["Guardar como"]"""), Look((2, "Inicio"), (Index, SaveAs)));

        ExternalCapabilityReceipt receipt = await Click(adapter, "Guardar", 99, Window);

        AssertCascaded(receipt, worker, locator);
    }

    [Test]
    public async Task AnIndexOfTheLookOfAnotherWindowLeavesTheCascade()
    {
        var (adapter, worker, locator) = Build(Tree("""["Guardar como"]"""), Look((2, "Inicio"), (Index, SaveAs)));

        ExternalCapabilityReceipt receipt = await Click(adapter, "Guardar", Index, 9999);

        AssertCascaded(receipt, worker, locator);
    }

    [Test]
    public async Task AClickWithoutIndexLeavesTheCascadeThoughTheLookHasTheCandidate()
    {
        var (adapter, worker, locator) = Build(Tree("""["Guardar como"]"""), Look((2, "Inicio"), (Index, SaveAs)));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", JsonSerializer.SerializeToElement(new { label = "Guardar", window = (long)Window }),
            CancellationToken.None);

        AssertCascaded(receipt, worker, locator);
    }

    [Test]
    public async Task TheWholeNameWithItsIndexPressesThatControlByIdentity()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"" + SaveAs + "\"," +
            "\"controlIdentity\":\"" + Id(Index) + "\",\"absentOrDisabled\":false,\"selected\":true}");
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);
        var locator = new CountingLocator();
        var adapter = new WindowsVisibleControlAdapter(worker, locator, null, capture: Capture);
        RememberView(adapter, Look((2, "Inicio"), (Index, SaveAs)));

        ExternalCapabilityReceipt receipt = await Click(adapter, "GUARDAR  como", Index, Window);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(Sent(worker, Id(Index)), Is.True, "not pressed by the index's identity");
            Assert.That(locator.Calls, Is.Zero, "a later locator ran");
        });
    }

    private static void AssertEnded(
        ExternalCapabilityReceipt receipt, ComputerUsePerceptionTests.ScriptedUiaWorker worker, CountingLocator locator)
    {
        Assert.That(receipt.ErrorCode, Is.EqualTo(NotFoundError));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.EffectObserved, Is.False, "an effect was claimed");
            Assert.That(receipt.Verified, Is.False);
            Assert.That(locator.Calls, Is.Zero, "a later locator ran");
            Assert.That(Sent(worker, Id(Index)), Is.False, "the index's control was pressed");
            Assert.That(receipt.Result?.TryGetProperty("next", out _), Is.False, "this receipt says no next");
        });
    }

    private static void AssertCascaded(
        ExternalCapabilityReceipt receipt, ComputerUsePerceptionTests.ScriptedUiaWorker worker, CountingLocator locator)
    {
        Assert.That(receipt.ErrorCode, Is.Null, "the label did not reach the later locator");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, "the label was pressed by its cascade");
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            Assert.That(locator.Calls, Is.GreaterThan(0), "the later locator did not run");
            Assert.That(Sent(worker, Id(Index)), Is.False, "the index's control was pressed");
        });
    }

    private static string Tree(string candidates)
    {
        using JsonDocument document = JsonDocument.Parse(candidates);
        int count = document.RootElement.ValueKind == JsonValueKind.Array ? document.RootElement.GetArrayLength() : 1;
        return NotFound[..^1] + ",\"candidates\":" + candidates + ",\"candidateCount\":" + count + "}";
    }

    private static (WindowsVisibleControlAdapter Adapter, ComputerUsePerceptionTests.ScriptedUiaWorker Worker, CountingLocator Locator)
        Build(string treeAnswer, IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> controls)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker([.. Enumerable.Repeat(treeAnswer, 200)]);
        var locator = new CountingLocator();
        var adapter = new WindowsVisibleControlAdapter(worker, locator, null, timing: VisibleClickTiming.Default with
        {
            SettledLabel = TimeSpan.FromMilliseconds(60),
            Interval = TimeSpan.FromMilliseconds(20),
        });
        RememberView(adapter, controls);
        return (adapter, worker, locator);
    }

    private static string Id(int index) => $"42.{1000 + index}";

    private static WindowsVisibleControlAdapter.ViewControl[] Look(params (int Index, string Name)[] controls) =>
        [.. controls.Select(static control => new WindowsVisibleControlAdapter.ViewControl
        {
            Index = control.Index, Id = Id(control.Index), Kind = "Hyperlink", Name = control.Name, State = "",
        })];

    private static async Task<ExternalCapabilityReceipt> Click(
        WindowsVisibleControlAdapter adapter, string label, int index, long window) =>
        await adapter.InvokeAsync(
            "input.visible.click", JsonSerializer.SerializeToElement(new { label, index, window }), CancellationToken.None);

    // Whether any command to the worker carries that text as a whole value: here, the identity it would press.
    private static bool Sent(ComputerUsePerceptionTests.ScriptedUiaWorker worker, string text) =>
        worker.Commands.Any(command =>
        {
            using JsonDocument document = JsonDocument.Parse(command);
            return Carries(document.RootElement, text);
        });

    private static bool Carries(JsonElement element, string text) => element.ValueKind switch
    {
        JsonValueKind.String => string.Equals(element.GetString()?.Trim(), text, StringComparison.Ordinal),
        JsonValueKind.Object => element.EnumerateObject().Any(property => Carries(property.Value, text)),
        JsonValueKind.Array => element.EnumerateArray().Any(item => Carries(item, text)),
        _ => false,
    };

    private static void RememberView(
        WindowsVisibleControlAdapter adapter, IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> controls)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [Window, controls], null)!;
        field.SetValue(adapter, view);
    }

    private sealed class CountingLocator : IVisibleControlLocator
    {
        public int Calls { get; private set; }

        public string Stage => "ocr";

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken)
        {
            Calls++;
            JsonElement result = JsonDocument.Parse(
                "{\"version\":1,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":" + JsonSerializer.Serialize(label) + "," +
                "\"controlIdentity\":\"ocr.1\",\"absentOrDisabled\":false,\"selected\":false," +
                "\"surfaceChanged\":true,\"cascadeStage\":\"ocr\",\"authority\":\"ocr_locate_click_postread\"}")
                .RootElement.Clone();
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(
                new ExternalCapabilityReceipt(operation, true, true, result, null));
        }
    }
}
