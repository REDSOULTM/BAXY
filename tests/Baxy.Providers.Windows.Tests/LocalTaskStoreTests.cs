using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;
using System.Globalization;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class LocalTaskStoreTests
{
    [Test]
    public void LifecycleUsesCasAndRecoverableDeletion()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        LocalTaskRecord created = store.Create(
            "Revisar BAXY",
            "ejecutar pruebas",
            "2026-07-20T09:00:00-04:00");

        LocalTaskRecord resolved = store.ResolveExact("revisar baxy", false);
        LocalTaskRecord completed = store.SetCompleted(created.Id, created.Version, true);
        LocalTaskRecord deleted = store.Delete(completed.Id, completed.Version, completed.Title);
        LocalTaskRecord restored = store.Restore(deleted.Id, deleted.Version);
        LocalTaskRecord reopened = store.SetCompleted(restored.Id, restored.Version, false);

        Assert.Multiple(() =>
        {
            Assert.That(resolved, Is.EqualTo(created));
            Assert.That(completed.Completed, Is.True);
            Assert.That(completed.CompletedAtUtc, Is.Not.Null);
            Assert.That(deleted.Deleted, Is.True);
            Assert.That(restored.Deleted, Is.False);
            Assert.That(reopened.Completed, Is.False);
            Assert.That(reopened.CompletedAtUtc, Is.Null);
            Assert.That(reopened.Version, Is.EqualTo(5));
            Assert.That(
                () => store.SetCompleted(created.Id, created.Version, true),
                Throws.TypeOf<LocalTaskVersionConflictException>());
        });
    }

    [Test]
    public void SearchIsBoundedToTitleAndDetailsAndStatus()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        LocalTaskRecord open = store.Create("Atlas", "documentar", null);
        LocalTaskRecord done = store.Create("Otra", "validar atlas", null);
        store.SetCompleted(done.Id, done.Version, true);

        IReadOnlyList<LocalTaskRecord> all = store.Search("ATLAS", TaskListStatus.All, 10);
        IReadOnlyList<LocalTaskRecord> openOnly = store.Search("atlas", TaskListStatus.Open, 10);

        Assert.Multiple(() =>
        {
            Assert.That(all.Select(static task => task.Id), Is.EquivalentTo(new[] { open.Id, done.Id }));
            Assert.That(openOnly.Select(static task => task.Id), Is.EqualTo(new[] { open.Id }));
            Assert.That(store.Search("details", TaskListStatus.All, 10), Is.Empty);
        });
    }

    [Test]
    public void UpdateRequiresExactVersionAndPersistsAcrossRestart()
    {
        using TemporaryDirectory temporary = new();
        string root = Path.Combine(temporary.Path, "tasks");
        var first = new LocalTaskStore(root);
        LocalTaskRecord created = first.Create("Uno", string.Empty, null);
        LocalTaskRecord updated = first.Update(
            created.Id,
            created.Version,
            "Dos",
            "detalle",
            "2026-08-01T12:30:00Z");

        var reopened = new LocalTaskStore(root);
        LocalTaskRecord persisted = reopened.Read(created.Id);

        Assert.Multiple(() =>
        {
            Assert.That(persisted, Is.EqualTo(updated));
            Assert.That(persisted.Title, Is.EqualTo("Dos"));
            Assert.That(persisted.Details, Is.EqualTo("detalle"));
            Assert.That(
                persisted.DueUtc,
                Is.EqualTo(DateTimeOffset.Parse("2026-08-01T12:30:00Z", CultureInfo.InvariantCulture)));
        });
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                "baxy-task-tests",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture));
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true);
        }
    }
}
