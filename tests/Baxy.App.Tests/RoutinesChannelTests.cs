using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Providers.Windows.Routines;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// RUT4 (documentacion/RUTINAS.md §6; RUT3's panel): what the App gives the view of the person's routines. The list as
/// the store keeps it, each step with the title the conversation's cards give that call and why it would not run
/// today; the rail's number is the active ones and is never an old one; the switch and Borrar go by baxy.routines and
/// answer with the routine as it was left, or the handler's cause; «Olvidar todo» takes the routines and their tasks.
/// baxy.routines is answered here by the test: no store of this PC and no scheduler is reached.
/// </summary>
[TestFixture]
public sealed class RoutinesChannelTests
{
    private const string Two = """
        {"count":3,"routines":[
          {"id":"r-0a1b2c","name":"audífonos","trigger":{"phrase":"audífonos"},"active":true,
           "steps":[{"op":"audio.device.set","arguments":{"device":"Nimbo"}},{"say":"listo"}]},
          {"id":"r-0a1b2d","name":"10:00","trigger":{"at":"10:00","repeat":"daily"},"active":true,
           "steps":[{"say":"Buen día."}]},
          {"id":"r-0a1b2e","name":"vieja","trigger":{"phrase":"vieja"},"active":false,
           "steps":[{"op":"routine.retired.long.ago","arguments":{}}]}]}
        """;

    [Test]
    public async Task TheListNamesEachStepAsTheConversationDoesAndTheRailCountsTheActiveOnes()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            view.Channel.RunRoutines = (_, _) => Task.FromResult<OperationResponse?>(Completed(Two));

            (int status, JsonObject body) = await view.SendAsync("GET", "/routines");
            (_, JsonObject surfaces) = await view.SendAsync("GET", "/surfaces");

