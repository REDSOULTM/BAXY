using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Live 2026-10-07 (cu-universal v2 bench, cu-r8): when the mind returned no final for a computer-use mission, the App's
/// floor said «Lo hice en la aplicación «Reloj»; hay 2: «Reloj mundial».» or «No pude hacerlo en la aplicación
/// «Configuración».». It now says what the mind's floor says, from the same data (operation_floor.v1.json
/// «computerUse»): the place reached, or what was not reached and the typed cause. The fixture
/// (tests/data/cu_floor_twins.json) is written by the mind and read back by tests/test_cu_r8_voz_final.py too.
/// </summary>
[TestFixture]
public sealed class ComputerUseFloorTests
{
    private static IEnumerable<TestCaseData> TwinCases()
    {
        var fixture = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            FindRepositoryRoot(), "tests", "data", "cu_floor_twins.json")))!;
        foreach (JsonNode? row in (JsonArray)fixture["cases"]!)
        {
            string id = (string)row!["id"]!;
            yield return new TestCaseData(row["situation"]!.ToJsonString(), false, (string)row["es"]!)
                .SetName($"ComputerUseTwin({id},es)");
            yield return new TestCaseData(row["situation"]!.ToJsonString(), true, (string)row["en"]!)
                .SetName($"ComputerUseTwin({id},en)");
        }
    }

    // Revisión de r30. «floorOnly» (H1, H2): what the two floors say of a mission whose final is the model's (an arrival
    // by resemblance, a pick found chosen with no act): the name the term read is not told; whether the App would
    // publish that respaldo is not what these rows hold. «appAndMindDiffer» (H4): where the mind tells more than the
    // App on purpose (a colour's shade, data the App does not carry), both sentences on one situation. The mind's side
    // of both is read by tests/test_cu_r30_final_como_lo_escribe_la_ventana.py.
    private static IEnumerable<TestCaseData> FloorCases()
    {
        var fixture = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            FindRepositoryRoot(), "tests", "data", "cu_floor_twins.json")))!;
        foreach (string key in new[] { "floorOnly", "appAndMindDiffer" })
        {
            foreach (JsonNode? row in (JsonArray)fixture[key]!)
            {
                string id = (string)row!["id"]!;
                JsonNode said = row["app"] ?? row;
                yield return new TestCaseData(row["situation"]!.ToJsonString(), false, (string)said["es"]!)
                    .SetName($"ComputerUseFloor({key},{id},es)");
                yield return new TestCaseData(row["situation"]!.ToJsonString(), true, (string)said["en"]!)
                    .SetName($"ComputerUseFloor({key},{id},en)");
            }
        }
    }

    [TestCaseSource(nameof(FloorCases))]
    public void TheAppsFloorSaysWhatTheFixtureHoldsForIt(string situation, bool english, string expected) =>
        Assert.That(OperationFloor.Final((JsonObject)JsonNode.Parse(situation)!, english), Is.EqualTo(expected));

    [TestCaseSource(nameof(TwinCases))]
    public void TheAppSaysWhatTheMindSays(string situation, bool english, string expected)
    {
        var source = (JsonObject)JsonNode.Parse(situation)!;
        Assert.That(OperationFloor.Final(source, english), Is.EqualTo(expected));

        // And it is what the App publishes when the mind answered nothing.
        bool done = source["verified"] is JsonValue verified && verified.GetValue<bool>()
            && source["succeeded"] is JsonValue succeeded && succeeded.GetValue<bool>();
        var draft = new UserMessageDraft(situation, done || (string?)source["cause"] == "mission_completed"
            ? "status" : "error", null);
        string request = english ? "in the clock go to world clock" : "en el reloj andá a reloj mundial";
        Assert.That(
            ModelMessageComposer.DeterministicFinal(draft, request, ModelMessageComposer.CreateFacts(draft), string.Empty),
            Is.EqualTo(expected),
            () => $"refused: {UserMessagePolicy.ModelResponseRejectionReason(expected, draft, request)}");
    }

    [Test]
    public void AMissionWithAQuestionLeavesTheAnswerToTheMind()
    {
        var source = (JsonObject)JsonNode.Parse(
            """{"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,"observed":{"goal":"ir a personalización; y responder: el modo es claro u oscuro","application":"Configuración","reached":true,"steps":[]}}""")!;
        Assert.That(OperationFloor.Final(source, english: false), Does.Not.StartWith("Listo, estoy en"));
    }

    // Regresiones r4 (live v2-c2): a chain that calculated and pasted ended on the editor, whose text glued the paste to
    // its own («lista: pan leche144144»); the calculation part carries what its own window showed when it was reached.
    [Test]
    public void TheCalculationOfAChainThatEndedElsewhereIsToldFromItsOwnWindow()
    {
        static JsonObject Chain(string numbers) => (JsonObject)JsonNode.Parse(
            """{"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,"observed":{"goal":"calcular 12*12; luego apretar ctrl c; luego apretar ctrl v","application":"Calculadora","reached":true,"steps":[{"step":1,"operation":"input.text.type","text":"12*12","ok":true},{"step":2,"operation":"input.key.press","key":"enter","ok":true},{"step":3,"operation":"input.key.press","key":"ctrl_c","ok":true},{"step":4,"operation":"input.key.press","key":"ctrl_v","ok":true}],"window":{"title":"*lista pan: Bloc de notas","process":"Notepad"},"screen":{"title":"*lista pan: Bloc de notas","values":[{"name":"Editor de texto","value":"lista: pan leche144144"}],"numbers":["Línea 2, Columna 12"]},"subgoals":[{"goal":"calcular 12*12","application":"Calculadora","reached":true"""
            + numbers + """},{"goal":"apretar ctrl c","application":"Calculadora","reached":true},{"goal":"apretar ctrl v","application":"Bloc de notas","reached":true}]}}""")!;
        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.Final(Chain(string.Empty), english: false), Does.Not.Contain("144"));
            Assert.That(OperationFloor.Final(Chain(""","numbers":["Se muestra 144","12 × 12= 144"]"""), english: false),
                Does.Contain("12 × 12 = 144"));
            Assert.That(OperationFloor.Final(Chain(""","numbers":["Se muestra 0","0 × 9= 0"]"""), english: false),
                Does.Not.Contain("144"), "its window showed another value");
        });
    }

    // Falsos éxitos v3 M1 (v3-17, turn 2): «Listo, lo hice en «Fotos»» with no step taken. The floor says «Listo» only
    // after a verified act besides opening the application.
    [Test]
    public void TheFloorNeverSaysDoneWithoutAVerifiedAct()
    {
        static JsonObject Reached(string steps) => (JsonObject)JsonNode.Parse(
            """{"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,"observed":{"goal":"recortar la imagen en proporcion cuadrada","application":"Fotos","reached":true,"satisfiedBy":"model_evidence","steps":"""
            + steps + "}}")!;
        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.Final(Reached("[]"), english: false), Does.Not.StartWith("Listo, lo hice en"));
            Assert.That(OperationFloor.Final(
                Reached("""[{"step":1,"operation":"app.open","appId":"Fotos","ok":true}]"""), english: false), Does.Not.StartWith("Listo, lo hice en"));
            // Ronda 22 (pasada r18 t3-c18): the model's own evidence is a weak proof; the act is counted, never told as done.
            Assert.That(OperationFloor.Final(
                Reached("""[{"step":1,"operation":"input.visible.click","label":"Recortar","ok":true,"changed":true}]"""), english: false),
                Is.EqualTo("Llevo un paso en «Fotos», pero la pantalla todavía no muestra que haya quedado hecho."));
            JsonObject proved = Reached("""[{"step":1,"operation":"input.visible.click","label":"Recortar","ok":true,"changed":true}]""");
            proved["observed"]!["satisfiedBy"] = "control:recortar:current";
            Assert.That(OperationFloor.Final(proved, english: false), Is.EqualTo("Listo, lo hice en «Fotos»."));
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
