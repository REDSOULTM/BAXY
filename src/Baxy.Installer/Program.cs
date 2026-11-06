using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Reflection;
using System.Text;
using System.Windows;

namespace Baxy.Installer;

internal static class Program
{
    private const string ManifestResource = "Baxy.Installer.release.json";
    private const string RunUninstall = "--uninstall-run";
    private const string SingleInstance = @"Local\BAXY.Installer";
    private const int Failure = 1;

    internal static readonly string LogPath = Path.Combine(Path.GetTempPath(), "BAXY-Instalador.log");

    [STAThread]
    private static int Main(string[] arguments)
    {
        if (arguments.Contains("--uninstall"))
        {
            string copy = Path.Combine(Directory.CreateTempSubdirectory("BAXY-").FullName, "BAXY-Desinstalador.exe");
            File.Copy(Environment.ProcessPath!, copy, overwrite: true);
            using Process? started = Process.Start(new ProcessStartInfo(copy, RunUninstall)
            {
                UseShellExecute = false,
                WorkingDirectory = Path.GetDirectoryName(copy)!,
            });
            return 0;
        }

        using Mutex single = new(true, SingleInstance, out bool first);
        if (!first)
        {
            Log("another installer is already running");
            return Failure;
        }

        ReleaseManifest? manifest = LoadManifest();
        if (arguments.Contains("--quiet"))
        {
            return manifest is null ? Failure : InstallQuietly(manifest);
        }

        Application application = new();
        using MainWindow window = new(manifest, uninstalling: arguments.Contains(RunUninstall));
        application.DispatcherUnhandledException += (_, unhandled) =>
        {
            Log(unhandled.Exception.ToString());
            unhandled.Handled = true;
            window.ShowFailure(unhandled.Exception);
        };
        return application.Run(window);
    }

    /// <summary>A log that cannot be written (the disk that just filled up) never stops what is being told.</summary>
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

    private static ReleaseManifest? LoadManifest()
    {
        using Stream? resource = Assembly.GetExecutingAssembly().GetManifestResourceStream(ManifestResource);
        return resource is null ? null : ReleaseManifest.Parse(resource);
    }

    /// <summary>For installing by remote console (tests on other machines): no window, and what happened in the log.</summary>
    private static int InstallQuietly(ReleaseManifest manifest)
    {
        using HttpClient http = new() { Timeout = Timeout.InfiniteTimeSpan };
        http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY-Instalador/" + manifest.Version);
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed();
        manifest = manifest.ForMachine(adapters);
        Log($"{manifest.Version}: {MachineGpu.Choose(adapters)}; {string.Join(", ", manifest.Archives.Select(archive => archive.Name))}");
        if (Voice.BaxyIsOpen())
        {
            Log("a BAXY is open: close it first");
            return Failure;
        }

        Installation installation = new(manifest, InstallPaths.ForThisUser, new PartFetcher(http));
        try
        {
            Prerequisites.InstallMissingAsync(http, InstallPaths.ForThisUser.Downloads, CancellationToken.None).GetAwaiter().GetResult();
            installation.RunAsync((_, _, _) => { }, CancellationToken.None).GetAwaiter().GetResult();
            WindowsIntegration.Register(InstallPaths.ForThisUser, manifest.Version, manifest.InstalledBytes);
            Log("installed");
            return 0;
        }
#pragma warning disable CA1031 // The log is all a remote console has.
        catch (Exception failure)
#pragma warning restore CA1031
        {
            Log(failure.ToString());
            return Failure;
        }
    }
}
