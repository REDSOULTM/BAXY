using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Encargo 96: a click that changes a setting of Windows waits for the person's yes in normal mode, always, though their
/// own words asked for it: a question too many is the safe side, and no list of words of intention spares it. The turn
/// goes through the real loop to a small engine of this test, which challenges a call without a token and runs one with it.
/// </summary>
[TestFixture]
public sealed class SystemChangeYesTests
{
    private const string Token = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";

    // An engine on the real protocol: stdin requests, stdout responses, each request written down as it came.
    private const string Engine = """
        param([string]$Requests)
        while($null -ne ($line=[Console]::In.ReadLine())){
          Add-Content -LiteralPath $Requests -Value $line -Encoding UTF8
          $call=$line | ConvertFrom-Json
          $answer=@{ type='operation.response'; requestId=$call.requestId; missionId=$call.missionId; invocationId=$call.invocationId; verified=$false; replayed=$false; message='engine of the test' }
          if($call.confirmationToken){
            $answer.status='completed'; $answer.verified=$true; $answer.errorCode=$null
            $change=@{ control='Encender ahora'; before=@('Encender ahora'); after=@('Apagar ahora'); changed=$true }
            $answer.result=@{ systemChange=$change }
            $answer.message=(@{ status='completed'; verification='verified'; observed=@{ systemChange=$change } } | ConvertTo-Json -Compress -Depth 8)
          } else {
            $answer.status='pending'; $answer.errorCode='confirmation_required'
            $answer.result=@{ version=VERSION; token='TOKEN'; expiresAtUtc=[DateTime]::UtcNow.AddMinutes(1).ToString('o'); reconciliationRequired=$false
              facts=@{ systemChange=@{ control='Encender ahora'; change='action'; setting='Panel de prueba' } } }
          }
          [Console]::Out.WriteLine(($answer | ConvertTo-Json -Compress -Depth 8))
          [Console]::Out.Flush()
        }
        """;

