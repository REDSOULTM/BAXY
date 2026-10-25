using Baxy.App;
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
}
