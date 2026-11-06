using System.Reflection;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo P1 (F55): the model named a look's control by its index and only the first words of its name; the tree answered
/// «not found» with the names holding those words, that control among them, and a later stage pressed look-alike words
/// elsewhere in the window, inside a page's dialog. With the index's control among the candidates the cascade ends there:
/// nothing is pressed and the model gets the names. Every effect goes to fakes: no window is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseIndexLabelPartTests
{
    private const nint Window = 4660;
    private const string CardName = "Curso 12 | Dibujo técnico Sección B Segundo semestre";
    private const string TasksName = "Tareas - Curso 12 | Dibujo técnico";

    private static readonly VisibleClickTiming Quick = VisibleClickTiming.Default with
    {
        SettledLabel = TimeSpan.FromMilliseconds(60),
        Interval = TimeSpan.FromMilliseconds(20),
    };

    [Test]
    public async Task TheIndexsControlAmongTheCandidatesEndsTheCascadeWithItsNameFirst()
    {
        var ocr = new CountingLocator();
        var vision = new CountingLocator();
        var adapter = new WindowsVisibleControlAdapter(Answering(NotFoundWith(TasksName, CardName)), ocr, vision, timing: Quick);
        RememberView(adapter, Control(53, "1.53", CardName), Control(55, "1.55", TasksName));

        ExternalCapabilityReceipt receipt = await Click(adapter, "Curso 12 | Dibujo técnico", 53);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(ocr.Calls, Is.Zero, "OCR looked for the words elsewhere");
            Assert.That(vision.Calls, Is.Zero, "vision looked for the words elsewhere");
            Assert.That(
                receipt.Result?.GetProperty("candidates").EnumerateArray().Select(static name => name.GetString()),
                Is.EqualTo(new[] { CardName, TasksName }));
            // Measured: a next naming the index's control makes the model press it whatever the person asked for.
            Assert.That(receipt.Result?.TryGetProperty("next", out _), Is.False);
        });
    }

    // A label still being drawn keeps its wait: the tree's later look finds it, with no other stage in between.
    [Test]
    public async Task TheWaitForALabelStillBeingDrawnStays()
    {
        var ocr = new CountingLocator();
        var vision = new CountingLocator();
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            NotFoundWith(CardName),
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Curso 12\"," +
            "\"controlIdentity\":\"1.9\",\"absentOrDisabled\":false,\"selected\":true}");
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, vision, capture: Capture, timing: Quick);
        RememberView(adapter, Control(53, "1.53", CardName));

        ExternalCapabilityReceipt receipt = await Click(adapter, "Curso 12", 53);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(ocr.Calls + vision.Calls, Is.Zero);
        });
    }

    // Contracase: an index the candidates do not list says nothing about them: the label goes on looking.
    [Test]
    public async Task AnIndexOutsideTheCandidatesLeavesTheLabelToItsCascade()
    {
        var locator = new CountingLocator();
        var adapter = new WindowsVisibleControlAdapter(Answering(NotFoundWith(CardName)), locator, null, timing: Quick);
        RememberView(adapter, Control(13, "1.13", "Captura de pantalla"), Control(53, "1.53", CardName));

        await Click(adapter, "Curso 12", 13);

        Assert.That(locator.Calls, Is.EqualTo(1));
    }

    // Contracase: an index the look did not have, as in a look of only written lines.
    [Test]
    public async Task AnIndexTheLookDidNotHaveLeavesTheLabelToItsCascade()
    {
        var locator = new CountingLocator();
        var adapter = new WindowsVisibleControlAdapter(Answering(NotFoundWith(CardName)), locator, null, timing: Quick);
        RememberView(adapter, Control(53, "1.53", CardName));

        await Click(adapter, "Curso 12", 10);

        Assert.That(locator.Calls, Is.EqualTo(1));
    }

    // Contracase: with no candidates (a kind that holds no title, words the name does not have) nothing changes.
    [Test]
    public async Task NoCandidatesLeaveTheLabelToItsCascade()
    {
        var locator = new CountingLocator();
        var adapter = new WindowsVisibleControlAdapter(Answering(NotFoundWith()), locator, null, timing: Quick);
        RememberView(adapter, Control(5, "1.5", "Guardar como"));

        await Click(adapter, "Guardar", 5);

        Assert.That(locator.Calls, Is.EqualTo(1));
    }

    // Contracase: a label alone keeps its cascade: a drawn button may share its words with the title of a tab.
    [Test]
    public async Task ALabelWithoutAnIndexLeavesTheCandidatesToItsCascade()
    {
        var locator = new CountingLocator();
        var adapter = new WindowsVisibleControlAdapter(Answering(NotFoundWith("Tienda - Sitio de prueba")), locator, null, timing: Quick);
        RememberView(adapter, Control(3, "1.3", "Tienda - Sitio de prueba"));

        await adapter.InvokeAsync(
            "input.visible.click",
            JsonSerializer.SerializeToElement(new { label = "Tienda", window = (long)Window }),
            CancellationToken.None);

        Assert.That(locator.Calls, Is.EqualTo(1));
    }

    // Contracase: the whole name with its index is pressed by its identity, as before.
    [Test]
    public async Task TheWholeNameIsPressedByTheIndexsIdentity()
    {
        var locator = new CountingLocator();
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"" + CardName + "\"," +
            "\"controlIdentity\":\"1.53\",\"absentOrDisabled\":false,\"selected\":true}");
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);
        var adapter = new WindowsVisibleControlAdapter(worker, locator, null, capture: Capture);
        RememberView(adapter, Control(53, "1.53", CardName));

        ExternalCapabilityReceipt receipt = await Click(adapter, CardName, 53);

        Assert.That(receipt.ErrorCode, Is.Null);
        Assert.That(locator.Calls, Is.Zero);
    }

    private static ComputerUsePerceptionTests.ScriptedUiaWorker Answering(string answer) =>
        new([.. Enumerable.Repeat(answer, 200)]);

    private static string NotFoundWith(params string[] candidates) =>
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"," +
        "\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false" +
        (candidates.Length == 0
            ? string.Empty
            : ",\"candidates\":" + JsonSerializer.Serialize(candidates) + ",\"candidateCount\":" + candidates.Length) +
        "}";

    private static WindowsVisibleControlAdapter.ViewControl Control(int index, string id, string name) =>
        new() { Index = index, Id = id, Kind = "Hyperlink", Name = name, State = "" };

    private static ValueTask<ExternalCapabilityReceipt> Click(WindowsVisibleControlAdapter adapter, string label, int index) =>
        adapter.InvokeAsync(
            "input.visible.click",
            JsonSerializer.SerializeToElement(new { label, index, window = (long)Window }),
            CancellationToken.None);

    private static void RememberView(
        WindowsVisibleControlAdapter adapter, params WindowsVisibleControlAdapter.ViewControl[] controls)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [Window, (IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>)controls], null)!;
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
