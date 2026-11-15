using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Net.Http;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows;

namespace Baxy.Installer;

internal static partial class Program
{
    private const string ManifestResource = "Baxy.Installer.release.json";
    private const string FilesResource = "Baxy.Installer.files.json";
    private const string SingleInstance = @"Local\BAXY.Installer";
    internal const int Failure = 1;
    private const int AttachParentProcess = -1;
    private const int StandardOutput = -11;
    private const uint DiskFile = 1;
    private const uint PipeFile = 3;

    internal static readonly string LogPath = Path.Combine(Path.GetTempPath(), "BAXY-Instalador.log");

    [STAThread]
    private static int Main(string[] arguments)
    {
        CommandLine command = CommandLine.Parse(arguments);
        int result = Run(command);
        // V132: the copy in TEMP that did the uninstall cannot delete itself; it hands its removal over as it ends.
        if (command.UninstallRun)
        {
            TempCopy.RemoveWhenDone();
        }

        return result;
    }

    private static int Run(CommandLine command)
    {
        if (command.Help || command.Error is not null)
        {
            string help = CommandLine.HelpText(CommandLine.Language, InstallPaths.ForThisUser.Root);
            Log(command.Error ?? "help");
            Tell(command.Error is null ? help : $"{command.Error}{Environment.NewLine}{Environment.NewLine}{help}", command.Quiet);
            return command.Error is null ? 0 : CommandLine.InvalidCommandLine;
        }

        InstallPaths paths;
        try
        {
            paths = command.Uninstall ? InstallPaths.ForUninstall(command.Directory, WindowsPlaces.ForThisUser, Environment.ProcessPath)
                : command.Directory is null ? InstallPaths.ForThisUser
                : InstallPaths.Chosen(command.Directory);
        }
        catch (Exception wrong) when (wrong is ArgumentException or IOException or UnauthorizedAccessException)
        {
            Log(wrong.Message);
            Tell(wrong.Message, command.Quiet);
            return wrong is NothingToUninstallException ? CommandLine.NotInstalled : CommandLine.InvalidCommandLine;
        }

        // UNI1 (REV8 U1): --delete-data of data another installed BAXY uses removes nothing, and says why, before any copy.
        if (command.Uninstall && command.DeleteData && WindowsIntegration.DataSharedWith(paths) is { } sharedWith)
        {
            string refused = CommandLine.DataStays(CommandLine.Language, sharedWith, WindowsPlaces.ForThisUser.Data);
            Log(refused);
            Tell(refused, command.Quiet);
            return Failure;
        }

        // A copy outside the folder (the downloaded installer) removes it in place and its exit code is the result; the
        // installed copy cannot delete its own exe and hands the work to a copy in TEMP.
        bool inPlace = command.Quiet && !IsInside(Environment.ProcessPath!, paths.Root);
        if (command.Uninstall && !command.UninstallRun && !inPlace)
        {
            return UninstallFromACopy(paths, command);
        }

        using Mutex single = new(true, SingleInstance, out bool first);
        if (!first)
        {
            Log("another installer is already running");
            return Failure;
        }

        // UNI3 (VIVOU2): what an uninstaller before UNI2 left of a BAXY that is gone, before anything else is done.
        WindowsIntegration.ForgetGone(WindowsPlaces.ForThisUser);

        if (command.Uninstall && command.Quiet)
        {
            string? held = command.Original is int waiting && OriginalProcess.PathOf(waiting) is { } exe && IsInside(exe, paths.Root)
                ? exe
                : null;
            int result = UninstallQuietly(paths, command.DeleteData, held);
            if (command.Original is int original
                && OriginalProcess.End(original, result, Path.GetFileNameWithoutExtension(WindowsIntegration.InstallerName))
                && held is not null
                && result == 0)
            {
                WindowsIntegration.DeleteHeld(paths, held);
            }

            return result;
        }

        ReleaseManifest? manifest = LoadManifest();
        FileManifest? files = manifest is null ? null : LoadFiles(manifest);
        // AUT2: the installer BAXY already has, given a newer release (--release), or BAXY's own download first (--fetch).
        if (command.Update && paths.HoldsBaxy && (command.Release is not null || command.Fetch))
        {
            return Applied(command, manifest, files, paths);
        }

        if (command.Quiet)
        {
            return manifest is null ? Failure : InstallQuietly(manifest, files, paths, command.Update);
        }

        // AUT1: the update BAXY started has nothing to ask (the agreement is the one already accepted): no window.
        if (command.Update && manifest is not null && paths.HoldsBaxy
            && !AcceptedAgreement.MustBeAccepted(paths, AcceptedAgreement.Read(paths)))
        {
            return UpdateSilently(manifest, files, paths, voiceAllowed: !command.NoVoice);
        }

        Application application = new();
        using MainWindow window = new(
            manifest, uninstalling: command.UninstallRun, paths, voiceAllowed: !command.NoVoice, updating: command.Update, files);
        application.DispatcherUnhandledException += (_, unhandled) =>
        {
            Log(unhandled.Exception.ToString());
            unhandled.Handled = true;
            window.ShowFailure(unhandled.Exception);
        };
        _ = application.Run(window);
        // APP2 (VIVO14): «No pude instalarme… Ya estoy abierto» exited with 0, which a script reads as installed.
        if (window.Result != 0)
        {
            Log($"the window closed without finishing: exit {window.Result}");
        }

        return window.Result;
    }