    private static async Task<CoreProcessClient> StartEngineAsync(string folder, string requests)
    {
        string script = Path.Combine(folder, "engine.ps1");
        await File.WriteAllTextAsync(script, Engine
            .Replace("VERSION", ConfirmationChallengeContract.CurrentVersion.ToString(System.Globalization.CultureInfo.InvariantCulture), StringComparison.Ordinal)
            .Replace("TOKEN", Token, StringComparison.Ordinal));
        string shell = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0", "powershell.exe");
        LocalJsonlSidecarProcess sidecar = LocalJsonlSidecarProcess.Start(new LocalJsonlSidecarDefinition(
            "core", shell, folder, ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script, "-Requests", requests],
            drainStandardError: false));
        var core = new CoreProcessClient();
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        var pump = new CancellationTokenSource();
        typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_started", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(core, sidecar.Process);
        typeof(CoreProcessClient).GetField("_sidecar", Private)!.SetValue(core, sidecar);
        typeof(CoreProcessClient).GetField("_pumpCancellation", Private)!.SetValue(core, pump);
        typeof(CoreProcessClient).GetField("_stdoutPump", Private)!.SetValue(core, typeof(CoreProcessClient)
            .GetMethod("PumpStandardOutputAsync", Private)!.Invoke(core, [sidecar.Process, pump.Token]));
        return core;
    }

    private static JsonObject Click() => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject
            {
                ["type"] = "turn.result",
                ["kind"] = "action",
                ["operation"] = "input.visible.click",
                ["arguments"] = new JsonObject { ["label"] = "Encender ahora" },
            },
            ["turn.continue"] = new JsonObject
            {
                ["type"] = "turn.result", ["kind"] = "clarify", ["question"] = "¿Lo enciendo?",
            },
        },
    };

    private static string[] Requests(string file) => File.Exists(file) ? File.ReadAllLines(file) : [];

    // The words ask for this very change, in the forms the removed list spared: it asks all the same, nothing runs before
    // the yes, the yes runs that same call, and the receipt says what changed.
    [TestCase("enciende el panel de prueba")]
    [TestCase("abre configuración y enciéndeme el panel de prueba ahí mismo, porfa")]
    [TestCase("pulsa encender ahora")]
    public async Task ASettingOfWindowsWaitsForTheYesThoughTheWordsAskForIt(string words)
    {
        using var fake = new FakeMind();
        fake.Script(Click());
        string requests = Path.Combine(fake.Folder, "engine-requests.jsonl");
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        await using CoreProcessClient core = await StartEngineAsync(fake.Folder, requests);
        var steps = new List<NativeTurnStep>();
        var asked = new List<NativeTurnConfirmation>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            ConfirmationAsked = asked.Add,
        });

        await loop.RunAsync(words, Stopwatch.GetTimestamp(), CancellationToken.None);

        string[] sentFirst = Requests(requests);
        Assert.Multiple(() =>
        {
            Assert.That(loop.HasPendingConfirmation, Is.True, "their words are not the yes");
            Assert.That(asked, Has.Count.EqualTo(1));
            Assert.That(asked[0].Cause, Is.EqualTo(PendingOperationConfirmation.SystemChangeCause));
            Assert.That(sentFirst, Has.Length.EqualTo(1), "nothing went with the token");
            Assert.That(sentFirst[0], Does.Not.Contain("confirmationToken"));
            Assert.That(steps[^1].Status, Is.EqualTo("pending"));
            Assert.That(JsonNode.Parse(steps[^1].Observation)?["systemChange"]?["control"]?.GetValue<string>(), Is.EqualTo("Encender ahora"),
                "the model reads what it would change");
        });

        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.confirm"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "confirmation.answer",
                    ["arguments"] = new JsonObject { ["answer"] = "yes" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "Listo.",
                },
            },
        });
        await loop.AnswerConfirmationAsync(true, "Sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        string[] sent = Requests(requests);
        NativeTurnStep ran = steps[^1];
        Assert.Multiple(() =>
        {
            Assert.That(sent, Has.Length.EqualTo(2));
            Assert.That(JsonNode.Parse(sent[1])?["confirmationToken"]?.GetValue<string>(), Is.EqualTo(Token));
            Assert.That(JsonNode.Parse(sent[1])?["invocationId"]?.GetValue<string>(),
                Is.EqualTo(JsonNode.Parse(sent[0])?["invocationId"]?.GetValue<string>()), "the same call, not a new one");
            Assert.That((ran.Operation, ran.Status, ran.Verified), Is.EqualTo(("input.visible.click", "completed", true)));
            Assert.That(ran.Observation, Does.Contain("Apagar ahora"), "the receipt says what it changed");
            Assert.That(loop.HasPendingConfirmation, Is.False);
        });
    }

    // The challenge carries the kernel's facts; anything else beside its four fields is still refused.
    [Test]
    public void TheChallengeKeepsItsFactsAndRefusesAnythingElse()
    {
        static OperationResponse Answered(PreparedOperation prepared, string extra) => new(
            ProtocolTypes.OperationResponse, "r", prepared.MissionId, prepared.InvocationId, OperationStatuses.Pending,
            "asks", false, false,
            JsonDocument.Parse("{\"version\":" + ConfirmationChallengeContract.CurrentVersion + ",\"token\":\""
                + new string('A', 43) + "\",\"expiresAtUtc\":\""
                + DateTimeOffset.UtcNow.AddMinutes(1).ToString("O", System.Globalization.CultureInfo.InvariantCulture)
                + "\",\"reconciliationRequired\":false" + extra + "}").RootElement.Clone(),
            ConfirmationChallengeContract.RequiredErrorCode);

        PreparedOperation prepared = PreparedOperation.Create("input.visible.click", new JsonObject { ["label"] = "Uno" });
        bool withFacts = PendingOperationConfirmation.TryCreate(
            Answered(prepared, ",\"facts\":{\"systemChange\":{\"control\":\"Uno\"}}"), prepared, TimeProvider.System,
            out PendingOperationConfirmation? challenge);
        bool withOther = PendingOperationConfirmation.TryCreate(
            Answered(prepared, ",\"other\":1"), prepared, TimeProvider.System, out _);

        Assert.Multiple(() =>
        {
            Assert.That(withFacts, Is.True);
            Assert.That(challenge!.Facts!.Value.GetProperty("systemChange").GetProperty("control").GetString(), Is.EqualTo("Uno"));
            Assert.That(withOther, Is.False);
        });
    }
}
