using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The memory panel's list (src/Baxy.App/MemoryPanel.cs), page by page as the store gives them.</summary>
[TestFixture]
public sealed class MemoryPanelTests
{
    // Revisión de calidad (2026-10-25): with 501 to 512 entries the panel's last page asked offset 500 and limit 100,
    // a page past the store's 512 that memory.list refuses, and the whole list failed.
    [Test]
    public void NoPageReachesPastTheStoresEntries()
    {
        Assert.Multiple(() =>
        {
            Assert.That(MemoryPanel.PageLimit(0, 100), Is.EqualTo(100));
            Assert.That(MemoryPanel.PageLimit(400, 100), Is.EqualTo(100));
            Assert.That(MemoryPanel.PageLimit(500, 100), Is.EqualTo(12));
            Assert.That(MemoryPanel.PageLimit(0, 1), Is.EqualTo(1));
        });
    }

    // MEM8C (REV20 M-1): 4 records, «Olvidar todo» (or one forgotten, or edited) in the panel, then «¿qué recuerdas de
    // mí?»: the offer said «saved: 4» and the check «tiene 4 datos» until the App restarted. A panel request that answered
    // and is not a read makes the count read at the start not known (FieldProductChannel → ToolProfile.MemoryRecords).
    [Test]
    public void AnAnsweredChangeInThePanelMakesTheCountNotKnown()
    {
        Assert.Multiple(() =>
        {
            Assert.That(MemoryPanel.ChangesKept("DELETE", 200), Is.True, "Olvidar todo, or one forgotten");
            Assert.That(MemoryPanel.ChangesKept("PUT", 200), Is.True, "an edit, or the switch");
            Assert.That(MemoryPanel.ChangesKept("GET", 200), Is.False, "the list reads only");
            Assert.That(MemoryPanel.ChangesKept("DELETE", 503), Is.False, "nothing changed");
        });
    }

    // MEM8C (REV20 M-5): a temporary record goes when its time ends while BAXY stays open: with one, the count read at the
    // start would say one more than there is then; it is not known. With none, it is memory.status's total.
    [Test]
    public void TheCountReadAtTheStartIsNotKnownWithATemporaryRecord()
    {
        static System.Text.Json.JsonElement Status(int temporary) =>
            System.Text.Json.JsonSerializer.Deserialize<System.Text.Json.JsonElement>(
            $"{{\"version\":1,\"enabled\":true,\"totalRecords\":{4 + temporary},\"persistentRecords\":3,"
            + $"\"sessionRecords\":1,\"temporaryRecords\":{temporary},\"maximumRecords\":512}}");

        Assert.Multiple(() =>
        {
            Assert.That(MainWindowViewModel.RecordsKept(Status(0)), Is.EqualTo(4));
            Assert.That(MainWindowViewModel.RecordsKept(Status(1)), Is.Null);
        });
    }
}
