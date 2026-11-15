using System.Diagnostics;
using System.Globalization;

namespace Baxy.Installer;

/// <summary>The BAXY an update opened: whether its process ended, and how to end it when it never started.</summary>
internal sealed record StartedBaxy(Func<bool> HasExited, Action Stop);

/// <summary>
/// AUT1 (orden del dueño, 13-11-2026: «El usuario debe simplemente decir Baxi actualízate y que se actualice
/// automáticamente […] se abre el instalador y yo tengo que darle al botón instalar. No me parece bien, eso debe ser
/// automático»). What --update does when there is nothing to ask the person: no window and no button. It waits for the
/// BAXY that started it to close, installs (only the files that differ, <see cref="FileDelta"/>), opens the new BAXY and
/// waits for it to say it started; until then the BAXY it replaced is kept beside it, and comes back by itself if the
/// new one never says so. It is the shape the update frameworks have: a process apart that waits for the app to exit,
/// applies and restarts it (Velopack: «WaitExitThenApplyUpdates […] will launch Update.exe and wait for 60 seconds»,
/// docs.velopack.io/integrating/overview), keeping the version before (Squirrel.Windows keeps «current and immediately
/// previous», docs/using/update-process.md); both read 2026-11-13. Going back when the new version does not start is
/// this installer's own: none of those documents it. Every way out is written for the BAXY that opens next
/// (<see cref="UpdateOutcome"/>), and the log says the same.
/// </summary>
internal sealed record SilentUpdate(
    string From,
    string To,
    Func<bool> BaxyIsOpen,
    Func<CancellationToken, Task> InstallAsync,
    Action Register,
    Func<StartedBaxy?> StartBaxy,
    Func<bool> Confirmed,
    Action DropPrevious,
    Action RollBack,
    Func<Exception, FailureKind> Classify,
    Func<long> DownloadedBytes,
    Action<UpdateOutcome> Tell,
    Action<string> Log)
{
    internal TimeSpan Pace { get; init; } = TimeSpan.FromMilliseconds(500);

    /// <summary>How long the BAXY that asked for the update is given to close: a minute, as --quiet --update gives it.</summary>
    internal TimeSpan CloseLimit { get; init; } = TimeSpan.FromSeconds(60);

    /// <summary>
    /// How long the person may be left with BAXY closed while it downloads and installs. A line that only trickles would
    /// keep it closed for hours with nothing on the screen (blind review, C-1): past this, the update stops with BAXY as
    /// it was, what was downloaded stays, and the next «actualízate» goes on from there.
    /// </summary>
    internal TimeSpan InstallLimit { get; init; } = TimeSpan.FromMinutes(20);

    /// <summary>How long the new BAXY is given to say it started (its window and its engine, not its model).</summary>
    internal TimeSpan StartLimit { get; init; } = TimeSpan.FromMinutes(5);

    /// <summary>The download took longer than BAXY may stay closed (<see cref="InstallLimit"/>).</summary>
    internal const string Slow = "slow";

    internal async Task<int> RunAsync()
    {
        Stopwatch clock = Stopwatch.StartNew();
        // One update, one moment: its steps are told as the same outcome, not as new ones (blind review, E-1).
        string at = DateTimeOffset.Now.ToString("o", CultureInfo.InvariantCulture);
        UpdateOutcome Outcome(string state, string? reason) =>
            new(From, To, state, reason, DownloadedBytes(), (int)clock.Elapsed.TotalSeconds, at);
        while (BaxyIsOpen() && clock.Elapsed < CloseLimit)
        {
            await Task.Delay(Pace).ConfigureAwait(false);
        }

        if (BaxyIsOpen())
        {
            // BAXY is busy or did not close: it stays as it is, open.
            Log("BAXY did not close: nothing was changed");
            Tell(Outcome(UpdateOutcome.Failed, Reason(FailureKind.Open)));
            return Program.Failure;
        }

        using (CancellationTokenSource limit = new(InstallLimit))
        {
            try
            {
                await InstallAsync(limit.Token).ConfigureAwait(false);
            }
#pragma warning disable CA1031 // Whatever stopped the update, the BAXY that was there opens again and says why.
            catch (Exception failure)
#pragma warning restore CA1031
            {
                Log(failure.ToString());
                FailureKind kind = Classify(failure);
                string reason = failure is OperationCanceledException && limit.IsCancellationRequested ? Slow : Reason(kind);
                Log($"not updated ({reason}): nothing was changed, the BAXY that was there opens again");
                Tell(Outcome(UpdateOutcome.Failed, reason));
                if (kind != FailureKind.Open)
                {
                    _ = StartBaxy();
                }

                return Program.Failure;
            }
        }

        int result = 0;
        try
        {
            Register();
        }
#pragma warning disable CA1031 // BAXY is in place: whatever its registration ended in, it is opened (blind review, D-2).
        catch (Exception refused)
#pragma warning restore CA1031
        {
            // The next installation tries its registration again (INS-5).
            Log("installed, but not registered: " + refused);
            result = QuietInstall.NotRegistered;
        }

        Tell(Outcome(UpdateOutcome.Started, null));
        StartedBaxy? started = StartBaxy();
        Stopwatch starting = Stopwatch.StartNew();
        bool confirmed = false;
        while (started is not null && !(confirmed = Confirmed()) && !started.HasExited() && starting.Elapsed < StartLimit)
        {
            await Task.Delay(Pace).ConfigureAwait(false);
        }

        if (confirmed || Confirmed())
        {
            DropPrevious();
            Tell(Outcome(UpdateOutcome.Installed, null));
            Log(string.Create(CultureInfo.InvariantCulture, $"updated {From} -> {To}: {DownloadedBytes()} bytes downloaded, {clock.Elapsed.TotalSeconds:F0} s"));
            return result;
        }

        Log($"BAXY {To} did not start: BAXY {From} comes back");
        started?.Stop();
        try
        {
            RollBack();
        }
        catch (Exception stuck) when (stuck is IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            // Windows did not let the folders go back: whatever BAXY is in the folder is opened, so the person is not
            // left without one, and what is told is what is there, not what was wanted (blind review, A-1).
            Log(stuck.ToString());
            Tell(Outcome(UpdateOutcome.Started, UpdateOutcome.NotStarted));
            _ = StartBaxy();
            return Program.Failure;
        }

        Tell(Outcome(UpdateOutcome.RolledBack, UpdateOutcome.NotStarted));
        _ = StartBaxy();
        return Program.Failure;
    }

    /// <summary>
    /// The update over the real pieces: the signature first (FIR1: nothing is downloaded nor installed before
    /// release.json's checks out), then Windows' components, then the files that differ, with the BAXY before kept until
    /// the new one says it started. What only the real machine has (whether BAXY is open, opening it, «Installed apps»,
    /// the recorded voice) comes in from outside, so the rest is the same code under test and in the installer.
    /// </summary>
    /// <param name="carried">The manifest as this installer carries it; <paramref name="chosen"/> is it for this machine.</param>
    /// <param name="told">The folder where the outcome is written and the new BAXY confirms its start.</param>
    /// <param name="unregister">«Installed apps» says again what it said before, when the update is undone.</param>
    /// <param name="freeBytes">The free bytes of the installation's drive, when not the drive's own (a test's).</param>
    internal static SilentUpdate Over(
        ReleaseManifest carried,
        ReleaseManifest chosen,
        FileManifest? files,
        InstallPaths paths,
        HttpClient http,
        IReadOnlyList<string> keys,
        string told,
        Func<bool> baxyIsOpen,
        Func<CancellationToken, Task> prerequisites,
        Action register,
        Action unregister,
        Func<StartedBaxy?> open,
        Action<string> say,
        Action<string> log,
        Func<long>? freeBytes = null)
    {
        PartFetcher parts = new(http);
        RangeFetcher ranges = new(http);
        Installation installation = freeBytes is null
            ? new(chosen, paths, parts, files: files, ranges: ranges)
            : new(chosen, paths, parts, files: files, ranges: ranges) { FreeBytes = freeBytes };
        SpokenProgress spoken = new(say);
        return new SilentUpdate(
            SignedRelease.InstalledVersion(paths.App)?.ToString(3) ?? "0.0.0",
            chosen.Version,
            baxyIsOpen,
            async within =>
            {
                UpdateOutcome.Unconfirm(told);
                paths.RefuseWhatIsNotBaxys();
                await SignedRelease.ConfirmAsync(http, carried, paths, keys, within).ConfigureAwait(false);
                await prerequisites(within).ConfigureAwait(false);
                await installation.RunAsync(spoken.Report, within, keepPrevious: true).ConfigureAwait(false);
                log($"files: {installation.KeptFiles} already here, {installation.TakenFiles} downloaded alone, {installation.DownloadedBytes} bytes");
            },
            register,
            open,
            () => UpdateOutcome.IsConfirmed(told, chosen.Version),
            installation.DropPrevious,
            () =>
            {
                installation.RollBack();
                unregister();
            },
            failure => Failures.Classify(failure, baxyIsOpen),
            () => installation.DownloadedBytes,
            outcome =>
            {
                try
                {
                    outcome.Write(told);
                }
                catch (Exception unwritten) when (unwritten is IOException or UnauthorizedAccessException)
                {
                    log("the outcome was not written: " + unwritten.Message);
                }
            },
            log);
    }

    /// <summary>The cause as the file says it, for the BAXY that reads it.</summary>
    internal static string Reason(FailureKind kind) => kind switch
    {
        FailureKind.Disk => "disk",
        FailureKind.Network => "network",
        FailureKind.Open => "open",
        FailureKind.Damaged => "damaged",
        FailureKind.Windows => "windows",
        FailureKind.Unsigned => "unsigned",
        FailureKind.Older => "older",
        FailureKind.NotBaxys => "not_baxys",
        _ => "other",
    };
}

