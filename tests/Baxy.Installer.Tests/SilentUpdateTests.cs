using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// AUT1 (orden del dueño, 13-11-2026): the update BAXY starts for itself has no window and no button; whatever happens,
/// BAXY ends open (the new one, or the one that was there) and the next BAXY is told how it ended.
/// </summary>
[TestFixture]
internal sealed class SilentUpdateTests
{
    private string directory = string.Empty;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(directory, recursive: true);

    [Test]
    public async Task It_installs_opens_the_new_baxy_and_lets_the_old_one_go_once_it_started()
    {
        Run run = new() { ConfirmsAfterStarts = 1 };

        int result = await run.Update().RunAsync();

        Assert.That(result, Is.Zero);
        Assert.That(run.Steps, Is.EqualTo(new[] { "install", "register", "start", "drop" }));
        Assert.That(run.Told.Select(outcome => (outcome.State, outcome.Reason)), Is.EqualTo(new[]
        {
            (UpdateOutcome.Started, (string?)null), (UpdateOutcome.Installed, null),
        }));
        Assert.That(run.Told[^1], Has.Property(nameof(UpdateOutcome.From)).EqualTo("1.5.2").And.Property(nameof(UpdateOutcome.To)).EqualTo("1.5.3"));
        Assert.That(run.Told[^1].DownloadedBytes, Is.EqualTo(94_000_000));
    }

    [Test]
    public async Task It_waits_for_the_baxy_that_asked_to_close()
    {
        Run run = new() { ConfirmsAfterStarts = 1, OpenChecks = 3 };

        int result = await run.Update().RunAsync();

        Assert.That(result, Is.Zero);
        Assert.That(run.Steps[0], Is.EqualTo("install"));
    }

    [Test]
    public async Task A_baxy_that_does_not_close_is_left_as_it_is()
    {
        Run run = new() { OpenChecks = int.MaxValue };

        int result = await (run.Update() with { CloseLimit = TimeSpan.FromMilliseconds(30) }).RunAsync();

        Assert.That(result, Is.EqualTo(Program.Failure));
        Assert.That(run.Steps, Is.Empty, "nothing is installed, and no second BAXY is opened over the one that is open");
        Assert.That(run.Told.Select(outcome => (outcome.State, outcome.Reason)), Is.EqualTo(new[] { (UpdateOutcome.Failed, (string?)"open") }));
    }

    private static IEnumerable<TestCaseData> Failures() =>
    [
        new TestCaseData(new HttpRequestException("the line went down"), "network"),
        new TestCaseData(new InvalidDataException("app/Baxy.exe does not have the expected hash"), "damaged"),
        new TestCaseData(new UnsignedReleaseException("release.json is not signed with BAXY's key"), "unsigned"),
        new TestCaseData(new IOException("disk full") { HResult = unchecked((int)0x80070070) }, "disk"),
        new TestCaseData(new OlderReleaseException("1.6.0", "1.5.3"), "older"),
    ];

    [TestCaseSource(nameof(Failures))]
    public async Task What_fails_before_the_swap_changes_nothing_and_the_baxy_that_was_there_opens_again(Exception failure, string reason)
    {
        Run run = new() { InstallFails = failure };

        int result = await run.Update().RunAsync();

        Assert.That(result, Is.EqualTo(Program.Failure));
        Assert.That(run.Steps, Is.EqualTo(new[] { "install", "start" }), "no registration, no rollback: only the BAXY that was there, opened again");
        Assert.That(run.Told.Select(outcome => (outcome.State, outcome.Reason)), Is.EqualTo(new[] { (UpdateOutcome.Failed, (string?)reason) }));
    }

    [Test]
    public async Task A_new_baxy_that_ends_without_saying_it_started_is_undone_and_the_old_one_opens()
    {
        Run run = new() { ExitsAfterChecks = 2 };

        int result = await run.Update().RunAsync();

        Assert.That(result, Is.EqualTo(Program.Failure));
        Assert.That(run.Steps, Is.EqualTo(new[] { "install", "register", "start", "stop", "rollback", "start" }));
        Assert.That(run.Told.Select(outcome => (outcome.State, outcome.Reason)), Is.EqualTo(new[]
        {
            (UpdateOutcome.Started, (string?)null), (UpdateOutcome.RolledBack, UpdateOutcome.NotStarted),
        }));
    }

    [Test]
    public async Task A_new_baxy_that_hangs_is_ended_and_undone_after_the_limit()
    {
        Run run = new();

        int result = await (run.Update() with { StartLimit = TimeSpan.FromMilliseconds(40) }).RunAsync();

        Assert.That(result, Is.EqualTo(Program.Failure));
        Assert.That(run.Steps, Is.EqualTo(new[] { "install", "register", "start", "stop", "rollback", "start" }));
        Assert.That(run.Told[^1].State, Is.EqualTo(UpdateOutcome.RolledBack));
    }

    [Test]
    public async Task A_baxy_that_could_not_even_be_opened_is_undone()
    {
        Run run = new() { DoesNotOpen = true };

        int result = await run.Update().RunAsync();

        Assert.That(result, Is.EqualTo(Program.Failure));
        Assert.That(run.Steps, Is.EqualTo(new[] { "install", "register", "start", "rollback", "start" }));
    }

