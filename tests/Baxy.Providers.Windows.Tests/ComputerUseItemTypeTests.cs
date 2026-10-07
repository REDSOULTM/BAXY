using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The type a list, grid or tree item reports through UI Automation (a folder, a shortcut, an application) reaches the
/// view: the worker caches and emits it as <c>itemType</c> and the adapter passes it through. Scripted worker answers,
/// never a real window.
/// </summary>
[TestFixture]
public sealed class ComputerUseItemTypeTests
{
    [Test]
    public async Task TheViewCarriesTheItemTypeTheWorkerReports()
    {
        // A handle no window has: nothing on the desktop is read or moved.
        const long front = 0x7FFF_0F2E;
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"ok\":true,\"error\":\"\",\"hwnd\":" + front + ",\"window\":\"Trabajo\",\"controls\":[" +
            "{\"i\":0,\"kind\":\"ListItem\",\"name\":\"Imágenes\",\"id\":\"4.1\",\"state\":\"\",\"value\":null," +
            "\"itemType\":\"Carpeta de archivos\",\"rect\":null,\"repeated\":0}," +
            "{\"i\":1,\"kind\":\"ListItem\",\"name\":\"notas.txt\",\"id\":\"4.2\",\"state\":\"\",\"value\":null," +
            "\"itemType\":\"\",\"rect\":null,\"repeated\":0}," +
            "{\"i\":2,\"kind\":\"Button\",\"name\":\"Atrás\",\"id\":\"4.3\",\"state\":\"\",\"value\":null," +
            "\"rect\":null,\"repeated\":0}],\"controlCount\":3,\"focused\":null}");
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, browserWindow: new FixedFront(front));

        ExternalCapabilityReceipt view = await adapter.InvokeAsync(
            "input.visible.controls", JsonDocument.Parse("""{"application":"el navegador"}""").RootElement.Clone(),
            CancellationToken.None);

        JsonElement controls = view.Result!.Value.GetProperty("controls");
        Assert.Multiple(() =>
        {
            Assert.That(view.Verified, Is.True);
            Assert.That(controls[0].GetProperty("itemType").GetString(), Is.EqualTo("Carpeta de archivos"));
            Assert.That(controls[1].TryGetProperty("itemType", out _), Is.False, "an empty type says nothing");
            Assert.That(controls[2].TryGetProperty("itemType", out _), Is.False);
        });
    }

    [Test]
    public void TheWorkerCachesAndEmitsTheItemType()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = File.ReadAllText(worker);
        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Contain("$AE::ItemTypeProperty"), "read in the same cached call as the other properties");
            Assert.That(script, Does.Contain("$item.Cached.ItemType"));
            Assert.That(script, Does.Contain("itemType=$entry.itemType"), "emitted with each control");
        });
    }

    private sealed class FixedFront(long handle) : IUserBrowserWindowLocator
    {
        public nint FrontWindow() => (nint)handle;
    }
}
