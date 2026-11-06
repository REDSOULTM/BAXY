using System.Diagnostics;
using Baxy.Contracts;
using Baxy.Core;
using Baxy.Kernel.Journal;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso 85 (notebook, Steam session): a profile of another version or with keys this account cannot open stopped the core
/// at every start (exit 70, «stopped safely») and the App relaunched it for ever. A start a local store stops ends with
/// its own code (CoreExitCodes.ProfileUnreadable), which the App treats as terminal; nothing of the profile is touched.
/// </summary>
[TestFixture]
public sealed class UnreadableProfileTests
{
    [Test]
    public async Task ACoreWhoseMemoryWasSealedByAnotherKeySaysTheProfileIsUnreadable()
    {
        using var profile = new Profile();
        // The memory a profile of another installation left: sealed by a key this profile does not hold.
        var otherKey = new WindowsProtectedPayload(Path.Combine(profile.Other, "security", "private-payload.v1.key"));
        _ = new LocalMemoryStore(Path.Combine(profile.Root, "memory-store"), otherKey);
        string[] before = profile.Files();

        (int exit, string stderr) = await RunCoreAsync(profile.Root);

        Assert.Multiple(() =>
        {
            Assert.That(exit, Is.EqualTo(CoreExitCodes.ProfileUnreadable), stderr);
            Assert.That(stderr, Does.Contain("MemoryStoreCorruptException"));
            Assert.That(profile.Files(), Is.SupersetOf(before), "nothing the profile held is removed");
        });
    }

    [Test]
    public async Task ACoreWhoseKeyStoreCannotBeOpenedSaysTheProfileIsUnreadable()
    {
        using var profile = new Profile();
        string keyPath = Path.Combine(profile.Root, "security", "private-payload.v1.key");
        _ = new WindowsProtectedPayload(keyPath).Seal("x"u8, "test.seal");
        byte[] key = File.ReadAllBytes(keyPath);
        key[^1] ^= 0x5A;  // the key file of another version: its DPAPI blob is not this one's
        using (var stream = new FileStream(keyPath, FileMode.Open, FileAccess.Write, FileShare.None))
        {
            stream.Write(key);
        }

        (int exit, string stderr) = await RunCoreAsync(profile.Root);

        Assert.Multiple(() =>
        {
            Assert.That(exit, Is.EqualTo(CoreExitCodes.ProfileUnreadable), stderr);
            Assert.That(stderr, Does.Contain("ProtectedPayloadException"));
            Assert.That(File.ReadAllBytes(keyPath), Is.EqualTo(key), "the key is kept as it was");
        });
    }

    [Test]
    public void OnlyAStoreThatCannotBeReadOrTrustedIsTheProfiles()
    {
        using var profile = new Profile();
        string keyPath = Path.Combine(profile.Root, "security", "private-payload.v1.key");
        byte[] sealedValue = new WindowsProtectedPayload(keyPath).Seal("x"u8, "test.seal");
        ProtectedPayloadException wrongKey = Assert.Throws<ProtectedPayloadException>(
            () => new WindowsProtectedPayload(Path.Combine(profile.Other, "security", "k.key")).Open(sealedValue, "test.seal"))!;

        Assert.Multiple(() =>
        {
            Assert.That(UnreadableProfile.Is(new MemoryStoreCorruptException()), Is.True);
            Assert.That(UnreadableProfile.Is(wrongKey), Is.True);
            Assert.That(UnreadableProfile.Is(new JournalIntegrityException("bad")), Is.True);
            Assert.That(UnreadableProfile.Is(new InvalidOperationException("start", new MemoryStoreCorruptException())), Is.True);
            Assert.That(UnreadableProfile.Is(new IOException("disk")), Is.False);
            Assert.That(UnreadableProfile.Is(new UnsafeMemoryStorePathException()), Is.False);
            Assert.That(UnreadableProfile.Is(new OperationCanceledException()), Is.False);
        });
    }

    // DPAPI opens only what the same logon credentials protected on the same computer: in a session where it protects
    // nothing (the notebook over SSH), a store that cannot be opened says nothing about the profile.
    [Test]
    public void AStoreUnreadableOnlyBecauseTheSessionCannotProtectIsNoProfileVerdict()
    {
        Assert.Multiple(() =>
        {
            Assert.That(UnreadableProfile.ExitCode(() => true), Is.EqualTo(CoreExitCodes.ProfileUnreadable));
            Assert.That(UnreadableProfile.ExitCode(() => false), Is.EqualTo(UnreadableProfile.StoppedSafely));
            Assert.That(WindowsProtectedPayload.CurrentUserProtectionWorks(), Is.True,
                "this desktop session protects and opens its own secrets");
        });
    }

    private static async Task<(int Exit, string Stderr)> RunCoreAsync(string dataRoot)
    {
        var start = new ProcessStartInfo(Path.Combine(AppContext.BaseDirectory, "baxy-core.exe"))
        {
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.Environment["BAXY_DATA_DIR"] = dataRoot;
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("baxy-core did not start");
        Task<string> stdout = process.StandardOutput.ReadToEndAsync();
        Task<string> stderr = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException)
        {
            process.Kill(entireProcessTree: true);  // this test's own process, by its handle
            throw new TimeoutException("baxy-core kept running on an unreadable profile: " + await stdout);
        }

        // N3: the core is gone, so the end of its pipes is due now; a child that kept them is a defect of the core's, not a
        // wait for ever (ChildProcessHandles).
        using var ended = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        try
        {
            _ = await stdout.WaitAsync(ended.Token);
            return (process.ExitCode, await stderr.WaitAsync(ended.Token));
        }
        catch (OperationCanceledException)
        {
            Assert.Fail("baxy-core exited and a process it started still holds its output");
            throw;
        }
    }

    // A data root is a direct child of %LOCALAPPDATA%\BAXY (WindowsPrivateStorage): these are the test's own, never «1».
    private sealed class Profile : IDisposable
    {
        internal Profile()
        {
            string baxy = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY");
            string name = $"prueba-ilegible-{Guid.NewGuid():N}";
            Root = WindowsPrivateStorage.PreparePrivateDataRoot(Path.Combine(baxy, name));
            Other = WindowsPrivateStorage.PreparePrivateDataRoot(Path.Combine(baxy, name + "-otra"));
        }

        internal string Root { get; }

        internal string Other { get; }

        internal string[] Files() =>
            Directory.GetFiles(Root, "*", SearchOption.AllDirectories)
                .Select(path => Path.GetRelativePath(Root, path))
                .ToArray();

        public void Dispose()
        {
            foreach (string directory in new[] { Root, Other })
            {
                if (Directory.Exists(directory))
                {
                    Directory.Delete(directory, recursive: true);
                }
            }
        }
    }
}
