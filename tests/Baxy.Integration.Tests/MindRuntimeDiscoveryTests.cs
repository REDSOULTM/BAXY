using Baxy.App;
using NUnit.Framework;
using System.Security.Cryptography;
using System.Text;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MindRuntimeDiscoveryTests
{
    [Test]
    [NonParallelizable]
    public void DevelopmentTreeIsNeverUsedAsAnImplicitRuntime()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-discovery-" + Guid.NewGuid());
        string[] names =
        [
            MindSidecarClient.DisabledEnvironmentVariable,
            MindSidecarClient.PythonEnvironmentVariable,
            MindSidecarClient.PythonPathEnvironmentVariable,
            "BAXY_MIND_LLM_GGUF",
            "BAXY_MIND_LLAMA_SERVER",
            "BAXY_MIND_STT_DIR",
        ];
        var previous = names.ToDictionary(
            name => name,
            Environment.GetEnvironmentVariable,
            StringComparer.Ordinal);
        try
        {
            foreach (string name in names)
            {
                Environment.SetEnvironmentVariable(name, null);
            }

            Touch(Path.Combine(root, "Baxy.slnx"));
            Touch(Path.Combine(root, "src", "baxy_mind", "__main__.py"));
            Touch(Path.Combine(
                root,
                "experiments",
                "mind_router_spike",
                ".venv",
                "Scripts",
                "python.exe"));
            Touch(Path.Combine(
                root,
                "legacy",
                "models",
                "artifacts",
                "gemma4-e2b",
                "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"));
            Touch(Path.Combine(
                root,
                "legacy",
                "models",
                "artifacts",
                "llama-b9980",
                "llama-server.exe"));

            bool configured = MindRuntimeDiscovery.TryConfigureCurrentProcess(
                Path.Combine(root, "missing-mind-runtime-v1.json"));

            Assert.Multiple(() =>
            {
                Assert.That(configured, Is.False);
                Assert.That(
                    Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable),
                    Is.Null);
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"), Is.Null);
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"), Is.Null);
            });
        }
        finally
        {
            foreach ((string name, string? value) in previous)
            {
                Environment.SetEnvironmentVariable(name, value);
            }

            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public void ExplicitInterpreterDoesNotRequireARegisteredRuntime()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-explicit-only-" + Guid.NewGuid());
        string[] names =
        [
            MindSidecarClient.DisabledEnvironmentVariable,
            MindSidecarClient.PythonEnvironmentVariable,
        ];
        var previous = names.ToDictionary(
            name => name,
            Environment.GetEnvironmentVariable,
            StringComparer.Ordinal);
        try
        {
            foreach (string name in names)
            {
                Environment.SetEnvironmentVariable(name, null);
            }

            string python = Touch(Path.Combine(root, "override", "python.exe"));
            Environment.SetEnvironmentVariable(
                MindSidecarClient.PythonEnvironmentVariable,
                python);

            bool configured = MindRuntimeDiscovery.TryConfigureCurrentProcess(
                Path.Combine(root, "missing-mind-runtime-v1.json"));

            Assert.Multiple(() =>
            {
                Assert.That(configured, Is.True);
                Assert.That(
                    Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable),
                    Is.EqualTo(python));
            });
        }
        finally
        {
            foreach ((string name, string? value) in previous)
            {
                Environment.SetEnvironmentVariable(name, value);
            }

            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public void RegisteredRuntimeRequiresAnExactCompleteManifest()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-registration-" + Guid.NewGuid());
        try
        {
            string python = Touch(Path.Combine(root, "venv", "python.exe"));
            string pythonPath = Path.Combine(root, "source");
            Touch(Path.Combine(pythonPath, "baxy_mind", "__main__.py"));
            string gguf = Touch(Path.Combine(root, "models", "gemma.gguf"));
            string server = Touch(Path.Combine(root, "llama", "llama-server.exe"));
            string stt = Path.Combine(root, "stt");
            foreach (string name in new[]
                     {
                         "encoder.int8.onnx",
                         "decoder.int8.onnx",
                         "joiner.int8.onnx",
                         "tokens.txt",
                     })
            {
                Touch(Path.Combine(stt, name));
            }

            string manifest = Path.Combine(root, "mind-runtime-v1.json");
            string wake = WriteRuntimeManifest(
                manifest,
                python,
                pythonPath,
                gguf,
                server,
                stt,
                99);

            MindRuntimeConfiguration? discovered = MindRuntimeDiscovery.LoadRegistered(manifest);

            Assert.That(discovered, Is.Not.Null);
            MindRuntimeConfiguration runtime = discovered!;
            Assert.Multiple(() =>
            {
                Assert.That(runtime.Python, Is.EqualTo(python));
                Assert.That(runtime.PythonPath, Is.EqualTo(pythonPath));
                Assert.That(runtime.SttDirectory, Is.EqualTo(stt));
                Assert.That(runtime.WakeManifest, Is.EqualTo(wake));
                Assert.That(runtime.GpuLayers, Is.EqualTo(99));
                Assert.That(runtime.WakeOnStart, Is.True);
            });

            File.AppendAllText(manifest, "\n");
            Assert.That(MindRuntimeDiscovery.LoadRegistered(manifest), Is.Not.Null);
            File.WriteAllText(manifest, "{}");
            Assert.That(MindRuntimeDiscovery.LoadRegistered(manifest), Is.Null);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public void RegisteredRuntimeRejectsUnknownFieldsAndMissingAssets()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-registration-bad-" + Guid.NewGuid());
        try
        {
            Directory.CreateDirectory(root);
            string manifest = Path.Combine(root, "mind-runtime-v1.json");
            File.WriteAllText(
                manifest,
                """
                {
                  "schema": "baxy-mind-runtime-v1",
                  "python": "C:\\missing\\python.exe",
                  "python_path": "C:\\missing\\src",
                  "gguf": "C:\\missing\\model.gguf",
                  "llama_server": "C:\\missing\\llama-server.exe",
                  "stt_dir": "C:\\missing\\stt",
                  "ngl": 99,
                  "wake_on_start": true,
                  "unexpected": true
                }
                """);

            Assert.That(MindRuntimeDiscovery.LoadRegistered(manifest), Is.Null);
            Assert.That(MindRuntimeDiscovery.LoadRegistered("relative.json"), Is.Null);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public void RegisteredRuntimeConfiguresPlannerVoiceAndWakeWithoutManualVariables()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-registration-env-" + Guid.NewGuid());
        string[] names =
        [
            MindSidecarClient.PythonEnvironmentVariable,
            MindSidecarClient.PythonPathEnvironmentVariable,
            "BAXY_MIND_LLM_GGUF",
            "BAXY_MIND_LLAMA_SERVER",
            "BAXY_MIND_STT_DIR",
            "BAXY_MIND_NGL",
            "BAXY_VOICE_WAKE_MANIFEST",
            "BAXY_VOICE_WAKE_CASCADE_MANIFEST",
            "BAXY_VOICE_WAKE_ON_START",
            "HF_HUB_OFFLINE",
        ];
        var previous = names.ToDictionary(
            name => name,
            Environment.GetEnvironmentVariable,
            StringComparer.Ordinal);
        try
        {
            foreach (string name in names)
            {
                Environment.SetEnvironmentVariable(name, null);
            }

            string python = Touch(Path.Combine(root, "venv", "python.exe"));
            string pythonPath = Path.Combine(root, "source");
            Touch(Path.Combine(pythonPath, "baxy_mind", "__main__.py"));
            string gguf = Touch(Path.Combine(root, "models", "gemma.gguf"));
            string server = Touch(Path.Combine(root, "llama", "llama-server.exe"));
            string stt = Path.Combine(root, "stt");
            foreach (string name in new[]
                     {
                         "encoder.int8.onnx",
                         "decoder.int8.onnx",
                         "joiner.int8.onnx",
                         "tokens.txt",
                     })
            {
                Touch(Path.Combine(stt, name));
            }

            string manifest = Path.Combine(root, "mind-runtime-v1.json");
            string wake = WriteRuntimeManifest(
                manifest,
                python,
                pythonPath,
                gguf,
                server,
                stt,
                42);

            bool configured = MindRuntimeDiscovery.TryConfigureCurrentProcess(manifest);

            Assert.That(configured, Is.True);
            Assert.Multiple(() =>
            {
                Assert.That(
                    Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable),
                    Is.EqualTo(python));
                Assert.That(
                    Environment.GetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable),
                    Is.EqualTo(pythonPath));
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"), Is.EqualTo(gguf));
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"), Is.EqualTo(server));
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"), Is.EqualTo(stt));
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_NGL"), Is.EqualTo("42"));
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_MANIFEST"),
                    Is.EqualTo(wake));
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_CASCADE_MANIFEST"),
                    Is.EqualTo(wake));
                Assert.That(Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START"), Is.EqualTo("1"));
                Assert.That(Environment.GetEnvironmentVariable("HF_HUB_OFFLINE"), Is.EqualTo("1"));
            });
        }
        finally
        {
            foreach ((string name, string? value) in previous)
            {
                Environment.SetEnvironmentVariable(name, value);
            }

            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public void RegisteredPromotedCascadeConfiguresTheCascadeResolver()
    {
        string root = Path.Combine(
            Path.GetTempPath(),
            "baxy-mind-registration-cascade-" + Guid.NewGuid());
        Dictionary<string, string?> previous = CaptureRuntimeEnvironment();
        try
        {
            ClearRuntimeEnvironment();
            RuntimeFixture runtime = CreateRuntimeFixture(
                root,
                wakeFileName: "baxy-wake-cascade-v1.promoted.json",
                wakeSchema: "baxy-wake-cascade-v1");

            bool configured = MindRuntimeDiscovery.TryConfigureCurrentProcess(runtime.Manifest);

            Assert.Multiple(() =>
            {
                Assert.That(configured, Is.True);
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_MANIFEST"),
                    Is.EqualTo(runtime.Wake));
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_CASCADE_MANIFEST"),
                    Is.EqualTo(runtime.Wake));
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START"),
                    Is.EqualTo("1"));
            });
        }
        finally
        {
            RestoreRuntimeEnvironment(previous);
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public void RegisteredRuntimeRejectsAHashVerifiedUnknownWakeSchema()
    {
        string root = Path.Combine(
            Path.GetTempPath(),
            "baxy-mind-registration-wake-schema-" + Guid.NewGuid());
        try
        {
            RuntimeFixture runtime = CreateRuntimeFixture(
                root,
                wakeSchema: "invented-wake-manifest-v1");

            Assert.That(
                MindRuntimeDiscovery.LoadRegistered(runtime.Manifest),
                Is.Null);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public void ExplicitInterpreterStillReceivesRegisteredVoicePaths()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-explicit-python-" + Guid.NewGuid());
        string[] names =
        [
            MindSidecarClient.PythonEnvironmentVariable,
            MindSidecarClient.PythonPathEnvironmentVariable,
            "BAXY_MIND_LLM_GGUF",
            "BAXY_MIND_LLAMA_SERVER",
            "BAXY_MIND_STT_DIR",
            "BAXY_MIND_NGL",
            "BAXY_VOICE_WAKE_MANIFEST",
            "BAXY_VOICE_WAKE_CASCADE_MANIFEST",
            "BAXY_VOICE_WAKE_ON_START",
            "HF_HUB_OFFLINE",
        ];
        var previous = names.ToDictionary(
            name => name,
            Environment.GetEnvironmentVariable,
            StringComparer.Ordinal);
        try
        {
            foreach (string name in names)
            {
                Environment.SetEnvironmentVariable(name, null);
            }

            string explicitPython = Touch(Path.Combine(root, "override", "python.exe"));
            string registeredPython = Touch(Path.Combine(root, "registered", "python.exe"));
            string pythonPath = Path.Combine(root, "source");
            Touch(Path.Combine(pythonPath, "baxy_mind", "__main__.py"));
            string gguf = Touch(Path.Combine(root, "models", "gemma.gguf"));
            string server = Touch(Path.Combine(root, "llama", "llama-server.exe"));
            string stt = Path.Combine(root, "stt");
            foreach (string name in new[]
                     {
                         "encoder.int8.onnx",
                         "decoder.int8.onnx",
                         "joiner.int8.onnx",
                         "tokens.txt",
                     })
            {
                Touch(Path.Combine(stt, name));
            }

            string manifest = Path.Combine(root, "mind-runtime-v1.json");
            WriteRuntimeManifest(
                manifest,
                registeredPython,
                pythonPath,
                gguf,
                server,
                stt,
                99);

            Environment.SetEnvironmentVariable(
                MindSidecarClient.PythonEnvironmentVariable,
                explicitPython);
            bool configured = MindRuntimeDiscovery.TryConfigureCurrentProcess(manifest);

            Assert.Multiple(() =>
            {
                Assert.That(configured, Is.True);
                Assert.That(
                    Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable),
                    Is.EqualTo(explicitPython));
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"), Is.EqualTo(stt));
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_NGL"), Is.EqualTo("99"));
                Assert.That(Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START"), Is.EqualTo("1"));
            });
        }
        finally
        {
            foreach ((string name, string? value) in previous)
            {
                Environment.SetEnvironmentVariable(name, value);
            }

            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public void DisabledMindCannotBeReenabledByAnExplicitInterpreterOrRegisteredRuntime()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-disabled-" + Guid.NewGuid());
        string[] names =
        [
            MindSidecarClient.DisabledEnvironmentVariable,
            MindSidecarClient.PythonEnvironmentVariable,
            MindSidecarClient.PythonPathEnvironmentVariable,
            "BAXY_MIND_LLM_GGUF",
            "BAXY_MIND_LLAMA_SERVER",
            "BAXY_MIND_STT_DIR",
            "BAXY_MIND_NGL",
            "BAXY_VOICE_WAKE_MANIFEST",
            "BAXY_VOICE_WAKE_CASCADE_MANIFEST",
            "BAXY_VOICE_WAKE_ON_START",
            "HF_HUB_OFFLINE",
        ];
        var previous = names.ToDictionary(
            name => name,
            Environment.GetEnvironmentVariable,
            StringComparer.Ordinal);
        try
        {
            foreach (string name in names)
            {
                Environment.SetEnvironmentVariable(name, null);
            }

            string explicitPython = Touch(Path.Combine(root, "override", "python.exe"));
            string registeredPython = Touch(Path.Combine(root, "registered", "python.exe"));
            string pythonPath = Path.Combine(root, "source");
            Touch(Path.Combine(pythonPath, "baxy_mind", "__main__.py"));
            string gguf = Touch(Path.Combine(root, "models", "gemma.gguf"));
            string server = Touch(Path.Combine(root, "llama", "llama-server.exe"));
            string stt = Path.Combine(root, "stt");
            foreach (string name in new[]
                     {
                         "encoder.int8.onnx",
                         "decoder.int8.onnx",
                         "joiner.int8.onnx",
                         "tokens.txt",
                     })
            {
                Touch(Path.Combine(stt, name));
            }

            string manifest = Path.Combine(root, "mind-runtime-v1.json");
            WriteRuntimeManifest(
                manifest,
                registeredPython,
                pythonPath,
                gguf,
                server,
                stt,
                99);

            Environment.SetEnvironmentVariable(
                MindSidecarClient.PythonEnvironmentVariable,
                explicitPython);
            Environment.SetEnvironmentVariable(
                MindSidecarClient.DisabledEnvironmentVariable,
                "1");

            bool configured = MindRuntimeDiscovery.TryConfigureCurrentProcess(manifest);

            Assert.Multiple(() =>
            {
                Assert.That(configured, Is.False);
                Assert.That(MindSidecarClient.IsConfigured, Is.False);
                Assert.That(
                    Environment.GetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable),
                    Is.Null);
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"), Is.Null);
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"), Is.Null);
                Assert.That(Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START"), Is.Null);
            });
        }
        finally
        {
            foreach ((string name, string? value) in previous)
            {
                Environment.SetEnvironmentVariable(name, value);
            }

            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public void RegisteredRuntimeRejectsAnyDeclaredAssetWhoseHashChanged()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-hash-" + Guid.NewGuid());
        try
        {
            string python = Touch(Path.Combine(root, "venv", "python.exe"));
            string pythonPath = Path.Combine(root, "source");
            Touch(Path.Combine(pythonPath, "baxy_mind", "__main__.py"));
            string gguf = Touch(Path.Combine(root, "models", "gemma.gguf"));
            string server = Touch(Path.Combine(root, "llama", "llama-server.exe"));
            string stt = Path.Combine(root, "stt");
            foreach (string name in SttFiles)
            {
                Touch(Path.Combine(stt, name));
            }
            string manifest = Path.Combine(root, "mind-runtime-v1.json");
            WriteRuntimeManifest(manifest, python, pythonPath, gguf, server, stt, 99);
            Assert.That(MindRuntimeDiscovery.LoadRegistered(manifest), Is.Not.Null);

            File.AppendAllText(gguf, "changed");

            Assert.That(MindRuntimeDiscovery.LoadRegistered(manifest), Is.Null);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public void DiscoverVerifiedDoesNotPublishUntilApplyVerified()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-split-" + Guid.NewGuid());
        Dictionary<string, string?> previous = CaptureRuntimeEnvironment();
        try
        {
            ClearRuntimeEnvironment();
            RuntimeFixture runtime = CreateRuntimeFixture(root);

            MindRuntimeDiscoveryResult discovery =
                MindRuntimeDiscovery.DiscoverVerified(runtime.Manifest);

            Assert.Multiple(() =>
            {
                Assert.That(discovery.CanConfigure, Is.True);
                Assert.That(discovery.Runtime, Is.Not.Null);
                Assert.That(MindSidecarClient.IsConfigured, Is.False);
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
                    Is.Null);
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"),
                    Is.Null);
            });

            bool applied = MindRuntimeDiscovery.ApplyVerified(discovery);

            Assert.Multiple(() =>
            {
                Assert.That(applied, Is.True);
                Assert.That(MindSidecarClient.IsConfigured, Is.True);
                Assert.That(
                    Environment.GetEnvironmentVariable(
                        MindSidecarClient.PythonEnvironmentVariable),
                    Is.EqualTo(runtime.Python));
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
                    Is.EqualTo(runtime.Gguf));
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"),
                    Is.EqualTo(runtime.Stt));
            });
        }
        finally
        {
            RestoreRuntimeEnvironment(previous);
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public void ApplyVerifiedHonorsALateDisableVetoWithoutPartialPublication()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-veto-" + Guid.NewGuid());
        Dictionary<string, string?> previous = CaptureRuntimeEnvironment();
        try
        {
            ClearRuntimeEnvironment();
            RuntimeFixture runtime = CreateRuntimeFixture(root);
            MindRuntimeDiscoveryResult discovery =
                MindRuntimeDiscovery.DiscoverVerified(runtime.Manifest);

            Environment.SetEnvironmentVariable(
                MindSidecarClient.DisabledEnvironmentVariable,
                "1");
            bool applied = MindRuntimeDiscovery.ApplyVerified(discovery);

            Assert.Multiple(() =>
            {
                Assert.That(applied, Is.False);
                Assert.That(MindSidecarClient.IsConfigured, Is.False);
                Assert.That(
                    Environment.GetEnvironmentVariable(
                        MindSidecarClient.PythonEnvironmentVariable),
                    Is.Null);
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
                    Is.Null);
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"),
                    Is.Null);
            });
        }
        finally
        {
            RestoreRuntimeEnvironment(previous);
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public void ApplyVerifiedRejectsAnOverrideChangedDuringVerification()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-race-" + Guid.NewGuid());
        Dictionary<string, string?> previous = CaptureRuntimeEnvironment();
        try
        {
            ClearRuntimeEnvironment();
            RuntimeFixture runtime = CreateRuntimeFixture(root);
            MindRuntimeDiscoveryResult discovery =
                MindRuntimeDiscovery.DiscoverVerified(runtime.Manifest);

            Environment.SetEnvironmentVariable("BAXY_MIND_NGL", "0");
            bool applied = MindRuntimeDiscovery.ApplyVerified(discovery);

            Assert.Multiple(() =>
            {
                Assert.That(applied, Is.False);
                Assert.That(MindSidecarClient.IsConfigured, Is.False);
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_MIND_NGL"),
                    Is.EqualTo("0"));
                Assert.That(
                    Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
                    Is.Null);
            });
        }
        finally
        {
            RestoreRuntimeEnvironment(previous);
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    [NonParallelizable]
    public async Task PendingDiscoveryCannotPublishOrCreateASidecarAndCancellationStaysFailClosed()
    {
        Dictionary<string, string?> previous = CaptureRuntimeEnvironment();
        try
        {
            ClearRuntimeEnvironment();
            var discovery =
                new TaskCompletionSource<MindRuntimeDiscoveryResult>(
                    TaskCreationOptions.RunContinuationsAsynchronously);
            using var cancellation = new CancellationTokenSource();
            int factoryCalls = 0;
            await using var viewModel = new MainWindowViewModel(
                testTurnResolver: null,
                mindClientFactory: () =>
                {
                    Interlocked.Increment(ref factoryCalls);
                    return new MindSidecarClient();
                });

            Task initialization = viewModel.InitializeMindAsync(
                discovery.Task,
                cancellation.Token);

            Assert.Multiple(() =>
            {
                Assert.That(initialization.IsCompleted, Is.False);
                Assert.That(Volatile.Read(ref factoryCalls), Is.Zero);
                Assert.That(MindSidecarClient.IsConfigured, Is.False);
            });

            cancellation.Cancel();
            OperationCanceledException? cancellationException = null;
            try
            {
                await initialization;
            }
            catch (OperationCanceledException exception)
            {
                cancellationException = exception;
            }
            Assert.Multiple(() =>
            {
                Assert.That(cancellationException, Is.Not.Null);
                Assert.That(Volatile.Read(ref factoryCalls), Is.Zero);
                Assert.That(MindSidecarClient.IsConfigured, Is.False);
            });
        }
        finally
        {
            RestoreRuntimeEnvironment(previous);
        }
    }

    [Test]
    [NonParallelizable]
    public async Task ApplyVerifiedCompletesBeforeTheSidecarFactoryCanRun()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-mind-order-" + Guid.NewGuid());
        Dictionary<string, string?> previous = CaptureRuntimeEnvironment();
        try
        {
            ClearRuntimeEnvironment();
            RuntimeFixture runtime = CreateRuntimeFixture(root);
            MindRuntimeDiscoveryResult discovery =
                MindRuntimeDiscovery.DiscoverVerified(runtime.Manifest);
            int factoryCalls = 0;
            await using var viewModel = new MainWindowViewModel(
                testTurnResolver: null,
                mindClientFactory: () =>
                {
                    Interlocked.Increment(ref factoryCalls);
                    Assert.Multiple(() =>
                    {
                        Assert.That(MindSidecarClient.IsConfigured, Is.True);
                        Assert.That(
                            Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
                            Is.EqualTo(runtime.Gguf));
                        Assert.That(
                            Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"),
                            Is.EqualTo(runtime.Stt));
                    });
                    throw new InvalidOperationException("stop-before-process-start");
                });

            Task initialization = viewModel.InitializeMindAsync(
                Task.FromResult(discovery),
                CancellationToken.None);

            InvalidOperationException? exception = Assert.ThrowsAsync<InvalidOperationException>(
                async () => await initialization);
            Assert.Multiple(() =>
            {
                Assert.That(exception?.Message, Is.EqualTo("stop-before-process-start"));
                Assert.That(Volatile.Read(ref factoryCalls), Is.EqualTo(1));
            });
        }
        finally
        {
            RestoreRuntimeEnvironment(previous);
            Directory.Delete(root, recursive: true);
        }
    }

    private static readonly string[] SttFiles =
    [
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    ];

    private static readonly string[] RuntimeEnvironmentNames =
    [
        MindSidecarClient.DisabledEnvironmentVariable,
        MindSidecarClient.PythonEnvironmentVariable,
        MindSidecarClient.PythonPathEnvironmentVariable,
        "BAXY_MIND_LLM_GGUF",
        "BAXY_MIND_LLAMA_SERVER",
        "BAXY_MIND_STT_DIR",
        "BAXY_MIND_NGL",
        "BAXY_VOICE_WAKE_MANIFEST",
        "BAXY_VOICE_WAKE_CASCADE_MANIFEST",
        "BAXY_VOICE_WAKE_ON_START",
        "HF_HUB_OFFLINE",
        "BAXY_ASSET_DESCRIPTOR",
    ];

    private static Dictionary<string, string?> CaptureRuntimeEnvironment() =>
        RuntimeEnvironmentNames.ToDictionary(
            static name => name,
            Environment.GetEnvironmentVariable,
            StringComparer.Ordinal);

    private static void ClearRuntimeEnvironment()
    {
        foreach (string name in RuntimeEnvironmentNames)
        {
            Environment.SetEnvironmentVariable(name, null);
        }
    }

    private static void RestoreRuntimeEnvironment(
        IReadOnlyDictionary<string, string?> previous)
    {
        foreach ((string name, string? value) in previous)
        {
            Environment.SetEnvironmentVariable(name, value);
        }
    }

    private static RuntimeFixture CreateRuntimeFixture(
        string root,
        string wakeFileName = "baxy-wakeword-v1.json",
        string wakeSchema = "baxy-wakeword-v1")
    {
        string python = Touch(Path.Combine(root, "venv", "python.exe"));
        string pythonPath = Path.Combine(root, "source");
        Touch(Path.Combine(pythonPath, "baxy_mind", "__main__.py"));
        string gguf = Touch(Path.Combine(root, "models", "gemma.gguf"));
        string server = Touch(Path.Combine(root, "llama", "llama-server.exe"));
        string stt = Path.Combine(root, "stt");
        foreach (string name in SttFiles)
        {
            Touch(Path.Combine(stt, name));
        }
        string manifest = Path.Combine(root, "mind-runtime-v1.json");
        string wake = WriteRuntimeManifest(
            manifest,
            python,
            pythonPath,
            gguf,
            server,
            stt,
            42,
            wakeFileName,
            wakeSchema);
        return new(manifest, python, gguf, stt, wake);
    }

    private static string WriteRuntimeManifest(
        string manifest,
        string python,
        string pythonPath,
        string gguf,
        string server,
        string stt,
        int ngl,
        string wakeFileName = "baxy-wakeword-v1.json",
        string wakeSchema = "baxy-wakeword-v1")
    {
        string wake = Path.Combine(
            Path.GetDirectoryName(manifest)!,
            "wake",
            wakeFileName);
        Directory.CreateDirectory(Path.GetDirectoryName(wake)!);
        File.WriteAllText(
            wake,
            System.Text.Json.JsonSerializer.Serialize(new { schema = wakeSchema }));
        wake = Path.GetFullPath(wake);
        File.WriteAllText(
            manifest,
            $$"""
            {
              "schema": "baxy-mind-runtime-v1",
              "python": {{Json(python)}},
              "python_sha256": {{Json(Sha256(python))}},
              "python_path": {{Json(pythonPath)}},
              "gguf": {{Json(gguf)}},
              "gguf_sha256": {{Json(Sha256(gguf))}},
              "llama_server": {{Json(server)}},
              "llama_server_sha256": {{Json(Sha256(server))}},
              "stt_dir": {{Json(stt)}},
              "stt_sha256": {{Json(SttSha256(stt))}},
              "wake_manifest": {{Json(wake)}},
              "wake_manifest_sha256": {{Json(Sha256(wake))}},
              "tts_model": null,
              "tts_sha256": null,
              "ngl": {{ngl}},
              "wake_on_start": true
            }
            """);
        return wake;
    }

    private static string SttSha256(string directory)
    {
        var value = new StringBuilder();
        foreach (string name in SttFiles)
        {
            value.Append(name).Append(':').Append(Sha256(Path.Combine(directory, name))).Append('\n');
        }
        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value.ToString())));
    }

    private static string Sha256(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }

    private static string Touch(string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllBytes(path, [1]);
        return Path.GetFullPath(path);
    }

    private static string Json(string value) =>
        System.Text.Json.JsonSerializer.Serialize(value);

    private sealed record RuntimeFixture(
        string Manifest,
        string Python,
        string Gguf,
        string Stt,
        string Wake);
}