            JsonArray routines = body["routines"]!.AsArray();
            Assert.Multiple(() =>
            {
                Assert.That(status, Is.EqualTo(200));
                Assert.That((int?)body["count"], Is.EqualTo(3));
                Assert.That((string?)routines[0]!["steps"]![0]!["title"],
                    Is.EqualTo(FieldStepProjection.Label("audio.device.set", new JsonObject { ["device"] = "Nimbo" }, english: false)));
                Assert.That((string?)routines[0]!["steps"]![0]!["title"], Does.Contain("Nimbo"));
                Assert.That(routines[0]!["steps"]![0]!["blocked"], Is.Null, "Completo, the profile a new data root has, shows it");
                Assert.That(routines[0]!["steps"]![1]!.AsObject().ContainsKey("title"), Is.False, "a text to say is its own words");
                Assert.That((string?)routines[2]!["steps"]![0]!["blocked"], Is.EqualTo("unknown_operation"));
                Assert.That((string?)routines[1]!["trigger"]!["at"], Is.EqualTo("10:00"));
                Assert.That((int?)surfaces["routines"], Is.EqualTo(2), "the active ones");
                Assert.That(view.Sink.Events.Any(static e => (string?)e["type"] == "surfaces" && (int?)e["routines"] == 2), Is.True);
            });
        }
    }

    // A step whose tool the profile keeps off is marked with the profile's own refusal, the one that call would get.
    // RUT6: pausing and resuming (media.control) is Esencial's now; playing music by name is not.
    [Test]
    public async Task AStepOffInTheToolProfileIsMarkedAsThatCallWouldBeRefused()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            Assert.That(viewModel.ToolProfileState.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
            view.Channel.RunRoutines = (_, _) => Task.FromResult<OperationResponse?>(Completed("""
                {"count":1,"routines":[{"id":"r-0a1b2c","name":"jazz","trigger":{"phrase":"jazz"},"active":true,
                  "steps":[{"op":"media.play.query","arguments":{"query":"jazz"}},{"op":"audio.volume","arguments":{"level":20}}]}]}
                """));

            (_, JsonObject body) = await view.SendAsync("GET", "/routines");

            JsonArray steps = body["routines"]![0]!["steps"]!.AsArray();
            Assert.Multiple(() =>
            {
                Assert.That((string?)steps[0]!["blocked"], Is.EqualTo(ToolProfile.OffCode));
                Assert.That((string?)steps[0]!["title"], Is.Not.Empty);
                Assert.That(steps[1]!["blocked"], Is.Null);
            });
        }
    }

    [Test]
    public async Task TheSwitchAndBorrarGoByTheRoutinesNameAndAnswerWithWhatTheStoreLeft()
    {
        var sent = new List<string>();
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            view.Channel.RunRoutines = (arguments, _) =>
            {
                sent.Add((string?)arguments["action"] + " " + (string?)arguments["name"]);
                return Task.FromResult<OperationResponse?>((string?)arguments["action"] switch
                {
                    "list" => Completed(Two),
                    "disable" => Completed("""{"routine":{"id":"r-0a1b2c","name":"audífonos","trigger":{"phrase":"audífonos"},"active":false,"steps":[{"say":"listo"}]}}"""),
                    "enable" => Refused("routine_duplicate_phrase"),
                    "delete" => Completed("""{"deleted":{"id":"r-0a1b2d","name":"10:00","trigger":{"at":"10:00","repeat":"daily"},"active":true,"steps":[{"say":"Buen día."}]}}"""),
                    _ => null,
                });
            };

            (int offStatus, JsonObject off) = await view.SendAsync("PUT", "/routines/r-0a1b2c", new JsonObject { ["action"] = "disable" });
            (int clashStatus, JsonObject clash) = await view.SendAsync("PUT", "/routines/r-0a1b2e", new JsonObject { ["action"] = "enable" });
            (int goneStatus, JsonObject gone) = await view.SendAsync("DELETE", "/routines/r-0a1b2d");
            (int missingStatus, JsonObject missing) = await view.SendAsync("DELETE", "/routines/r-ffffff");
            (int badStatus, _) = await view.SendAsync("PUT", "/routines/r-0a1b2c", new JsonObject { ["action"] = "run" });
            (int badIdStatus, _) = await view.SendAsync("DELETE", "/routines/../memory");

            Assert.Multiple(() =>
            {
                Assert.That((offStatus, (string?)off["id"], (bool?)off["active"]), Is.EqualTo((200, "r-0a1b2c", false)));
                Assert.That((clashStatus, (string?)clash["error"]), Is.EqualTo((409, "duplicate_phrase")));
                Assert.That((goneStatus, (string?)gone["id"]), Is.EqualTo((200, "r-0a1b2d")));
                Assert.That((missingStatus, (string?)missing["error"]), Is.EqualTo((404, "not_found")));
                Assert.That(badStatus, Is.EqualTo(400));
                Assert.That(badIdStatus, Is.EqualTo(400));
                Assert.That(sent.Where(static call => !call.StartsWith("list", StringComparison.Ordinal)),
                    Is.EqualTo(new[] { "disable audífonos", "enable vieja", "delete 10:00" }));
            });
        }
    }

    // RUT3: a number that may be old is not shown. A routine made or deleted by chat drops it and it is read again, with
    // no need for the panel to be opened; a list that cannot be read leaves no number.
    [Test]
    public async Task ARoutineChangedByChatIsCountedAgainAndAListThatCannotBeReadLeavesNoNumber()
    {
        string listed = Two;
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            view.Channel.RunRoutines = (_, _) => Task.FromResult(listed.Length == 0 ? null : (OperationResponse?)Completed(listed));
            (_, JsonObject first) = await view.SendAsync("GET", "/surfaces");

            listed = """{"count":0,"routines":[]}""";
            const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
            object loop = typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
            var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
            host.StepCompleted!(new NativeTurnStep("baxy.routines", new JsonObject { ["action"] = "delete", ["name"] = "x" },
                OperationStatuses.Completed, true, null, 12, "{}", "c1", Sent: true));
            (_, JsonObject second) = await view.SendAsync("GET", "/surfaces");

            listed = string.Empty;
            (int status, _) = await view.SendAsync("GET", "/routines");
            (_, JsonObject third) = await view.SendAsync("GET", "/surfaces");

            Assert.Multiple(() =>
            {
                Assert.That((int?)first["routines"], Is.EqualTo(2));
                Assert.That((int?)second["routines"], Is.EqualTo(0));
                Assert.That(view.Sink.Events.Any(static e => (string?)e["type"] == "surfaces" && e["routines"] is JsonValue n
                    && n.GetValue<int>() == 0), Is.True, "published without the view asking");
                Assert.That(status, Is.EqualTo(503));
                Assert.That(third["routines"], Is.Null);
            });
        }
    }

    // «Olvidar todo»: the routines go, and before them the tasks of the ones at a time; a task that stays keeps them all
    // (one gone from the list that still spoke at its time would be a lie).
    [Test]
    public void ForgettingEverythingTakesTheRoutinesAndTheTasksOfTheOnesAtATime()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-rut4-forget-" + Guid.NewGuid().ToString("N"));
        try
        {
            var store = new LocalRoutineStore(Path.Combine(root, LocalRoutineStore.FolderName));
            JsonObject[] routines =
            [
                (JsonObject)JsonNode.Parse("""{"id":"r-0a1b2c","name":"audífonos","trigger":{"phrase":"audífonos"},"active":true,"steps":[{"say":"a"}]}""")!,
                (JsonObject)JsonNode.Parse("""{"id":"r-0a1b2d","name":"10:00","trigger":{"at":"10:00","repeat":"daily"},"active":true,"steps":[{"say":"b"}]}""")!,
            ];
            store.Write(routines);
            var asked = new List<string>();

            bool kept = FieldProductChannel.ForgetStoredRoutines(root, ids => { asked.AddRange(ids); return false; }, static () => true);
            int afterAFailure = store.Read().Count;
            bool forgotten = FieldProductChannel.ForgetStoredRoutines(root, static _ => true, static () => true);

            Assert.Multiple(() =>
            {
                Assert.That(kept, Is.False);
                Assert.That(afterAFailure, Is.EqualTo(2));
                Assert.That(asked, Is.EqualTo(new[] { "r-0a1b2d" }), "only the one at a time has a task");
                Assert.That(forgotten, Is.True);
                Assert.That(store.Read(), Is.Empty);
                Assert.That(Directory.GetFiles(store.Folder), Is.Empty);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // REV11 B-2: a routine said «once» that left the list before it spoke (the PC asleep at its time) keeps its task, and
    // «Olvidar todo» takes every BAXY-Say task this data root recorded, not only those of the routines still listed.
    [Test]
    public void ForgettingEverythingTakesEveryRoutineTaskOfTheDataRootAlsoOfOnesNoLongerListed()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-rev11-forget-" + Guid.NewGuid().ToString("N"));
        try
        {
            var store = new LocalRoutineStore(Path.Combine(root, LocalRoutineStore.FolderName));
            store.Write([(JsonObject)JsonNode.Parse("""{"id":"r-0a1b2c","name":"audífonos","trigger":{"phrase":"audífonos"},"active":true,"order":"cambia a los audífonos","steps":[]}""")!]);
            int swept = 0;

            bool kept = FieldProductChannel.ForgetStoredRoutines(root, static _ => true, () => { swept++; return false; });
            int afterAFailure = store.Read().Count;
            bool forgotten = FieldProductChannel.ForgetStoredRoutines(root, static _ => true, () => { swept++; return true; });

            Assert.Multiple(() =>
            {
                Assert.That(swept, Is.EqualTo(2), "every task of the data root is swept, with no timed routine listed");
                Assert.That(kept, Is.False);
                Assert.That(afterAFailure, Is.EqualTo(1), "a task that stayed keeps the routines");
                Assert.That(forgotten, Is.True);
                Assert.That(store.Read(), Is.Empty);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // RUT9 (REV9 H5): a routines file that cannot be read is forgotten too, once every task of this data root's routines
    // is gone (with no list, they are all of them); a task that stays keeps it.
    [Test]
    public void ForgettingEverythingTakesADamagedRoutinesFileOnceItsTasksAreGone()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-rut9-forget-" + Guid.NewGuid().ToString("N"));
        try
        {
            string folder = Path.Combine(root, LocalRoutineStore.FolderName);
            Directory.CreateDirectory(folder);
            string file = Path.Combine(folder, "routines.v1.json");
            File.WriteAllText(file, "{\"routines\":[{\"id\":\"r-000001\",\"order\":\"apaga el PC\"");   // cut halfway
            int asked = 0;

            bool kept = FieldProductChannel.ForgetStoredRoutines(root, static _ => true, () => { asked++; return false; });
            bool keptFile = File.Exists(file);
            bool forgotten = FieldProductChannel.ForgetStoredRoutines(root, static _ => true, () => { asked++; return true; });

            Assert.Multiple(() =>
            {
                Assert.That(kept, Is.False);
                Assert.That(keptFile, Is.True);
                Assert.That(asked, Is.EqualTo(2));
                Assert.That(forgotten, Is.True);
                Assert.That(Directory.GetFiles(folder), Is.Empty);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // The conversation's line of a routine said at its time: its time and its text, and the truth about the voice.
    [Test]
    public void TheLineOfARoutineSaidSaysItsTimeItsTextAndWhetherTheVoiceSaidIt()
    {
        var say = new RingNow("BAXY-Say-" + new string('a', 32), "aaaaaaaa", "say", "Buen día.", "09:05",
            DateTimeOffset.UnixEpoch, "Buen día.", "said");

        Assert.Multiple(() =>
        {
            Assert.That(FieldProductChannel.RoutineSaidLine(say, spoken: true, english: false),
                Is.EqualTo("Rutina de las 9:05 · dije: «Buen día.»"));
            Assert.That(FieldProductChannel.RoutineSaidLine(say, spoken: false, english: false),
                Does.Contain("voz apagada").And.Contain("«Buen día.»").And.Not.Contain("dije"));
            Assert.That(FieldProductChannel.RoutineSaidLine(say, spoken: true, english: true),
                Is.EqualTo("Routine, 9:05 · I said: “Buen día.”"));
        });
    }

    private static OperationResponse Completed(string result) => new(
        ProtocolTypes.OperationResponse, "r", "m", "i", OperationStatuses.Completed, "done", true, false,
        JsonDocument.Parse(result).RootElement.Clone(), null);

    private static OperationResponse Refused(string code) => new(
        ProtocolTypes.OperationResponse, "r", "m", "i", OperationStatuses.Failed, "refused", false, false, null, code);
}
