using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class ObservedUserCorpusReplayContractTests
{
    [Test]
    public void CatalogEvidenceUsesTheCurrentTypedDescriptorForFinalEffects()
    {
        using JsonDocument document = JsonDocument.Parse(
            """
            {"phase":"final","final":{"kind":"action","effect_operations":["window.application.status"]}}
            """);

        ObservedUserCorpusReplayTests.CatalogEvidenceRow[] evidence =
            ObservedUserCorpusReplayTests.CatalogEvidence(
                [document.RootElement.Clone()],
                []);

        Assert.That(evidence, Has.Length.EqualTo(1));
        Assert.Multiple(() =>
        {
            Assert.That(evidence[0].operation, Is.EqualTo("window.application.status"));
            Assert.That(evidence[0].risk, Is.EqualTo("read_only"));
            Assert.That(
                evidence[0].verifier_contract_id,
                Is.EqualTo("window.application.status.catalog.visible.snapshot.v1"));
        });
    }
}
