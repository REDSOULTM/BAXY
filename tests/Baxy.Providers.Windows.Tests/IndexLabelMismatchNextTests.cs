using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C03): Steam's page gave one control and its words only as read text; the model sent a word of that
/// text with index 0 six times. The refusal of an index that names another control keeps its candidates and, with the
/// aid index_label_next, says what the index is and that a read text is clicked by its label alone.
/// </summary>
[TestFixture]
public sealed class IndexLabelMismatchNextTests
{
    [Test]
    public void TheRefusalCarriesTheIndexsNameAndHowAReadTextIsClicked()
    {
        ExternalCapabilityReceipt receipt = WindowsVisibleControlAdapter.NotNamed(
            "input.visible.click", "visible_control_label_mismatch", ["Chrome Legacy Window"],
            next: "nothing was pressed: index 0 is «Chrome Legacy Window», not «Tienda»");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_label_mismatch"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("candidates")[0].GetString(), Is.EqualTo("Chrome Legacy Window"));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("index 0 is «Chrome Legacy Window»"));
        });
    }

    // Contracase: with no next the refusal reads as before (candidates only).
    [Test]
    public void WithoutANextTheRefusalReadsAsBefore()
    {
        ExternalCapabilityReceipt receipt = WindowsVisibleControlAdapter.NotNamed(
            "input.visible.click", "visible_control_label_mismatch", ["Fuente"]);

        Assert.That(receipt.Result?.TryGetProperty("next", out _), Is.False);
    }
}
