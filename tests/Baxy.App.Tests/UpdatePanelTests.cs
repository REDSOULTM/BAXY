using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// actualizar-ordenes-app: Settings › General «Buscar actualizaciones» and the notice of a newer BAXY are the chat's own
/// baxy.update sent to the engine. Only the «Actualizar» button answers the install's challenge (the person's yes); a
/// check never does, and the notice appears only when there is something newer.
/// </summary>
[TestFixture]
public sealed class UpdatePanelTests
{
    [Test]
    public async Task ACheckKeepsWhatItFoundAndANewerVersionIsANotice()
    {
        List<(string Action, bool Pressed)> sent = [];
        var panel = new UpdatePanel((action, _, pressed, _) =>
        {
            sent.Add((action, pressed));
            return Task.FromResult<OperationResponse?>(Response("completed", """{"channel":"github","installed":"1.3.2","latest":"1.4.0","newer":true}"""));
        });

        JsonObject found = await panel.CheckAsync(CancellationToken.None);
        JsonObject? notice = UpdatePanel.NoticeOf(panel.Known);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)found["ok"], Is.True);
            Assert.That(sent, Is.EqualTo(new[] { ("check", false) }));
            Assert.That((string?)notice?["type"], Is.EqualTo("update"));
            Assert.That((string?)notice?["latest"], Is.EqualTo("1.4.0"));
        });
    }

    [Test]
    public async Task NothingNewerIsNoNoticeAndAFailureKeepsItsFacts()
    {
        var latest = new UpdatePanel((_, _, _, _) => Task.FromResult<OperationResponse?>(
            Response("completed", """{"channel":"github","installed":"1.4.0","latest":"1.4.0","newer":false}""")));
        var already = new UpdatePanel((_, _, _, _) => Task.FromResult<OperationResponse?>(
            Response("failed", """{"channel":"github","installed":"1.4.0","latest":"1.4.0","newer":false}""", "baxy_update_already_latest")));

        await latest.CheckAsync(CancellationToken.None);
        JsonObject install = await already.InstallAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(UpdatePanel.NoticeOf(latest.Known), Is.Null);
            Assert.That((string?)install["error"], Is.EqualTo("baxy_update_already_latest"));
            Assert.That((string?)install["latest"], Is.EqualTo("1.4.0"));
            Assert.That((bool?)install["ok"], Is.Not.True);
        });
    }

    // The button is the yes to the install; with no engine nothing is said done.
    [Test]
    public async Task OnlyTheInstallButtonAnswersAndWithNoEngineNothingIsDone()
    {
        List<(string Action, bool Pressed)> sent = [];
        var panel = new UpdatePanel((action, _, pressed, _) =>
        {
            sent.Add((action, pressed));
            return Task.FromResult<OperationResponse?>(null);
        });

        JsonObject install = await panel.InstallAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sent, Is.EqualTo(new[] { ("install", true) }));
            Assert.That((string?)install["error"], Is.EqualTo("engine_not_ready"));
            Assert.That(panel.Known, Is.Null);
        });
    }

    // INT19 (blind review): «Actualizar» in Settings asked GitHub and downloaded the installer with nothing in «Salidas a
    // internet», and a check GitHub answered with an error (a 403 of its rate limit, a 5xx) was not said either: the request
    // had gone out. Whatever reached GitHub is said; a store, a development copy or a channel with no repository is not.
    // Second review: an install the App stopped waiting for (the ~80 MB past its 10 minutes) had asked GitHub too; the channel
    // is the one the check before the button found.
    [Test]
    public async Task EveryCallThatReachedGitHubIsSaidAsGoingOnline()
    {
        static UpdatePanel Answering(string status, string result, string? error = null) => new((_, _, _, _) =>
            Task.FromResult<OperationResponse?>(Response(status, result, error)));

        JsonObject installed = await Answering("completed", """{"channel":"github","installed":"1.3.2","latest":"1.4.0","installerStarted":true}""")
            .InstallAsync(CancellationToken.None);
        JsonObject limited = await Answering("failed", """{"channel":"github","installed":"1.3.2"}""", "baxy_update_unreachable")
            .CheckAsync(CancellationToken.None);
        JsonObject found = await Answering("completed", """{"channel":"github","installed":"1.3.2","updatedBy":"github","newer":false}""")
            .CheckAsync(CancellationToken.None);
        JsonObject steam = await Answering("completed", """{"channel":"steam","installed":"1.3.2","opened":"steam_library"}""")
            .InstallAsync(CancellationToken.None);
        JsonObject noRepository = await Answering("failed", """{"channel":"github","installed":"1.3.2"}""", "baxy_update_source_unknown")
            .InstallAsync(CancellationToken.None);
        JsonObject development = await Answering("failed", """{"channel":"development","installed":"1.3.2"}""", "baxy_update_development_build")
            .CheckAsync(CancellationToken.None);

        var slow = new UpdatePanel((action, _, _, _) => action == "check"
            ? Task.FromResult<OperationResponse?>(Response("completed", """{"channel":"github","installed":"1.3.2","latest":"1.4.0","newer":true}"""))
            : throw new TimeoutException());
        JsonObject checkedFirst = await slow.CheckAsync(CancellationToken.None);
        JsonObject stoppedWaiting = await slow.InstallAsync(CancellationToken.None);
        var noEngine = new UpdatePanel((action, _, _, _) => action == "check"
            ? Task.FromResult<OperationResponse?>(Response("completed", """{"channel":"github","installed":"1.3.2","latest":"1.4.0","newer":true}"""))
            : Task.FromResult<OperationResponse?>(null));
        await noEngine.CheckAsync(CancellationToken.None);
        JsonObject notSent = await noEngine.InstallAsync(CancellationToken.None);
        var neverChecked = new UpdatePanel((_, _, _, _) => throw new TimeoutException());
        JsonObject unknown = await neverChecked.InstallAsync(CancellationToken.None);
        var panel = Answering("completed", "{}");

        Assert.Multiple(() =>
        {
            Assert.That(panel.WentOnline("install", installed), Does.Contain("github.com").And.Contain("instalador").Or.Contain("installer"));
            Assert.That(panel.WentOnline("check", limited), Does.Contain("api.github.com"));
            Assert.That(panel.WentOnline("check", found), Does.Contain("api.github.com").And.Not.Contain("instalador").And.Not.Contain("installer"));
            Assert.That(panel.WentOnline("install", steam), Is.Null);
            Assert.That(panel.WentOnline("install", noRepository), Is.Null);
            Assert.That(panel.WentOnline("check", development), Is.Null);
            Assert.That((string?)stoppedWaiting["error"], Is.EqualTo("update_outcome_unknown"));
            Assert.That(slow.WentOnline("install", stoppedWaiting), Does.Contain("github.com"), "an install the App stopped waiting for");
            Assert.That(noEngine.WentOnline("install", notSent), Is.Null, "with no engine nothing was asked");
            Assert.That(neverChecked.WentOnline("install", unknown), Is.Null, "no check said where it would go");
            Assert.That(slow.WentOnline("check", checkedFirst), Does.Contain("api.github.com"));
        });
    }

    // APP1 (UPD-f, review of the App 2026-11-09): the view gives a request 30 s (field-native-bridge.js) and the installer's
    // download takes longer on a slow line, so the view said «no pude» while the engine went on, started the installer and
    // BAXY closed; a second press sent a second install. The button's request answers at once with the install's state,
    // nothing is said done or failed while it runs, and a second press joins the install that is running.
    [Test]
    public async Task AnInstallThatTakesLongAnswersAtOnceWithItsStateAndASecondPressStartsNoOther()
    {
        var engine = new TaskCompletionSource<OperationResponse?>(TaskCreationOptions.RunContinuationsAsynchronously);
        List<string> sent = [];
        var panel = new UpdatePanel((action, _, _, _) =>
        {
            lock (sent)
            {
                sent.Add(action);
            }

            return engine.Task;
        });

        Task<JsonObject> pressed = panel.InstallAsync(CancellationToken.None);
        bool answered = await Task.WhenAny(pressed, Task.Delay(TimeSpan.FromSeconds(5))) == pressed;
        Task<JsonObject> pressedAgain = panel.InstallAsync(CancellationToken.None);
        bool answeredAgain = await Task.WhenAny(pressedAgain, Task.Delay(TimeSpan.FromSeconds(5))) == pressedAgain;
        int installs;
        lock (sent)
        {
            installs = sent.Count(static action => action == "install");
        }

        JsonObject? first = answered ? await pressed : null;
        engine.SetResult(Response("completed", """{"channel":"github","installed":"1.3.2","latest":"1.4.0","installerStarted":true}"""));
        await Task.WhenAll(pressed, pressedAgain);

        Assert.Multiple(() =>
        {
            Assert.That(answered, Is.True, "the button's request answers while the engine still downloads");
            Assert.That(answeredAgain, Is.True);
            Assert.That(installs, Is.EqualTo(1), "a second press starts no other install");
            Assert.That((bool?)first?["installing"], Is.True);
            Assert.That(first?.ContainsKey("ok"), Is.False, "nothing is said done or failed while it runs");
            Assert.That(first?.ContainsKey("error"), Is.False);
        });
    }

    // APP1 (UPD-f): while the engine downloads, the state says how much of the installer is here, read from the «.part» the
    // engine writes with no sharing (BaxyUpdateHandler); every published byte here is «checking»; the end is the engine's
    // own, with its cause.
    [Test]
    public async Task WhileItDownloadsTheStateSaysHowMuchIsHereAndTheEndIsTheEnginesOwn()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-update-panel-tests", Guid.NewGuid().ToString("N"));
        string part = Path.Combine(root, "updates", "BAXY-Instalador-1.4.0.exe.part");
        Directory.CreateDirectory(Path.GetDirectoryName(part)!);
        try
        {
            var engine = new TaskCompletionSource<OperationResponse?>(TaskCreationOptions.RunContinuationsAsynchronously);
            List<JsonObject> ended = [];
            var panel = new UpdatePanel(
                (action, _, _, _) => action == "check"
                    ? Task.FromResult<OperationResponse?>(Response("completed", """{"channel":"github","installed":"1.3.2","latest":"1.4.0","newer":true,"downloadBytes":1000}"""))
                    : engine.Task,
                () => root,
                TimeSpan.FromMilliseconds(50));
            panel.InstallEnded += ended.Add;
            JsonObject before = panel.InstallState();
            await panel.CheckAsync(CancellationToken.None);

            JsonObject starting = await panel.InstallAsync(CancellationToken.None);
            JsonObject downloading;
            JsonObject whole;
            using (FileStream written = new(part, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                written.Write(new byte[370]);
                written.Flush();
                downloading = panel.InstallState();
                written.Write(new byte[630]);
                written.Flush();
                whole = panel.InstallState();
            }

            engine.SetResult(Response("failed", """{"channel":"github","installed":"1.3.2","latest":"1.4.0"}""", "baxy_update_download_failed"));
            await panel.Installing!;
            JsonObject failed = panel.InstallState();

            Assert.Multiple(() =>
            {
                Assert.That(before.ToJsonString(), Is.EqualTo("""{"installing":false}"""));
                Assert.That(starting.ToJsonString(), Is.EqualTo(
                    """{"installing":true,"phase":"downloading","latest":"1.4.0","downloadBytes":1000,"downloadedBytes":null}"""));
                Assert.That((long?)downloading["downloadedBytes"], Is.EqualTo(370));
                Assert.That((string?)downloading["phase"], Is.EqualTo("downloading"));
                Assert.That((string?)whole["phase"], Is.EqualTo("checking"));
                Assert.That((long?)whole["downloadedBytes"], Is.EqualTo(1000));
                Assert.That((bool?)failed["installing"], Is.False);
                Assert.That((bool?)failed["ok"], Is.False);
                Assert.That((string?)failed["error"], Is.EqualTo("baxy_update_download_failed"));
                Assert.That(ended.Select(static told => (string?)told["error"]), Is.EqualTo(new[] { "baxy_update_download_failed" }));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // APP1 (UPD-f): an install that ended is the last word until the button is pressed again, which starts another; a
    // failure nothing expected is kept and told as an end that is not known, never as nothing at all.
    [Test]
    public async Task AfterAnEndTheButtonStartsAnotherAndAFailureNothingExpectedIsToldAndKept()
    {
        int installs = 0;
        List<string> kept = [];
        var panel = new UpdatePanel(
            (_, _, _, _) => Interlocked.Increment(ref installs) == 1
                ? throw new FormatException("not one of the failures a call to the engine has")
                : Task.FromResult<OperationResponse?>(Response("completed", """{"channel":"github","installed":"1.3.2","latest":"1.4.0","installerStarted":true}""")),
            record: (source, failure) => kept.Add($"{source}:{failure.GetType().Name}"));

        JsonObject unknown = await panel.InstallAsync(CancellationToken.None);
        JsonObject stillUnknown = panel.InstallState();
        JsonObject started = await panel.InstallAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(unknown.ToJsonString(), Is.EqualTo("""{"ok":false,"error":"update_outcome_unknown","installing":false}"""));
            Assert.That(stillUnknown.ToJsonString(), Is.EqualTo(unknown.ToJsonString()));
            Assert.That(kept, Is.EqualTo(new[] { "update:FormatException" }));
            Assert.That(installs, Is.EqualTo(2));
            Assert.That((bool?)started["ok"], Is.True);
            Assert.That((bool?)started["installerStarted"], Is.True);
            Assert.That((bool?)started["installing"], Is.False);
        });
    }

    // APP1 (UPD-f): the view's two routes. With no engine the button's request answers its end at once, and the state the
    // view reads afterwards is that same end.
    [Test]
    public async Task TheViewsRoutesAnswerTheInstallsStateAtOnce()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            (int idle, JsonObject before) = await view.SendAsync("GET", "/update/install");
            (int pressed, JsonObject answer) = await view.SendAsync("POST", "/update/install");
            (int read, JsonObject state) = await view.SendAsync("GET", "/update/install");

            Assert.Multiple(() =>
            {
                Assert.That(new[] { idle, pressed, read }, Is.All.EqualTo(200));
                Assert.That(before.ToJsonString(), Is.EqualTo("""{"installing":false}"""));
                Assert.That(answer.ToJsonString(), Is.EqualTo("""{"ok":false,"error":"engine_not_ready","installing":false}"""));
                Assert.That(state.ToJsonString(), Is.EqualTo(answer.ToJsonString()));
            });
        }
    }

    // VER1 (G-14, INT19's blind review left it open): said in the chat, «Actualizar BAXY» was noted in «Salidas a internet»
    // wherever it ran, because the catalog says baxy.update may reach the internet. A copy from Steam or itch.io only opens
    // the store, and a development copy asks no one: the call's own receipt says where it went (its typed «channel»), as the
    // Settings button already reads it (WentOnline). A receipt that does not say keeps the note: nothing said it stayed in.
    [TestCase("install", "completed", """{"version":1,"channel":"github","installed":"1.3.2","latest":"1.4.0","newer":true}""", null, true)]
    [TestCase("install", "failed", """{"version":1,"channel":"github","installed":"1.3.2"}""", "baxy_update_unreachable", true)]
    [TestCase("install", "completed", """{"version":1,"channel":"steam","installed":"1.3.2","opened":"steam_library","updatedBy":"steam","storeUpdatesItself":true}""", null, false)]
    [TestCase("install", "completed", """{"version":1,"channel":"itch","installed":"1.3.2","opened":"itch_page","updatedBy":"itch","storeUpdatesItself":true}""", null, false)]
    [TestCase("install", "failed", """{"version":1,"channel":"itch","installed":"1.3.2","updatedBy":"itch","storeUpdatesItself":true}""", "baxy_update_by_itch_app", false)]
    [TestCase("install", "failed", """{"version":1,"channel":"development","installed":"1.3.2"}""", "baxy_update_development_build", false)]
    [TestCase("install", "failed", """{"version":1,"channel":"github","installed":"1.3.2"}""", "baxy_update_source_unknown", false)]
    [TestCase("install", "failed", null, "provider_failed", true)]
    // Held-out: sixteen receipts a reviewer wrote from BaxyUpdateHandler alone, without this change (VER1, 2026-11-09).
    [TestCase("check", "completed", """{"version":1,"channel":"steam","installed":"1.3.2","updatedBy":"steam","storeUpdatesItself":true,"authority":"baxy_distribution_store"}""", null, false, TestName = "HeldOut_h01_check_steam_ok")]
    [TestCase("check", "completed", """{"version":1,"channel":"itch","installed":"1.3.2","updatedBy":"itch","storeUpdatesItself":true,"authority":"baxy_distribution_store"}""", null, false, TestName = "HeldOut_h02_check_itch_ok")]
    [TestCase("check", "failed", """{"version":1,"channel":"development","installed":"1.3.2"}""", "baxy_update_development_build", false, TestName = "HeldOut_h03_check_development_baxy_update_development_build")]
    [TestCase("check", "failed", """{"version":1,"channel":"github","installed":"1.3.2"}""", "baxy_update_source_unknown", false, TestName = "HeldOut_h04_check_github_baxy_update_source_unknown")]
    [TestCase("check", "pending", """{"version":1,"channel":"github","installed":"1.3.2"}""", "baxy_update_unreachable", true, TestName = "HeldOut_h05_check_github_baxy_update_unreachable")]
    [TestCase("check", "completed", """{"version":1,"channel":"github","installed":"1.3.2","updatedBy":"github","latest":"1.4.0","newer":true,"downloadBytes":48211456,"releasePage":"https://github.com/ejemplo/BAXY/releases/tag/v1.4.0","authority":"github_releases_latest"}""", null, true, TestName = "HeldOut_h06_check_github_ok")]
    [TestCase("check", "completed", """{"version":1,"channel":"github","installed":"1.3.2","updatedBy":"github","latest":"1.3.2","newer":false,"releasePage":"https://github.com/ejemplo/BAXY/releases/tag/v1.3.2","authority":"github_releases_latest"}""", null, true, TestName = "HeldOut_h07_check_github_ok")]
    [TestCase("install", "completed", """{"version":1,"channel":"steam","installed":"1.3.2","updatedBy":"steam","storeUpdatesItself":true,"opened":"steam_library","delivered":true,"authority":"baxy_update_store_opened"}""", null, false, TestName = "HeldOut_h08_install_steam_ok")]
    [TestCase("install", "failed", """{"version":1,"channel":"steam","installed":"1.3.2","updatedBy":"steam","storeUpdatesItself":true}""", "baxy_update_store_not_opened", false, TestName = "HeldOut_h09_install_steam_baxy_update_store_not_opened")]
    [TestCase("install", "completed", """{"version":1,"channel":"itch","installed":"1.3.2","updatedBy":"itch","storeUpdatesItself":true,"opened":"itch_page","delivered":true,"authority":"baxy_update_store_opened"}""", null, false, TestName = "HeldOut_h10_install_itch_ok")]
    [TestCase("install", "failed", """{"version":1,"channel":"itch","installed":"1.3.2","updatedBy":"itch","storeUpdatesItself":true}""", "baxy_update_by_itch_app", false, TestName = "HeldOut_h11_install_itch_baxy_update_by_itch_app")]
    [TestCase("install", "pending", """{"version":1,"channel":"github","installed":"1.3.2","latest":"1.4.0"}""", "baxy_update_download_failed", true, TestName = "HeldOut_h12_install_github_baxy_update_download_failed")]
    [TestCase("install", "failed", """{"version":1,"channel":"github","installed":"1.3.2","latest":"1.3.2","newer":false}""", "baxy_update_already_latest", true, TestName = "HeldOut_h13_install_github_baxy_update_already_latest")]
    [TestCase("install", "failed", """{"version":1,"channel":"github","installed":"1.3.2","latest":"1.4.0"}""", "baxy_update_installer_missing", true, TestName = "HeldOut_h14_install_github_baxy_update_installer_missing")]
    [TestCase("install", "failed", """{"version":1,"channel":"github","installed":"1.3.2","latest":"1.4.0"}""", "baxy_update_hash_mismatch", true, TestName = "HeldOut_h15_install_github_baxy_update_hash_mismatch")]
    [TestCase("install", "completed", """{"version":1,"channel":"github","installed":"1.3.2","latest":"1.4.0","installerSha256":"9f2c4e1ab07d5c83e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7","installerStarted":true,"appExitRequested":true,"delivered":true,"authority":"baxy_update_installer_started"}""", null, true, TestName = "HeldOut_h16_install_github_ok")]
    public async Task TheChatNotesAnUpdateAsGoingOnlineOnlyWhereItsReceiptSaysItDid(
        string action, string status, string? result, string? error, bool online)
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            JsonElement? facts = result is null ? null : JsonDocument.Parse(result).RootElement.Clone();
            OperationOutcome outcome = error is null ? OperationOutcome.Success(facts)
                : status == "pending" ? OperationOutcome.RetryableFailure(error, facts)
                : OperationOutcome.Failure(error, facts);
            string message = OperationVisibleFacts.FromOutcome(UpdatePanel.Operation, outcome);
            var step = new NativeTurnStep(UpdatePanel.Operation, new JsonObject { ["action"] = action },
                status, status == "completed", error, 12, message, "c1", Sent: true);
            const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
            object loop = typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
            var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
            host.StepCompleted!(step);
            JsonObject shown = view.Sink.Items.Single(static i => (string?)i["who"] == "baxy")["steps"]!.AsArray()
                .OfType<JsonObject>().Single();
            bool logged = view.Sink.Events.Any(static e => (string?)e["type"] == "net");

            Assert.Multiple(() =>
            {
                Assert.That(shown["net"] is not null, Is.EqualTo(online), "the step's «salió a internet»");
                Assert.That(logged, Is.EqualTo(online), "the session's «Salidas a internet»");
            });
        }
    }

    private static OperationResponse Response(string status, string result, string? error = null) => new(
        ProtocolTypes.OperationResponse,
        "request",
        "mission",
        "invocation",
        status,
        "{}",
        status == "completed",
        false,
        JsonDocument.Parse(result).RootElement.Clone(),
        error);
}
