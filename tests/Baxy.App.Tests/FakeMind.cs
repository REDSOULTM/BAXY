using System.Diagnostics;
using System.IO;
using System.Text.Json.Nodes;

namespace Baxy.App.Tests;

/// <summary>
/// The mind the App's tests talk to: FakeMind/baxy_mind (the baxy.mind.v1 protocol only, no model and no voice), run by
/// this PC's Python through the same variables the App reads (BAXY_MIND_PYTHON, BAXY_MIND_PYTHONPATH). Each test gets its
/// own folder (its script, what the fake saw and the pids it ran as) and its own data root (BAXY_DATA_DIR), which the
/// App accepts only directly under %LOCALAPPDATA%\BAXY (WindowsPrivateStorage): one «apptest-…» folder there per test,
/// removed after it.
/// </summary>
internal sealed class FakeMind : IDisposable
{
    private static readonly Lazy<string> InstalledPython = new(FindPython);
    private readonly Dictionary<string, string?> _previous = [];

    internal FakeMind()
    {
        Folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        string package = Path.Combine(Folder, "baxy_mind");
        Directory.CreateDirectory(package);
        foreach (string file in Directory.EnumerateFiles(Path.Combine(AppContext.BaseDirectory, "FakeMind", "baxy_mind")))
        {
            File.Copy(file, Path.Combine(package, Path.GetFileName(file)));
        }

        DataRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY",
            "apptest-" + Guid.NewGuid().ToString("N"));
        SetVariable(MindSidecarClient.PythonEnvironmentVariable, InstalledPython.Value);
        SetVariable(MindSidecarClient.PythonPathEnvironmentVariable, Folder);
        SetVariable(MindSidecarClient.DisabledEnvironmentVariable, null);
        SetVariable("BAXY_DATA_DIR", DataRoot);
        // The mind's stderr log goes beside its trace (MindSidecarClient.TraceDirectory): this test's folder, never the
        // owner's %LOCALAPPDATA%\BAXY\renew.
        SetVariable(MindSidecarClient.TraceDirectoryEnvironmentVariable, Folder);
        // What the App's first start leaves in its environment (MindRuntimeDiscovery.ApplyVerified fills the model's
        // variables), so every start a test runs finds the environment it verified, as each one after the first does.
        foreach (string name in (string[])["BAXY_MIND_LLM_GGUF", "BAXY_MIND_LLAMA_SERVER", "BAXY_MIND_NGL"])
        {
            SetVariable(name, Environment.GetEnvironmentVariable(name));
        }

        _ = MindRuntimeDiscovery.ApplyVerified(MindRuntimeDiscovery.DiscoverVerified());
    }

    internal string Folder { get; }

    internal string DataRoot { get; }

    /// <summary>Where the App keeps what the fake wrote to its stderr.</summary>
    internal string StandardErrorLog => Path.Combine(Folder, MindSidecarClient.StandardErrorLogName);

    internal static MindStartupCatalog EmptyCatalog => new([], null, null);

    /// <summary>What the fake does from its next request on (see FakeMind/baxy_mind/__main__.py).</summary>
    internal void Script(JsonObject script) => File.WriteAllText(Path.Combine(Folder, "script.json"), script.ToJsonString());

    /// <summary>Lets a request held on <paramref name="file"/> go.</summary>
    internal void Open(string file) => File.WriteAllText(Path.Combine(Folder, file), string.Empty);

    /// <summary>Every request's type, in the order the fake read them.</summary>
    internal IReadOnlyList<string> Seen
    {
        get
        {
            string log = Path.Combine(Folder, "seen.log");
            if (!File.Exists(log))
            {
                return [];
            }

            using var stream = new FileStream(log, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            using var reader = new StreamReader(stream);
            return reader.ReadToEnd().Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        }
    }

    /// <summary>Every request of <paramref name="type"/> as the fake read it, in order.</summary>
    internal IReadOnlyList<JsonObject> Requests(string type)
    {
        string log = Path.Combine(Folder, "requests.jsonl");
        if (!File.Exists(log))
        {
            return [];
        }

        using var stream = new FileStream(log, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd().Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(static line => JsonNode.Parse(line) as JsonObject)
            .Where(request => request is not null && (string?)request["type"] == type)
            .Select(static request => request!)
            .ToList();
    }

    /// <summary>The fake's processes still running.</summary>
    internal IReadOnlyList<int> LiveProcesses
    {
        get
        {
            string pids = Path.Combine(Folder, "pids");
            if (!Directory.Exists(pids))
            {
                return [];
            }

            var live = new List<int>();
            foreach (string file in Directory.EnumerateFiles(pids))
            {
                if (int.TryParse(Path.GetFileName(file), out int pid) && IsRunning(pid))
                {
                    live.Add(pid);
                }
            }

            return live;
        }
    }

    internal async Task<bool> WaitSeenAsync(string type, int count = 1, double seconds = 10)
    {
        var clock = Stopwatch.StartNew();
        while (clock.Elapsed < TimeSpan.FromSeconds(seconds))
        {
            if (Seen.Count(seen => seen == type) >= count)
            {
                return true;
            }

            await Task.Delay(20);
        }

        return false;
    }

    internal static async Task<MindSidecarClient> StartClientAsync()
    {
        var mind = new MindSidecarClient();
        if (!await mind.TryStartAsync(Task.FromResult(EmptyCatalog), TimeSpan.FromSeconds(30), CancellationToken.None))
        {
            await mind.DisposeAsync();
            throw new InvalidOperationException("The fake mind did not start.");
        }

        return mind;
    }

    public void Dispose()
    {
        foreach (int pid in LiveProcesses)
        {
            try
            {
                using Process process = Process.GetProcessById(pid);
                process.Kill();
                process.WaitForExit(5_000);
            }
            catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
            }
        }

        foreach ((string name, string? value) in _previous)
        {
            Environment.SetEnvironmentVariable(name, value);
        }

        foreach (string folder in (string[])[Folder, DataRoot])
        {
            try
            {
                if (Directory.Exists(folder))
                {
                    Directory.Delete(folder, recursive: true);
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
            }
        }
    }

    private void SetVariable(string name, string? value)
    {
        _previous.TryAdd(name, Environment.GetEnvironmentVariable(name));
        Environment.SetEnvironmentVariable(name, value);
    }

    private static bool IsRunning(int pid)
    {
        try
        {
            using Process process = Process.GetProcessById(pid);
            return !process.HasExited;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return false;
        }
    }

    // This PC's Python 3 (the py launcher's), whatever interpreter the product registered: the fake needs only the
    // standard library.
    private static string FindPython()
    {
        using var launcher = Process.Start(new ProcessStartInfo("py", ["-3", "-c", "import sys; print(sys.executable)"])
        {
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        }) ?? throw new InvalidOperationException("The py launcher did not start.");
        string path = launcher.StandardOutput.ReadToEnd().Trim();
        launcher.WaitForExit();
        return File.Exists(path) ? path : throw new InvalidOperationException("No Python 3 for the fake mind.");
    }
}