    // Blind review A-1: Windows refusing the way back left the person with no BAXY open at all.
    [Test]
    public async Task A_rollback_that_windows_refuses_says_what_is_in_the_folder_and_opens_it()
    {
        Run run = new() { ExitsAfterChecks = 1, RollBackFails = true };

        int result = await run.Update().RunAsync();

        Assert.That(result, Is.EqualTo(Program.Failure));
        Assert.That(run.Told[^1], Has.Property(nameof(UpdateOutcome.State)).EqualTo(UpdateOutcome.Started)
            .And.Property(nameof(UpdateOutcome.Reason)).EqualTo(UpdateOutcome.NotStarted));
        Assert.That(run.Steps, Is.EqualTo(new[] { "install", "register", "start", "stop", "rollback", "start" }),
            "the BAXY that is in the folder is opened: the person is not left without one");
    }

    // Blind review E-1: «started» and «installed» carried two moments, and «Me actualicé» was told at two starts.
    [Test]
    public async Task Every_step_of_one_update_is_the_same_outcome_for_whoever_tells_it()
    {
        Run run = new() { ConfirmsAfterStarts = 1 };

        _ = await run.Update().RunAsync();

        Assert.That(run.Told.Select(outcome => outcome.At).Distinct().Count(), Is.EqualTo(1));
        run.Told[0].Write(directory);
        run.Told[0].MarkTold(directory);
        run.Told[^1].Write(directory);
        Assert.That(UpdateOutcome.Read(directory)!.WasTold(directory), Is.True, "told at its «started», it is not told again at its «installed»");
    }

    // Blind review C-1: with no window, a line that only trickles kept BAXY closed for ever.
    [Test]
    public async Task A_download_that_never_ends_stops_at_its_limit_with_baxy_as_it_was()
    {
        Run run = new() { InstallNeverEnds = true };

        int result = await (run.Update() with { InstallLimit = TimeSpan.FromMilliseconds(50) }).RunAsync();

        Assert.That(result, Is.EqualTo(Program.Failure));
        Assert.That(run.Steps, Is.EqualTo(new[] { "install", "start" }), "the BAXY that was there opens again");
        Assert.That(run.Told.Select(outcome => (outcome.State, outcome.Reason)), Is.EqualTo(new[] { (UpdateOutcome.Failed, (string?)SilentUpdate.Slow) }));
    }

    // Blind review D-2: a registration that failed in a way nobody expected left the new BAXY in place and unopened.
    [Test]
    public async Task Whatever_the_registration_throws_the_new_baxy_is_opened()
    {
        Run run = new() { ConfirmsAfterStarts = 1, RegisterThrows = new InvalidOperationException("the registry said no") };

        int result = await run.Update().RunAsync();

        Assert.That(result, Is.EqualTo(QuietInstall.NotRegistered));
        Assert.That(run.Steps, Is.EqualTo(new[] { "install", "register", "start", "drop" }));
        Assert.That(run.Told[^1].State, Is.EqualTo(UpdateOutcome.Installed));
    }

    [Test]
    public async Task A_registration_windows_refuses_does_not_undo_the_update()
    {
        Run run = new() { ConfirmsAfterStarts = 1, RegisterFails = true };

        int result = await run.Update().RunAsync();

        Assert.That(result, Is.EqualTo(QuietInstall.NotRegistered));
        Assert.That(run.Told[^1].State, Is.EqualTo(UpdateOutcome.Installed));
    }

    [Test]
    public void The_outcome_is_read_as_it_was_written_and_told_once()
    {
        UpdateOutcome written = new("1.5.2", "1.5.3", UpdateOutcome.RolledBack, UpdateOutcome.NotStarted, 123, 45, "2026-11-13T20:00:00.0000000-03:00");

        Assert.That(UpdateOutcome.Read(directory), Is.Null, "no update yet");
        written.Write(directory);
        UpdateOutcome? read = UpdateOutcome.Read(directory);

        Assert.That(read, Is.EqualTo(written));
        Assert.That(read!.Updated, Is.False);
        Assert.That(read.WasTold(directory), Is.False);
        read.MarkTold(directory);
        Assert.That(read.WasTold(directory), Is.True);
        Assert.That((written with { At = "2026-11-14T09:00:00.0000000-03:00" }).WasTold(directory), Is.False, "the next update is told too");
    }

    [Test]
    public void The_new_baxy_confirms_its_own_version_only()
    {
        Assert.That(UpdateOutcome.IsConfirmed(directory, "1.5.3"), Is.False);

        UpdateOutcome.Confirm(directory, "1.5.2");
        Assert.That(UpdateOutcome.IsConfirmed(directory, "1.5.3"), Is.False, "the old BAXY, opened again, confirms nothing of the new one");

        UpdateOutcome.Confirm(directory, "1.5.3");
        Assert.That(UpdateOutcome.IsConfirmed(directory, "1.5.3"), Is.True);

        UpdateOutcome.Unconfirm(directory);
        Assert.That(UpdateOutcome.IsConfirmed(directory, "1.5.3"), Is.False);
    }

