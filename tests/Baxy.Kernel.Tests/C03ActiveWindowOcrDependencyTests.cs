using System.Text.Json;
using Baxy.Kernel.Planning;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class C03ActiveWindowOcrDependencyTests
{
    [TestCase("capture.screenshot")]
    [TestCase("capture.active.window")]
    public void BothCaptureProducersAuthorizeDeferredOcrWithExactCaptureIdentity(string producer)
    {
        MissionPlanProposal proposal = Proposal(producer, ["capture"]);

        Assert.DoesNotThrow(() => MissionPlanValidator.Validate(proposal));
        Assert.Multiple(() =>
        {
            Assert.That(MissionPlanValidator.DependencyProducerOperations("ocr.read"),
                Does.Contain(producer));
            Assert.That(MissionPlanValidator.DependencyAuthorityFields("ocr.read"),
                Is.EqualTo(new[] { "captureId" }));
            Assert.That(proposal.Steps[1].Arguments, Is.Null);
            Assert.That(proposal.Steps[1].DependsOn, Is.EqualTo(new[] { "capture" }));
        });
    }

    [TestCase("capture.screenshot")]
    [TestCase("capture.active.window")]
    public void CaptureWithoutDeclaredDependencyDoesNotAuthorizeOcr(string producer) =>
        Assert.Throws<MissionPlanValidationException>(() =>
            MissionPlanValidator.Validate(Proposal(producer, [])));

    [TestCase("capture.screenshot")]
    [TestCase("capture.active.window")]
    public void MissingProducerStepCannotBePresentedAsObservedDependency(string producer) =>
        Assert.Throws<MissionPlanValidationException>(() =>
            MissionPlanValidator.Validate(Proposal(producer, ["not_observed"])));

    [Test]
    public void ActiveWindowIdentityIsNotACaptureProducer() =>
        Assert.Throws<MissionPlanValidationException>(() =>
            MissionPlanValidator.Validate(Proposal("window.active", ["capture"])));

    [TestCase("capture.screenshot")]
    [TestCase("capture.active.window")]
    public void DeferredOcrCannotContainACaptureIdBeforeTheProducerRuns(string producer)
    {
        MissionPlanProposal proposal = Proposal(producer, ["capture"]);
        MissionPlanStepProposal read = proposal.Steps[1] with
        {
            Arguments = JsonSerializer.SerializeToElement(new
            {
                captureId = "capture_0123456789abcdef0123456789abcdef",
            }),
        };
        proposal = proposal with { Steps = [proposal.Steps[0], read] };

        Assert.Throws<MissionPlanValidationException>(() => MissionPlanValidator.Validate(proposal));
    }

    private static MissionPlanProposal Proposal(string producer, IReadOnlyList<string> dependencies) =>
        new(1, "Read the requested capture",
        [
            new("capture", producer, "Observe the requested surface", [], "literal",
                JsonSerializer.SerializeToElement(new { })),
            new("read", "ocr.read", "Read the observed capture", dependencies,
                "after_dependencies", null),
        ]);
}
