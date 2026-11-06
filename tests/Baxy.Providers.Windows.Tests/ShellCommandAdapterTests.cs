using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, comandos; D11): el comando se
/// corre en una consola sin perfil, en la carpeta pedida, con la salida tal
/// cual; lo destructivo se nombra y no se corre.
/// </summary>
[TestFixture]
public sealed class ShellCommandAdapterTests
{
    [Test]
    public async Task ACommandRunsInTheNamedFolderAndItsOutputTravelsVerbatim()
    {
        var runner = new RecordingRunner(0, "On branch main\r\nnothing to commit, working tree clean\r\n", string.Empty);
        string cwd = Path.GetTempPath();
        var adapter = new ShellCommandAdapter(runner, cwd);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "shell.command.run",
            JsonSerializer.SerializeToElement(new { command = "git status", cwd }),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            // Nothing read back what the command changed: it may have changed something (git is not a read-only
            // command for the kernel), so the result says so, and no effect was observed.
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(result.GetProperty("effectReadBack").GetBoolean(), Is.False);
            Assert.That(runner.Executable, Is.EqualTo("powershell.exe"));
            Assert.That(runner.Arguments, Does.Contain("-NoProfile").And.Contain("-NonInteractive"));
            Assert.That(runner.Arguments[^1], Does.StartWith(PowerShellCommand.Utf8Output + "Set-Location -LiteralPath '").And.EndWith("; git status" + ShellCommandAdapter.ExitTail));
            Assert.That(result.GetProperty("exitCode").GetInt32(), Is.EqualTo(0));
            Assert.That(result.GetProperty("succeeded").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("lineCount").GetInt32(), Is.EqualTo(2));
            Assert.That(result.TryGetProperty("lines", out _), Is.False, "the output goes once, as stdout");
            Assert.That(result.GetProperty("truncated").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("cwd").GetString(), Is.EqualTo(cwd));
        });
    }

    [Test]
    public async Task AFailingCommandKeepsItsExitCodeAndErrorText()
    {
        var runner = new RecordingRunner(1, string.Empty, "pytest : El término 'pytest' no se reconoce");
        var adapter = new ShellCommandAdapter(runner, Path.GetTempPath());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "shell.command.run",
            JsonSerializer.SerializeToElement(new { command = "pytest" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("shell_command_exit_nonzero"));
            Assert.That(receipt.Result!.Value.GetProperty("exitCode").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result!.Value.GetProperty("succeeded").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("stderr").GetString(), Does.Contain("no se reconoce"));
        });
    }

    [Test]
    public async Task ACommandThatOnlyReadsRanWithoutAnEffect()
    {
        var runner = new RecordingRunner(0, "a.txt\r\n", string.Empty);
        var adapter = new ShellCommandAdapter(runner, Path.GetTempPath());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "shell.command.run",
            JsonSerializer.SerializeToElement(new { command = "Get-ChildItem" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
        });
    }

    // Round A: a cmdlet that fails leaves $LASTEXITCODE unset, and «exit $LASTEXITCODE» exited 0 (succeeded:true for
    // «Get-Item <missing>»). A real console runs the same script the product runs: the failed cmdlet exits non-zero,
    // a native command keeps its own code, and one that ran well exits 0. Only reads and «cmd /c exit»; nothing changes.
    [TestCase("Get-Item -LiteralPath 'MISSING'", 1)]
    [TestCase("cmd /c exit 5", 5)]
    [TestCase("cmd /c exit 4; Get-Date | Out-Null", 4)]
    [TestCase("Get-Date | Out-Null", 0)]
    public async Task ARealConsoleExitsWithTheStatusOfWhatRan(string command, int exitCode)
    {
        string cwd = Path.GetTempPath();
        string missing = Path.Combine(cwd, "baxy-missing-" + Guid.NewGuid().ToString("N"));
        var adapter = new ShellCommandAdapter(new ExternalProcessRunner(), cwd);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "shell.command.run",
            JsonSerializer.SerializeToElement(new { command = command.Replace("MISSING", missing) }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("exitCode").GetInt32(), Is.EqualTo(exitCode));
            Assert.That(receipt.Result!.Value.GetProperty("succeeded").GetBoolean(), Is.EqualTo(exitCode == 0));
            Assert.That(receipt.ErrorCode, Is.EqualTo(exitCode == 0 ? null : "shell_command_exit_nonzero"));
        });
    }

    // Round A: a console whose output passed the runner's bound ran and was stopped; it was told as «not started».
    // Ronda B: a console stopped at its deadline was told as an observed effect, even for a command that only reads.
    [TestCase("git pull", true, false)]
    [TestCase("Get-ChildItem", false, false)]
    [TestCase("git pull", true, true)]
    [TestCase("Get-ChildItem", false, true)]
    public async Task AConsoleThatWasStoppedRanAndSaysWhatItMayHaveChanged(string command, bool mayChange, bool timedOut)
    {
        var adapter = new ShellCommandAdapter(
            new StoppingRunner(timedOut
                ? new TimeoutException("External process timed out.")
                : new ExternalProcessOutputTooLargeException("External process output exceeded its bound.")),
            Path.GetTempPath());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "shell.command.run",
            JsonSerializer.SerializeToElement(new { command }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode,
                Is.EqualTo(timedOut ? "shell_command_timeout" : "shell_command_output_too_large"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.EqualTo(mayChange));
        });
    }

    [Test]
    public async Task LongOutputIsBoundedAndMarkedTruncated()
    {
        var runner = new RecordingRunner(0, new string('x', ShellCommandAdapter.MaximumOutputCharacters + 100), string.Empty);
        var adapter = new ShellCommandAdapter(runner, Path.GetTempPath());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "shell.command.run",
            JsonSerializer.SerializeToElement(new { command = "ls" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("stdout").GetString()!.Length, Is.EqualTo(ShellCommandAdapter.MaximumOutputCharacters));
            Assert.That(receipt.Result!.Value.GetProperty("truncated").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task AMissingFolderIsAnHonestAbsenceBeforeAnyRun()
    {
        var runner = new RecordingRunner(0, string.Empty, string.Empty);
        var adapter = new ShellCommandAdapter(runner, Path.GetTempPath());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "shell.command.run",
            JsonSerializer.SerializeToElement(new { command = "ls", cwd = @"C:\no\such\folder\baxy" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("shell_command_directory_not_found"));
            Assert.That(runner.Executable, Is.Null);
        });
    }

    // A command that ran well reaches the person as completed through the handler and the kernel, the same path the
    // product takes (round 3: a change to the observed-effect rule turned a console that ran well into «failed», and
    // nothing between the adapter and the response was tested). One that may change something is asked for first and
    // runs with the person's yes; one that only reads runs at once.
    [TestCase("git status")]
    [TestCase("Get-Date")]
    public async Task ACommandThatRanWellIsCompletedThroughTheHandlerAndTheKernel(string command)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-shell-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var runner = new RecordingRunner(0, "ok\r\n", string.Empty);
            var handler = new ExternalCapabilityHandler(
                "shell.command.run", new AdapterProvider(new ShellCommandAdapter(runner, root)));
            await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                Path.Combine(root, "journal.jsonl"),
                new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
            using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
            var request = new OperationRequest(
                ProtocolTypes.OperationRequest,
                Guid.NewGuid().ToString("D"),
                Guid.NewGuid().ToString("D"),
                Guid.NewGuid().ToString("D"),
                "shell.command.run",
                JsonSerializer.SerializeToElement(new { command, cwd = root }));

            OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);
            if (response.ErrorCode == "confirmation_required")
            {
                response = await engine.ExecuteAsync(
                    request with
                    {
                        RequestId = Guid.NewGuid().ToString("D"),
                        ConfirmationToken = response.Result!.Value.GetProperty("token").GetString(),
                    },
                    CancellationToken.None);
            }

            Assert.Multiple(() =>
            {
                Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed), response.Message);
                Assert.That(response.Verified, Is.True);
                Assert.That(response.ErrorCode, Is.Null);
                Assert.That(response.Result!.Value.GetProperty("exitCode").GetInt32(), Is.Zero);
                Assert.That(runner.Executable, Is.EqualTo("powershell.exe"), "the command ran");
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private sealed class AdapterProvider(ShellCommandAdapter adapter) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            adapter.InvokeAsync(operation, arguments, cancellationToken);
    }

    private sealed class RecordingRunner(int exitCode, string output, string error) : IExternalProcessRunner
    {
        internal string? Executable { get; private set; }

        internal IReadOnlyList<string> Arguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable,
            IReadOnlyList<string> arguments,
            TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            Executable = executable;
            Arguments = arguments;
            return ValueTask.FromResult(new ExternalProcessResult(exitCode, output, error));
        }
    }

    private sealed class StoppingRunner(Exception stop) : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable,
            IReadOnlyList<string> arguments,
            TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw stop;
    }

    // Encargo 61 (banco de uso U45, diag-f11d c1, c5, c6): file.write and filesystem.create.directory read «BAXY-bench» in
    // the home folder and this call refused the same words, so the model created a folder that was there, ran it again
    // to the same refusal, or asked the person whether the folder existed. One reading for the three.
    [TestCase("")]
    [TestCase("home/")]
    public async Task AFolderNoKnownFolderStartsIsInTheHomeFolderAsAFileToolReadsIt(string before)
    {
        string name = "baxy-cwd-" + Guid.NewGuid().ToString("N");
        string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), name);
        Directory.CreateDirectory(folder);
        try
        {
            var adapter = new ShellCommandAdapter(new RecordingRunner(0, "ok", ""), Path.GetTempPath());

            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "shell.command.run",
                JsonSerializer.SerializeToElement(new { command = "dir", cwd = before + name }),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(receipt.Result?.GetProperty("cwd").GetString(), Is.EqualTo(folder));
            });
        }
        finally
        {
            Directory.Delete(folder);
        }
    }

    // Encargo 61 (banco de uso U45, held-out): the model wrote the home of the file tools' example (C:\Users\<other>\…), and
    // the code alone left it saying the person's folder did not exist. The failure says where it looked and their home and,
    // when the path named another place, the call with the folder's own name. Measured: 23/35 → 32/35.
    [Test]
    public async Task AFolderThatIsNotThereSaysWhereItLookedAndTheCallWithItsOwnName()
    {
        string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        string name = "baxy-cwd-" + Guid.NewGuid().ToString("N");
        var runner = new RecordingRunner(0, "ok", "");
        var adapter = new ShellCommandAdapter(runner, Path.GetTempPath());

        ExternalCapabilityReceipt elsewhere = await adapter.InvokeAsync(
            "shell.command.run",
            JsonSerializer.SerializeToElement(new { command = "whoami", cwd = @"C:\Users\otra-persona\" + name }),
            CancellationToken.None);
        ExternalCapabilityReceipt inHome = await adapter.InvokeAsync(
            "shell.command.run", JsonSerializer.SerializeToElement(new { command = "whoami", cwd = name }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(elsewhere.ErrorCode, Is.EqualTo("shell_command_directory_not_found"));
            Assert.That(elsewhere.Result?.GetProperty("cwd").GetString(), Is.EqualTo(@"C:\Users\otra-persona\" + name));
            Assert.That(elsewhere.Result?.GetProperty("next").GetString(), Is.EqualTo(
                $@"nothing ran: there is no folder C:\Users\otra-persona\{name}; this person's home is {home}; "
                + $$"""to run it in their folder of that name, call shell_command_run {"command":"whoami","cwd":"{{name}}"}"""));
            // Its own name in their home and not there: there is no other call to offer.
            Assert.That(inHome.ErrorCode, Is.EqualTo("shell_command_directory_not_found"));
            Assert.That(inHome.Result?.GetProperty("next").GetString(), Is.EqualTo(
                $@"nothing ran: there is no folder {Path.Combine(home, name)}; this person's home is {home}"));
            Assert.That(runner.Executable, Is.Null);
        });
    }

    [Test]
    public async Task AFolderOutOfThePersonsFoldersIsRefusedBeforeRunning()
    {
        var runner = new RecordingRunner(0, "ok", "");
        var adapter = new ShellCommandAdapter(runner, Path.GetTempPath());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "shell.command.run", JsonSerializer.SerializeToElement(new { command = "dir", cwd = "../.." }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("shell_command_directory_not_found"));
            Assert.That(runner.Executable, Is.Null);
        });
    }

    [Test]
    public async Task AKnownFolderNamesTheWorkingDirectoryAndAnythingElseIsRefused()
    {
        // Fase 5 (2026-09-21, H0048 «ejecuta pytest»): «cwd» is a known folder name (or a
        // subfolder of one) or an absolute path; a folder that is not there is refused before running.
        var runner = new RecordingRunner(0, "ok", "");
        var adapter = new ShellCommandAdapter(runner, Path.GetTempPath());

        ExternalCapabilityReceipt known = await adapter.InvokeAsync(
            "shell.command.run", JsonSerializer.SerializeToElement(new { command = "dir", cwd = "desktop" }), CancellationToken.None);
        ExternalCapabilityReceipt refused = await adapter.InvokeAsync(
            "shell.command.run", JsonSerializer.SerializeToElement(new { command = "dir", cwd = "perfil" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(known.Verified, Is.True, known.ErrorCode);
            Assert.That(known.Result?.GetProperty("cwd").GetString(), Is.EqualTo(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory)));
            Assert.That(refused.Verified, Is.False);
            Assert.That(refused.ErrorCode, Is.EqualTo("shell_command_directory_not_found"));
        });
    }
}
