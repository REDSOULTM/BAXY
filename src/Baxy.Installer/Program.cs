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
            string language = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "es" ? "es" : "en";
            string help = CommandLine.HelpText(language, InstallPaths.ForThisUser.Root);
            Log(command.Error ?? "help");
            Tell(command.Error is null ? help : $"{command.Error}{Environment.NewLine}{Environment.NewLine}{help}", command.Quiet);
            return command.Error is null ? 0 : CommandLine.InvalidCommandLine;
        }

        InstallPaths paths;
        try
        {
            paths = command.Uninstall ? InstallPaths.ForUninstall(command.Directory, WindowsPlaces.ForThisUser)
                : command.Directory is null ? InstallPaths.ForThisUser
                : InstallPaths.Chosen(command.Directory);
        }
        catch (Exception wrong) when (wrong is ArgumentException or IOException or UnauthorizedAccessException)
        {
            Log(wrong.Message);
            Tell(wrong.Message, command.Quiet);
            return CommandLine.InvalidCommandLine;
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
        if (command.Quiet)
        {
            return manifest is null ? Failure : InstallQuietly(manifest, paths, command.Update);
        }

        Application application = new();
        using MainWindow window = new(
            manifest, uninstalling: command.UninstallRun, paths, voiceAllowed: !command.NoVoice, updating: command.Update);
        application.DispatcherUnhandledException += (_, unhandled) =>
        {
            Log(unhandled.Exception.ToString());
            unhandled.Handled = true;
            window.ShowFailure(unhandled.Exception);
        };
        return application.Run(window);
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
    private static int InstallQuietly(ReleaseManifest manifest, InstallPaths paths, bool updating = false)
    {
        using HttpClient http = new() { Timeout = Timeout.InfiniteTimeSpan };
        http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY-Instalador/" + manifest.Version);
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed();
        ReleaseManifest chosen = manifest.ForMachine(adapters);
        LogMachine(chosen, adapters, paths);
        Installation installation = new(chosen, paths, new PartFetcher(http));
        // PRV2 (A5): --quiet shows no agreement, as always; it keeps what the installation it replaces accepted, so the
        // next update with a window asks for the agreement if it is not that one (AcceptedAgreement).
        string? accepted = AcceptedAgreement.Read(paths);
        QuietInstall quiet = new(
            MachineGpu.Choose(adapters),
            updating,
            Voice.BaxyIsOpen,
            async () =>
            {
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