    /// <summary>A log that cannot be written (the disk that just filled up) never stops what is being told.</summary>
    /// <summary>
    /// The first line of an installation, with or without window: the cards read on this machine and what is told of
    /// them, the parts chosen for it and where it goes. It is what to look at when a machine got the wrong parts (INS-2).
    /// </summary>
    internal static void LogMachine(ReleaseManifest forMachine, IReadOnlyList<GpuAdapter> adapters, InstallPaths paths) =>
        Log($"{forMachine.Version}: {MachineGpu.Describe(adapters)}; {string.Join(", ", forMachine.Archives.Select(archive => archive.Name))}; {paths.Root}");

    internal static void Log(string line)
    {
        try
        {
            File.AppendAllText(LogPath, $"{DateTime.Now:s} {line}{Environment.NewLine}", Encoding.UTF8);
        }
        catch (Exception unwritten) when (unwritten is IOException or UnauthorizedAccessException)
        {
            Debug.WriteLine(unwritten);
        }
    }

    /// <summary>
    /// This is a window program: its text goes to the file or pipe a script gave it, else to the console it was started
    /// from (AttachConsole), else to a message box (a shortcut with --help). The file or pipe is taken before attaching,
    /// which would point the output at the console instead; attaching still gives it the console's code page, the one
    /// the shell that reads it decodes with.
    /// </summary>
    private static void Tell(string text, bool quiet)
    {
        nint handle = GetStdHandle(StandardOutput);
        bool redirected = handle is not (0 or -1) && GetFileType(handle) is DiskFile or PipeFile;
        using Stream given = redirected ? Console.OpenStandardOutput() : Stream.Null;
        bool attached = AttachConsole(AttachParentProcess);
        if (redirected)
        {
            using StreamWriter writer = new(given, attached ? ConsoleEncoding() : new UTF8Encoding(false));
            writer.WriteLine();
            writer.WriteLine(text);
        }
        else if (attached)
        {
            Console.Out.WriteLine();
            Console.Out.WriteLine(text);
        }
        else if (!quiet)
        {
            // Never with --quiet: a box nobody sees would hold a script (WinRM, a scheduled task) for ever.
            MessageBox.Show(text, "BAXY");
        }
    }

