using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C10 variante, C11): office.format.apply formats what the person has open in Word or Excel through the
/// running application's object model and reads it back. These tests check what reaches the script and what the receipt
/// says, with a fake runner: no Office is touched.
/// </summary>
[TestFixture]
public sealed class OfficeFormatAdapterTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    [TestCase("""{"app":"excel","style":"bold","target":"row","row":1}""", """{"app":"excel","style":"bold","on":true,"target":"row","row":1,"column":null,"cells":null,"paragraph":null}""")]
    [TestCase("""{"app":"excel","style":"bold","target":"column","column":"a"}""", """{"app":"excel","style":"bold","on":true,"target":"column","row":null,"column":"A","cells":null,"paragraph":null}""")]
    [TestCase("""{"app":"word","style":"underline","on":false}""", """{"app":"word","style":"underline","on":false,"target":"selection","row":null,"column":null,"cells":null,"paragraph":null}""")]
    [TestCase("""{"app":"word","style":"center","target":"title"}""", """{"app":"word","style":"center","on":true,"target":"title","row":null,"column":null,"cells":null,"paragraph":null}""")]
    [TestCase("""{"app":"word","style":"bold","target":"paragraph","paragraph":3}""", """{"app":"word","style":"bold","on":true,"target":"paragraph","row":null,"column":null,"cells":null,"paragraph":3}""")]
    public void AFormatOfOneApplicationReachesTheScriptAsAsked(string arguments, string request)
    {
        Assert.That(OfficeFormatAdapter.Request(Json(arguments)), Is.EqualTo(request));
    }

    // Contracases: what names no format of one application is refused before anything runs.
    [TestCase("""{"app":"powerpoint","style":"bold"}""")]
    [TestCase("""{"app":"excel","style":"blink"}""")]
    [TestCase("""{"app":"word","style":"bold","target":"row","row":1}""")]
    [TestCase("""{"app":"excel","style":"bold","target":"title"}""")]
    [TestCase("""{"app":"word","style":"bold","target":"paragraph"}""")]
    [TestCase("""{"app":"excel","style":"bold","target":"row"}""")]
    [TestCase("""{"app":"excel","style":"bold","target":"column","column":"A1"}""")]
    public async Task WhatNamesNoFormatIsRefusedBeforeAnythingRuns(string arguments)
    {
        var runner = new CountingRunner("{}");
        ExternalCapabilityReceipt receipt = await new OfficeFormatAdapter(runner).InvokeAsync(
            OfficeFormatAdapter.Operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("office_format_arguments_invalid"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(runner.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task TheReceiptSaysTheDocumentAndWhatReceivedTheFormat()
    {
        var runner = new CountingRunner("""{"ok":true,"effectObserved":true,"error":"","document":"datos.xlsx","sheet":"Hoja1","applied":"1:1"}""");
        ExternalCapabilityReceipt receipt = await new OfficeFormatAdapter(runner).InvokeAsync(
            OfficeFormatAdapter.Operation, Json("""{"app":"excel","style":"bold","target":"row","row":1}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("document").GetString(), Is.EqualTo("datos.xlsx"));
            Assert.That(receipt.Result?.GetProperty("applied").GetString(), Is.EqualTo("1:1"));
            Assert.That(receipt.Result?.GetProperty("on").GetBoolean(), Is.True);
        });
    }

    // With no Word or Excel running nothing is started nor changed; a format that did not read back is no success.
    [TestCase("""{"ok":false,"effectObserved":false,"error":"office_app_not_open"}""", "office_app_not_open", false)]
    [TestCase("""{"ok":false,"effectObserved":true,"error":"office_format_not_read_back"}""", "office_format_not_read_back", true)]
    public async Task AFailureSaysWhetherAnythingMayHaveChanged(string answer, string code, bool mayHave)
    {
        ExternalCapabilityReceipt receipt = await new OfficeFormatAdapter(new CountingRunner(answer)).InvokeAsync(
            OfficeFormatAdapter.Operation, Json("""{"app":"word","style":"bold"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.EffectMayHaveOccurred, Is.EqualTo(mayHave));
        });
    }

    private sealed class CountingRunner(string answer) : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Calls++;
            return ValueTask.FromResult(new ExternalProcessResult(0, answer + "\n", string.Empty));
        }
    }
}
