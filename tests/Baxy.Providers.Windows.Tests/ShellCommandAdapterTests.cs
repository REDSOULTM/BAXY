using System.Text.Json;
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
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(runner.Executable, Is.EqualTo("powershell.exe"));
            Assert.That(runner.Arguments, Does.Contain("-NoProfile").And.Contain("-NonInteractive"));
            Assert.That(runner.Arguments[^1], Does.StartWith("Set-Location -LiteralPath '").And.Contain("; git status; exit $LASTEXITCODE"));
            Assert.That(result.GetProperty("exitCode").GetInt32(), Is.EqualTo(0));
            Assert.That(result.GetProperty("succeeded").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("lineCount").GetInt32(), Is.EqualTo(2));
            Assert.That(result.GetProperty("lines")[0].GetString(), Is.EqualTo("On branch main"));
            Assert.That(result.GetProperty("lines")[1].GetString(), Is.EqualTo("nothing to commit, working tree clean"));
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
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("exitCode").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result!.Value.GetProperty("succeeded").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("stderr").GetString(), Does.Contain("no se reconoce"));
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

    [Test]
    public async Task AKnownFolderNamesTheWorkingDirectoryAndAnythingElseIsRefused()
    {
        // Fase 5 (2026-09-21, H0048 «ejecuta pytest»): «cwd» is a known folder name (or a
        // subfolder of one) or an absolute path; a bare word is refused before running.
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
