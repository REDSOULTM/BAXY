using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C02): a click that changed nothing on a control the window had already chosen (the section Settings
/// opened at) says so, for the model to read the view it has instead of pressing the same control again; the worker
/// marks it from the control's own state before the click.
/// </summary>
[TestFixture]
public sealed class VisibleClickAlreadySelectedTests
{
    [Test]
    public void AControlAlreadyChosenSaysTheWindowAlreadyShowsIt()
    {
        JsonElement result = WindowsVisibleControlAdapter.AlreadySelected();

        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("alreadySelected").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("next").GetString(), Does.Contain("already shows it"));
        });
    }

    [Test]
    public void TheWorkerMarksTheUnchangedClickOfAControlChosenBeforeIt()
    {
        string worker = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        Assert.That(worker, Does.Contain("$pending.stateBefore.selected -eq $true){ $unchanged.alreadySelected=$true }"));
    }

    // BAXY Renew cu (C02), encargo 96: in Bypass a switch of Windows' own Settings is refused before any press, with its
    // state; the worker refuses it on both of its ways to press (by name or identity, and at a point).
    [Test]
    public void ASettingsSwitchIsRefusedWithItsState()
    {
        using JsonDocument worker = JsonDocument.Parse(
            """{"ok":false,"error":"visible_settings_switch_refused","name":"Wi-Fi","switchState":"On"}""");
        JsonElement facts = WindowsVisibleControlAdapter.SettingsSwitchFacts(worker.RootElement);
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));

        Assert.Multiple(() =>
        {
            Assert.That(facts.GetProperty("name").GetString(), Is.EqualTo("Wi-Fi"));
            Assert.That(facts.GetProperty("switch").GetString(), Is.EqualTo("on"));
            Assert.That(facts.GetProperty("next").GetString(), Does.StartWith("nothing was pressed"));
            Assert.That(System.Text.RegularExpressions.Regex.Count(
                script, @"\$switchRefused=Get-SettingsSwitchRefusal \$button \$name \$identity \$kind"), Is.EqualTo(2));
        });
    }

    // P2.15 (resultados honestos): the refusal holds for every switch of Settings, so its way out names every tool that
    // changes one of them; naming only the radios sent «modo avión» or «no molestar» to wifi_radio_set.
    [Test]
    public void ASettingsSwitchRefusalNamesEveryToolThatChangesASetting()
    {
        using JsonDocument worker = JsonDocument.Parse(
            """{"ok":false,"error":"visible_settings_switch_refused","name":"Modo avión","switchState":"Off"}""");
        string next = WindowsVisibleControlAdapter.SettingsSwitchFacts(worker.RootElement).GetProperty("next").GetString()!;

        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain("wifi_radio_set"));
            Assert.That(next, Does.Contain("bluetooth_radio_set"));
            Assert.That(next, Does.Contain("system_settings_set"));
        });
    }
}
