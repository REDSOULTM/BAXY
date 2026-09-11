"""One-shot temporary instrumentation of the actual failing startup fixture."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'artifacts/comprobaciones/C03/astra-fixture-startup-probe709'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-fixture-startup709-private'
FIXTURE = ROOT / 'tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs'
HELPER = ROOT / 'tests/Baxy.Integration.Tests/TemporaryStartupProbe709.cs'
STACK = Path(os.environ['TEMP']) / 'c03-dotnet-diagnostics705/dotnet-stack.exe'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

assert not PUBLIC.exists() and not PRIVATE.exists() and not HELPER.exists()
assert STACK.is_file()
assert not any(p.info['name'] and p.info['name'].lower() in {'testhost.exe', 'baxy-core.exe', 'llama-server.exe'}
               for p in psutil.process_iter(['name'])), 'Other tests/Core/inference active'
original = FIXTURE.read_bytes()
assert hashlib.sha256(original).hexdigest() == '628ab599ecae26227707d479220bbab41a06f17e9a3980c828c8dd6c45119ae3'
PUBLIC.mkdir()
PRIVATE.mkdir()
(PUBLIC / 'MindShellEndToEndTests.before.cs.txt').write_bytes(original)
newline = b'\r\n' if b'\r\n' in original else b'\n'
needle = newline.join([
    b'            await using var viewModel = new MainWindowViewModel();',
    b'            await viewModel.InitializeAsync(CancellationToken.None);',
    b'            Assert.Multiple(() =>',
])
replacement = newline.join([
    b'            await using var viewModel = new MainWindowViewModel();',
    b'            using (TemporaryStartupProbe709.Observe(viewModel))',
    b'            {',
    b'                await viewModel.InitializeAsync(CancellationToken.None);',
    b'            }',
    b'            Assert.Multiple(() =>',
])
assert original.count(needle) == 1
instrumented = original.replace(needle, replacement)
helper = r'''using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.ExceptionServices;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class TemporaryStartupProbe709
{
    [Test]
    public async Task FiftyColdStartsUsingTheActualContractFixture()
    {
        MethodInfo method = typeof(MindShellEndToEndTests).GetMethod(
            "WithContractMindAsync", BindingFlags.Static | BindingFlags.NonPublic)!;
        Func<MainWindowViewModel, string, string, Task> body = (_, _, _) => Task.CompletedTask;
        for (int index = 0; index < 50; index++)
        {
            TestContext.Progress.WriteLine($"Startup709 trial {index + 1}/50");
            await (Task)method.Invoke(null, new object[] { body })!;
        }
    }

    internal static IDisposable Observe(MainWindowViewModel viewModel) => new Observation(viewModel);

    private sealed class Observation : IDisposable
    {
        private readonly MainWindowViewModel _viewModel;
        private readonly Stopwatch _elapsed = Stopwatch.StartNew();
        private readonly string _directory;
        private readonly List<string> _exceptions = new();
        private int _captured;

        internal Observation(MainWindowViewModel viewModel)
        {
            _viewModel = viewModel;
            _directory = Path.Combine(
                Environment.GetEnvironmentVariable("C03_STARTUP_PROBE_DIRECTORY")!,
                $"startup-{DateTime.UtcNow:yyyyMMddTHHmmssfffffff}");
            Directory.CreateDirectory(_directory);
            AppDomain.CurrentDomain.FirstChanceException += Capture;
        }

        private void Capture(object? sender, FirstChanceExceptionEventArgs args)
        {
            if (args.Exception is not TimeoutException
                || args.Exception.Message != "El core no emitió el saludo local a tiempo."
                || Interlocked.Exchange(ref _captured, 1) != 0)
            {
                return;
            }

            // Runs after the unchanged deadline expired, before the App disposes its Core.
            try
            {
                File.WriteAllText(Path.Combine(_directory, "exception.txt"), args.Exception.ToString());
                object client = typeof(MainWindowViewModel).GetField(
                    "_coreClient", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(_viewModel)!;
                var core = (Process)client.GetType().GetField(
                    "_process", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(client)!;
                File.WriteAllText(Path.Combine(_directory, "timeout.json"), JsonSerializer.Serialize(new
                {
                    secondsBeforeDiagnostic = _elapsed.Elapsed.TotalSeconds,
                    corePid = core.Id,
                    coreStartUtc = core.StartTime.ToUniversalTime(),
                    coreHasExited = core.HasExited,
                }));
                if (core.HasExited)
                {
                    return;
                }

                var start = new ProcessStartInfo
                {
                    FileName = Environment.GetEnvironmentVariable("C03_STARTUP_STACK_TOOL")!,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                };
                start.ArgumentList.Add("report");
                start.ArgumentList.Add("--process-id");
                start.ArgumentList.Add(core.Id.ToString(System.Globalization.CultureInfo.InvariantCulture));
                using Process report = Process.Start(start)!;
                Task<string> output = report.StandardOutput.ReadToEndAsync();
                Task<string> error = report.StandardError.ReadToEndAsync();
                bool finished = report.WaitForExit(15_000);
                if (!finished)
                {
                    report.Kill(entireProcessTree: true);
                    report.WaitForExit(5_000);
                }

                bool drained = Task.WaitAll(new Task[] { output, error }, 5_000);
                File.WriteAllText(Path.Combine(_directory, "stack-result.json"), JsonSerializer.Serialize(new
                {
                    finished,
                    drained,
                    exitCode = report.HasExited ? report.ExitCode : (int?)null,
                }));
                if (drained)
                {
                    File.WriteAllText(Path.Combine(_directory, "managed-stack.txt"), output.Result);
                    File.WriteAllText(Path.Combine(_directory, "stack-stderr.txt"), error.Result);
                }
            }
            catch (Exception error)
            {
                _exceptions.Add(error.ToString());
            }
        }

        public void Dispose()
        {
            AppDomain.CurrentDomain.FirstChanceException -= Capture;
            File.WriteAllText(Path.Combine(_directory, "result.json"), JsonSerializer.Serialize(new
            {
                seconds = _elapsed.Elapsed.TotalSeconds,
                _viewModel.IsReady,
                _viewModel.HasStartupError,
                captured = _captured != 0,
                diagnosticErrors = _exceptions,
            }));
        }
    }
}
'''
command = ['dotnet', 'test', 'tests/Baxy.Integration.Tests', '-c', 'Release', '--nologo', '-v:minimal',
           '--filter', 'FullyQualifiedName~TemporaryStartupProbe709', '--logger', 'console;verbosity=normal']
write(PUBLIC / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'command': command,
    'maximum_startups': 50, 'stop': 'First real fixture failure; do not retry to obtain a pass.',
    'method': 'Actual WithContractMindAsync including parallel Mind discovery and its stdlib Python fixture. No turns or LLM. Subscribe around InitializeAsync to the exact Core handshake TimeoutException; capture owned Core stack before App disposal, only after the original 10-second deadline expired. Observe process descendants every 250 ms; private raw logs. This is diagnosis, not acceptance.',
    'fixture_before_sha256': sha(FIXTURE), 'candidate': '../astra-window-vocabulary-source705/CANDIDATE4.json',
    'stack_tool_sha256': sha(STACK), 'stack_tool_version': '10.0.731102',
    'stack_docs': 'https://learn.microsoft.com/en-us/dotnet/core/diagnostics/dotnet-stack',
    'coverage_added': 0, 'goal_complete': False,
})
env = dict(os.environ, C03_STARTUP_PROBE_DIRECTORY=str(PRIVATE), C03_STARTUP_STACK_TOOL=str(STACK))
FIXTURE.write_bytes(instrumented)
HELPER.write_text(helper, encoding='utf-8')
helper_hash = sha(HELPER)
(PUBLIC / 'TemporaryStartupProbe709.cs.txt').write_bytes(HELPER.read_bytes())
(PUBLIC / 'MindShellEndToEndTests.instrumented.cs.txt').write_bytes(instrumented)
proc = None
try:
    with (PUBLIC / 'TEST.log').open('w', encoding='utf-8') as log, (PRIVATE / 'process-samples.jsonl').open('w', encoding='utf-8') as samples:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        owner = psutil.Process(proc.pid)
        while proc.poll() is None:
            sample = {'utc': datetime.now(timezone.utc).isoformat(),
                      'available_ram_mib': psutil.virtual_memory().available / 2**20, 'processes': []}
            try:
                for child in owner.children(recursive=True):
                    try:
                        sample['processes'].append({'pid': child.pid, 'ppid': child.ppid(), 'name': child.name(),
                                                    'created': child.create_time(), 'command': child.cmdline(),
                                                    'cpu_seconds': sum(child.cpu_times()[:2]),
                                                    'rss_mib': child.memory_info().rss / 2**20})
                    except psutil.Error:
                        pass
            except psutil.Error:
                pass
            samples.write(json.dumps(sample) + '\n')
            samples.flush()
            time.sleep(.25)
finally:
    assert FIXTURE.read_bytes() == instrumented, 'Concurrent fixture edit: do not overwrite'
    assert sha(HELPER) == helper_hash, 'Concurrent diagnostic edit: do not remove'
    FIXTURE.write_bytes(original)
    assert HELPER.resolve().is_relative_to(ROOT.resolve())
    HELPER.unlink()
    write(PUBLIC / 'EXIT.json', {'utc': datetime.now(timezone.utc).isoformat(),
                               'exit_code': proc.returncode if proc else None,
                               'fixture_restored': FIXTURE.read_bytes() == original,
                               'temporary_helper_removed': not HELPER.exists(),
                               'test_binary_contains_diagnostics_until_next_build': True})
print((PUBLIC / 'EXIT.json').read_text(encoding='utf-8'), flush=True)
