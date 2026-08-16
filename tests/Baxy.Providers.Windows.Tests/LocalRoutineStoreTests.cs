using System.Globalization;
using Baxy.Providers.Windows.Routines;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class LocalRoutineStoreTests
{
    [Test]
    public void TrustedSeedLifecycleUsesCasAndNeverExecutesWorkflow()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalRoutineStore(temporary.Path);
        RoutineRecord created = store.CreateTrusted(
            "Copia diaria", "backup.exact", "1", ["source"], "manual", null);
        RoutineRecord resolved = store.ResolveExact("copia diaria", false);
        RoutineRecord disabled = store.SetEnabled(created.Id, created.Revision, false);
        RoutineRecord deleted = store.Delete(disabled.Id, disabled.Revision, disabled.Name);
        RoutineRecord restored = store.Restore(deleted.Id, deleted.Revision);

        Assert.Multiple(() =>
        {
            Assert.That(resolved.Id, Is.EqualTo(created.Id));
            Assert.That(resolved.Revision, Is.EqualTo(created.Revision));
            Assert.That(resolved.InputFields, Is.EqualTo(created.InputFields));
            Assert.That(disabled.Enabled, Is.False);
            Assert.That(deleted.Deleted, Is.True);
            Assert.That(restored.Deleted, Is.False);
            Assert.That(restored.Enabled, Is.False);
            Assert.That(restored.WorkflowId, Is.EqualTo("backup.exact"));
        });
    }

    [Test]
    public void PhraseRoutineNormalizesTriggerAndConstrainsWorkflowToMediaToggle()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalRoutineStore(temporary.Path);

        RoutineRecord created = store.CreatePhrase("Alternar música", "  TIÉMPO!!!  ");

        Assert.Multiple(() =>
        {
            Assert.That(created.TriggerKind, Is.EqualTo("on_phrase"));
            Assert.That(created.WorkflowId, Is.EqualTo("media.control"));
            Assert.That(created.WorkflowVersion, Is.EqualTo("1"));
            Assert.That(created.InputFields, Is.EqualTo(new[] { "action=toggle", "phrase=tiempo" }));
            Assert.That(created.Enabled, Is.True);
        });
    }

    [Test]
    public void PhraseRoutineCanBindTheTrustedScreenshotWorkflow()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalRoutineStore(temporary.Path);

        RoutineRecord created = store.CreatePhrase(
            "Capturar evidencia",
            "  PANTALLAZO!!!  ",
            "capture.screenshot");

        Assert.Multiple(() =>
        {
            Assert.That(created.TriggerKind, Is.EqualTo("on_phrase"));
            Assert.That(created.WorkflowId, Is.EqualTo("capture.screenshot"));
            Assert.That(created.WorkflowVersion, Is.EqualTo("1"));
            Assert.That(created.InputFields, Is.EqualTo(new[] { "phrase=pantallazo" }));
            Assert.That(created.Enabled, Is.True);
        });
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-routine-tests",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture));
            Directory.CreateDirectory(Path);
        }
        public string Path { get; }
        public void Dispose() { if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true); }
    }
}