    /// <summary>The attached console's code page (850 in a Spanish cmd), which .NET only knows with the code page provider.</summary>
    private static Encoding ConsoleEncoding()
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        int page = (int)GetConsoleOutputCP();
        return page == Encoding.UTF8.CodePage ? new UTF8Encoding(false) : Encoding.GetEncoding(page);
    }

    private static bool IsInside(string path, string root) =>
        Path.GetFullPath(path).StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);

    private static ReleaseManifest? LoadManifest()
    {
        using Stream? resource = Assembly.GetExecutingAssembly().GetManifestResourceStream(ManifestResource);
        return resource is null ? null : ReleaseManifest.Parse(resource);
    }

    // AUT1: files.json as this installer carries it; it counts only when it is the one its release.json names.
    private static FileManifest? LoadFiles(ReleaseManifest manifest)
    {
        using Stream? resource = Assembly.GetExecutingAssembly().GetManifestResourceStream(FilesResource);
        if (resource is null)
        {
            return null;
        }

        using MemoryStream carried = new();
        resource.CopyTo(carried);
        return FileManifest.Named(carried.ToArray(), manifest);
    }

    /// <summary>
    /// The copy in TEMP does the uninstall. With --quiet the original waits for it: the copy ends it with the result
    /// (<see cref="OriginalProcess"/>), so a script waiting on the original reads that result as its exit code.
    /// </summary>
    private static int UninstallFromACopy(InstallPaths paths, CommandLine command)
    {
        string copy = Path.Combine(Directory.CreateTempSubdirectory(TempCopy.FolderPrefix).FullName, TempCopy.CopyName);
        File.Copy(Environment.ProcessPath!, copy, overwrite: true);
        // Windows lets a folder move with a running exe inside but not with a process's working folder inside (W1, own
        // measurement): the original waits from the copy's folder, not from the one being removed.
        Environment.CurrentDirectory = Path.GetDirectoryName(copy)!;
        ProcessStartInfo start = new(copy)
        {
            UseShellExecute = false,
            WorkingDirectory = Path.GetDirectoryName(copy)!,
        };
        foreach (string argument in command.ForTheCopy(paths.Root, Environment.ProcessId))
        {
            start.ArgumentList.Add(argument);
        }

        using Process? started = Process.Start(start);
        if (!command.Quiet || started is null)
        {
            return started is null ? Failure : 0;
        }

        started.WaitForExit();
        return started.ExitCode;
    }

    /// <summary>For removing by script or remote console: no window, and what happened in the log.</summary>
    private static int UninstallQuietly(InstallPaths paths, bool deleteData, string? held = null)
    {
        if (Voice.BaxyIsOpen())
        {
            Log("a BAXY is open: close it first");
            return Failure;
        }

        try
        {
            WindowsIntegration.Uninstall(paths, deleteData, held: held);
            Log($"uninstalled {paths.Root}{(deleteData ? " and its data" : string.Empty)}");
            return 0;
        }
        catch (Exception failure) when (failure is IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            Log(failure.ToString());
            return Failure;
        }
    }

    /// <summary>For installing by remote console (tests on other machines): no window, and what happened in the log.</summary>
    private static int InstallQuietly(ReleaseManifest manifest, FileManifest? files, InstallPaths paths, bool updating = false)
    {
        using HttpClient http = new() { Timeout = Timeout.InfiniteTimeSpan };
        http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY-Instalador/" + manifest.Version);
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed();
        ReleaseManifest chosen = manifest.ForMachine(adapters);
        LogMachine(chosen, adapters, paths);
        Installation installation = new(chosen, paths, new PartFetcher(http), files: files, ranges: new RangeFetcher(http));
        // PRV2 (A5): --quiet shows no agreement, as always; it keeps what the installation it replaces accepted, so the
        // next update with a window asks for the agreement if it is not that one (AcceptedAgreement).
        string? accepted = AcceptedAgreement.Read(paths);
        QuietInstall quiet = new(
            MachineGpu.Choose(adapters),
            updating,
            Voice.BaxyIsOpen,
            async () =>
            {
                // UPD1 (REV10 M4): before the components of Windows are downloaded into the .download folder.
                paths.RefuseWhatIsNotBaxys();
                // FIR1: nothing of Windows nor of BAXY is installed before release.json's signature checks out.
                await SignedRelease.ConfirmAsync(http, manifest, paths, SignedRelease.BuiltInKeys, CancellationToken.None)
                    .ConfigureAwait(false);
                await Prerequisites.InstallMissingAsync(http, paths.Downloads, CancellationToken.None).ConfigureAwait(false);
                await installation.RunAsync((_, _, _) => { }, CancellationToken.None).ConfigureAwait(false);
            },
            () =>
            {
                if (accepted is not null)
                {
                    AcceptedAgreement.Write(paths, accepted, Log);
                }

                WindowsIntegration.Register(paths, chosen.Version, chosen.InstalledBytes);
            },
            Log);
        try
        {
            return quiet.RunAsync().GetAwaiter().GetResult();
        }
#pragma warning disable CA1031 // The log is all a remote console has.
        catch (Exception failure)
#pragma warning restore CA1031
        {
            Log(failure.ToString());
            return Failure;
        }
    }

    /// <summary>
    /// AUT1: the update BAXY started for itself, with no window (<see cref="SilentUpdate"/>). How it ended is written
    /// beside this installer, in the folder BAXY downloaded it to, for the BAXY that opens next (<see cref="UpdateOutcome"/>).
    /// </summary>
    private static int UpdateSilently(ReleaseManifest manifest, FileManifest? files, InstallPaths paths, bool voiceAllowed)
    {
        using HttpClient http = new() { Timeout = Timeout.InfiniteTimeSpan };
        http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY-Instalador/" + manifest.Version);
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed();
        ReleaseManifest chosen = manifest.ForMachine(adapters);
        LogMachine(chosen, adapters, paths);
        // The agreement is the one this installation accepted (else the window asks): it stays accepted.
        string? accepted = AcceptedAgreement.Read(paths);
        (string Version, int SizeKb)? registered = WindowsIntegration.Registered(paths);
        string told = Path.GetDirectoryName(Environment.ProcessPath!)!;
        Voice? voice = null;
        try
        {
            return SilentUpdate.Over(
                manifest,
                chosen,
                files,
                paths,
                http,
                SignedRelease.BuiltInKeys,
                told,
                Voice.BaxyIsOpen,
                within => Prerequisites.InstallMissingAsync(http, paths.Downloads, within),
                () =>
                {
                    if (accepted is not null)
                    {
                        AcceptedAgreement.Write(paths, accepted, Log);
                    }

                    WindowsIntegration.Register(paths, chosen.Version, chosen.InstalledBytes);
                },
                () =>
                {
                    if (registered is { } was)
                    {
                        WindowsIntegration.SayAgain(paths, was);
                    }
                },
                () => Open(paths),
                // The first line comes with BAXY closed, so its own voice is free; a BAXY whose voice the person
                // turned off is not spoken for either.
                line => (voice ??= new Voice(voiceAllowed && !VoiceIsOff(told))).Say(CommandLine.Language, line),
                Log).RunAsync().GetAwaiter().GetResult();
        }
#pragma warning disable CA1031 // The log is all there is: no window to tell it in.
        catch (Exception failure)
#pragma warning restore CA1031
        {
            Log(failure.ToString());
            return Failure;
        }
        finally
        {
            voice?.Dispose();
        }
    }

    /// <summary>
    /// AUT2: --fetch and --release, with no window ever. The release is this installer's own, or with --release a newer
    /// one it applies (<see cref="SignedRelease.ReadAsync"/>: refused when this installer is not enough for it, so BAXY
    /// downloads that release's installer). --fetch only downloads, with BAXY open, and says how far it is
    /// (<see cref="FetchProgress"/>); without it, the update with BAXY closed (<see cref="UpdateSilently"/>), which then
    /// finds what --fetch left. An agreement this installation did not accept is never shown here: BAXY asks for it by
    /// voice before starting this, and without it nothing is installed.
    /// </summary>
    private static int Applied(CommandLine command, ReleaseManifest? carried, FileManifest? carriedFiles, InstallPaths paths)
    {
        string told = Path.GetDirectoryName(Environment.ProcessPath!)!;
        using HttpClient http = new() { Timeout = Timeout.InfiniteTimeSpan };
        string own = typeof(Program).Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion
            ?? "0.0.0";
        http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY-Instalador/" + own.Split('+')[0]);
        ReleaseManifest? manifest = carried;
        FileManifest? files = carriedFiles;
        string? refused = null;
        if (command.Release is { } release)
        {
            try
            {
                (manifest, files) = SignedRelease.ReadAsync(http, new Uri(release), SignedRelease.BuiltInKeys, own,
                    AcceptedAgreement.Current, CancellationToken.None).GetAwaiter().GetResult();
            }
#pragma warning disable CA1031 // Whatever it was, nothing was changed, and BAXY is told why.
            catch (Exception failure)
#pragma warning restore CA1031
            {
                Log(failure.ToString());
                refused = failure is InstallerTooOldException ? TooOld : SilentUpdate.Reason(Failures.Classify(failure, () => false));
            }
        }

        if (refused is null && (manifest is null || AcceptedAgreement.MustBeAccepted(paths, AcceptedAgreement.Read(paths))))
        {
            refused = manifest is null ? "other" : NotAccepted;
        }

        if (refused is not null)
        {
            Log($"not updated ({refused}): nothing was changed");
            if (command.Fetch)
            {
                new FetchProgress(told, manifest?.Version ?? "?").Fail(refused, 0);
            }
            else
            {
                LeaveWritten(new UpdateOutcome(SignedRelease.InstalledVersion(paths.App)?.ToString(3) ?? "0.0.0",
                    manifest?.Version ?? "?", UpdateOutcome.Failed, refused, 0, 0,
                    DateTimeOffset.Now.ToString("o", CultureInfo.InvariantCulture)));
                _ = OpenAgain(paths);
            }

            return Failure;
        }

        return command.Fetch ? FetchSilently(manifest!, files, paths, http, told) : UpdateSilently(manifest!, files, paths, !command.NoVoice);
    }

    /// <summary>AUT2: what --release says when this installer is not the one for that release (outcome «reason»).</summary>
    internal const string TooOld = "installer_too_old";

    /// <summary>AUT2: the agreement this installation accepted is not the one this release brings.</summary>
    internal const string NotAccepted = "agreement_not_accepted";

    private static int FetchSilently(ReleaseManifest manifest, FileManifest? files, InstallPaths paths, HttpClient http, string told)
    {
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed();
        ReleaseManifest chosen = manifest.ForMachine(adapters);
        LogMachine(chosen, adapters, paths);
        FetchProgress progress = new(told, chosen.Version);
        Installation installation = new(chosen, paths, new PartFetcher(http), files: files, ranges: new RangeFetcher(http));
        try
        {
            SignedRelease.ConfirmAsync(http, manifest, paths, SignedRelease.BuiltInKeys, CancellationToken.None).GetAwaiter().GetResult();
            installation.FetchAsync(progress.Report, CancellationToken.None).GetAwaiter().GetResult();
            long total = installation.NeededBytes;
            progress.End(installation.DownloadedBytes, total);
            Log($"fetched {chosen.Version} with BAXY open: {installation.DownloadedBytes} bytes downloaded of {total} needed");
            return 0;
        }
#pragma warning disable CA1031 // The progress file is all the BAXY that waits has.
        catch (Exception failure)
#pragma warning restore CA1031
        {
            Log(failure.ToString());
            progress.Fail(SilentUpdate.Reason(Failures.Classify(failure, () => false)), installation.DownloadedBytes);
            return Failure;
        }
    }

    // The BAXY a refused update leaves as it was, opened again as the update would have. Revisión ciega (AUT2): the BAXY
    // that started this was asked to close and may still be closing; it is given the minute SilentUpdate gives it (else it
    // closed after this looked and was left closed), and one that stays open (busy) is left as it is.
    private static StartedBaxy? OpenAgain(InstallPaths paths)
    {
        Stopwatch closing = Stopwatch.StartNew();
        while (Voice.BaxyIsOpen() && closing.Elapsed < TimeSpan.FromSeconds(60))
        {
            Thread.Sleep(500);
        }

        return Voice.BaxyIsOpen() ? null : Open(paths);
    }

    /// <summary>
    /// AUT1: how an update ended, written beside this installer (the profile's updates folder, where BAXY downloads it)
    /// for the BAXY that opens next. What Windows refuses to write is logged: the update itself is not undone for it.
    /// </summary>
    internal static void LeaveWritten(UpdateOutcome outcome)
    {
        try
        {
            outcome.Write(Path.GetDirectoryName(Environment.ProcessPath!)!);
        }
        catch (Exception unwritten) when (unwritten is IOException or UnauthorizedAccessException)
        {
            Log("the outcome was not written: " + unwritten.Message);
        }
    }

    /// <summary>
    /// Whether the BAXY that downloaded this installer has its voice off (Settings › «voz», the profile's
    /// field-settings.v1.json, «voiceMuted»): the installer runs from that profile's updates folder
    /// (UpdateInstallerFile.Folder). No file there, or one that says nothing of it, is BAXY as it comes: with voice.
    /// </summary>
    internal static bool VoiceIsOff(string updatesFolder)
    {
        try
        {
            string settings = Path.Combine(Path.GetDirectoryName(Path.TrimEndingDirectorySeparator(updatesFolder)) ?? updatesFolder, "field-settings.v1.json");
            return File.Exists(settings)
                && System.Text.Json.Nodes.JsonNode.Parse(File.ReadAllText(settings)) is System.Text.Json.Nodes.JsonObject values
                && values["voiceMuted"] is System.Text.Json.Nodes.JsonValue muted && muted.TryGetValue(out bool off) && off;
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException or System.Text.Json.JsonException)
        {
            return false;
        }
    }

    // BAXY's app, opened as the window opens it; null when Windows did not start it.
    private static StartedBaxy? Open(InstallPaths paths)
    {
        try
        {
            Process? started = Process.Start(new ProcessStartInfo(paths.App)
            {
                UseShellExecute = true,
                WorkingDirectory = Path.GetDirectoryName(paths.App)!,
            });
            return started is null
                ? null
                : new StartedBaxy(
                    () => started.HasExited,
                    () =>
                    {
                        try
                        {
                            if (!started.HasExited)
                            {
                                // By its own process, and what it started with it: never another BAXY's.
                                started.Kill(entireProcessTree: true);
                                _ = started.WaitForExit(TimeSpan.FromSeconds(30));
                            }
                        }
                        catch (Exception gone) when (gone is InvalidOperationException or System.ComponentModel.Win32Exception)
                        {
                            Log(gone.Message);
                        }
                    });
        }
        catch (Exception refused) when (refused is System.ComponentModel.Win32Exception or FileNotFoundException or InvalidOperationException)
        {
            Log(refused.ToString());
            return null;
        }
    }

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachConsole(int processId);

    [LibraryImport("kernel32.dll")]
    private static partial nint GetStdHandle(int which);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetFileType(nint handle);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetConsoleOutputCP();
}