/// <summary>
/// AUT1: with no window, how far a long download is gets said with BAXY's own recorded lines («Me estoy instalando […]
/// Si se corta internet, sigo donde quedé», «Voy en la mitad», «Ya casi termino»: Assets/voice/lines.json), each when it
/// is true, never one over another. A download too short for a line to end (most updates: some 94 MB of 1.5.1 to 1.5.2)
/// is not announced at all: the BAXY that opens says it updated.
/// </summary>
internal sealed class SpokenProgress(Action<string> say, long worthSaying = 256L << 20, TimeSpan? apart = null)
{
    private readonly TimeSpan apart = apart ?? TimeSpan.FromSeconds(12);
    private readonly Stopwatch since = new();
    private readonly object gate = new();
    private int said;

    internal void Report(InstallPhase phase, long done, long total)
    {
        if (phase != InstallPhase.Downloading || total < worthSaying)
        {
            return;
        }

        lock (gate)
        {
            string? line = said == 0 ? "working"
                : since.Elapsed < apart ? null
                : said < 3 && done * 10 >= total * 9 ? "almost"
                : said < 2 && done * 2 >= total ? "half"
                : null;
            if (line is null)
            {
                return;
            }

            said = line == "working" ? 1 : line == "half" ? 2 : 3;
            since.Restart();
            say(line);
        }
    }
}
