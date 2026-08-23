using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class HonestyCorrectionAppTests
{
    [Test]
    public void AppReadsTheJournaledCorrectionBuiltFromTheShippedInProgressSignal()
    {
        FieldProgressNotice notice = FieldBridgeContract.Create(
            FieldProgressNotice.StageUnderstanding);
        const string denial = "verification_failed";
        const string correction = "No pude completar la petición solicitada.";

        HonestyCorrectionTrace trace = HonestyCorrection.Correct(
            HonestyCorrection.NonAssertingInProgress,
            denial,
            correction);
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            "ignored fallback",
            false,
            false,
            null,
            denial,
            EffectMayHaveOccurred: true,
            CauseCode: "honesty_self_correction",
            HonestyCorrection: trace);

        OperationResponseProjection projection = OperationResponseProjection.Create(
            response,
            "note.create");

        Assert.Multiple(() =>
        {
            Assert.That(notice.Label, Is.Null);
            Assert.That(trace.Claim, Is.EqualTo(HonestyCorrection.NonAssertingInProgress));
            Assert.That(trace.Verification, Is.EqualTo(denial));
            Assert.That(projection.Message, Is.EqualTo(correction));
            Assert.That(projection.Message, Does.Not.Contain("Listo"));
            Assert.That(projection.Message, Does.Not.Contain("ignored fallback"));
        });
    }
}