    [Test]
    public void A_file_that_is_not_an_outcome_is_none()
    {
        File.WriteAllText(Path.Combine(directory, "last-update.json"), "{\"from\":\"1.5.2\"");

        Assert.That(UpdateOutcome.Read(directory), Is.Null);
    }

    [Test]
    public void A_long_download_is_said_with_each_line_once_and_a_short_one_is_not_announced()
    {
        List<string> said = [];
        SpokenProgress longOne = new(said.Add, worthSaying: 100, apart: TimeSpan.Zero);
        foreach (long done in new long[] { 0, 10, 40, 50, 60, 89, 90, 100 })
        {
            longOne.Report(InstallPhase.Downloading, done, 100);
        }

        longOne.Report(InstallPhase.Unpacking, 100, 100);
        SpokenProgress shortOne = new(said.Add, worthSaying: 100, apart: TimeSpan.Zero);
        shortOne.Report(InstallPhase.Downloading, 50, 99);

        Assert.That(said, Is.EqualTo(new[] { "working", "half", "almost" }));
    }

    [Test]
    public void Lines_are_never_said_one_over_another()
    {
        List<string> said = [];
        SpokenProgress progress = new(said.Add, worthSaying: 100, apart: TimeSpan.FromMinutes(1));

        progress.Report(InstallPhase.Downloading, 0, 100);
        progress.Report(InstallPhase.Downloading, 60, 100);
        progress.Report(InstallPhase.Downloading, 95, 100);

        Assert.That(said, Is.EqualTo(new[] { "working" }), "the download ended before the first line did");
    }

    [Test]
    public void The_installer_keeps_quiet_for_a_baxy_whose_voice_is_off()
    {
        string updates = Path.Combine(directory, "updates");
        Directory.CreateDirectory(updates);

        Assert.That(Program.VoiceIsOff(updates), Is.False, "no settings yet: BAXY as it comes, with voice");

        File.WriteAllText(Path.Combine(directory, "field-settings.v1.json"), "{\"voiceMuted\":true,\"web\":true}");
        Assert.That(Program.VoiceIsOff(updates), Is.True);

        File.WriteAllText(Path.Combine(directory, "field-settings.v1.json"), "{\"voiceMuted\":false}");
        Assert.That(Program.VoiceIsOff(updates), Is.False);

        File.WriteAllText(Path.Combine(directory, "field-settings.v1.json"), "not json");
        Assert.That(Program.VoiceIsOff(updates), Is.False);
    }

    /// <summary>One update with everything around it faked: what it did, in order, and what it told.</summary>
    private sealed class Run
    {
        private int openChecks;
        private int starts;
        private int exitChecks;

        internal List<string> Steps { get; } = [];

        internal List<UpdateOutcome> Told { get; } = [];

        /// <summary>How many times BAXY is still found open before it closes.</summary>
        internal int OpenChecks { get; init; }

        internal Exception? InstallFails { get; init; }

        /// <summary>A line that only trickles: the download goes on until it is stopped.</summary>
        internal bool InstallNeverEnds { get; init; }

        /// <summary>The registration throws this (Windows refusing it is a NotRegisteredException; anything else, too).</summary>
        internal Exception? RegisterThrows { get; init; }

        internal bool RegisterFails { get; init; }

        internal bool RollBackFails { get; init; }

        internal bool DoesNotOpen { get; init; }

        /// <summary>The new BAXY says it started once it was opened this many times; 0: never.</summary>
        internal int ConfirmsAfterStarts { get; init; }

        /// <summary>The new BAXY's process is found ended at this check; 0: it never ends.</summary>
        internal int ExitsAfterChecks { get; init; }

        internal SilentUpdate Update() => new(
            "1.5.2",
            "1.5.3",
            () => openChecks++ < OpenChecks,
            within =>
            {
                Steps.Add("install");
                return InstallNeverEnds ? Task.Delay(Timeout.Infinite, within)
                    : InstallFails is null ? Task.CompletedTask
                    : Task.FromException(InstallFails);
            },
            () =>
            {
                Steps.Add("register");
                if (RegisterThrows is not null)
                {
                    throw RegisterThrows;
                }

                if (RegisterFails)
                {
                    throw new NotRegisteredException("refused", new UnauthorizedAccessException());
                }
            },
            () =>
            {
                Steps.Add("start");
                starts++;
                return DoesNotOpen && starts == 1
                    ? null
                    : new StartedBaxy(() => ExitsAfterChecks > 0 && ++exitChecks >= ExitsAfterChecks, () => Steps.Add("stop"));
            },
            () => ConfirmsAfterStarts > 0 && starts >= ConfirmsAfterStarts,
            () => Steps.Add("drop"),
            () =>
            {
                Steps.Add("rollback");
                if (RollBackFails)
                {
                    throw new IOException("in use");
                }
            },
            failure => Baxy.Installer.Failures.Classify(failure, () => false),
            () => 94_000_000,
            Told.Add,
            _ => { })
        {
            Pace = TimeSpan.FromMilliseconds(1),
        };
    }
}
