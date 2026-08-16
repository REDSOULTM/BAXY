using Baxy.App;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

public sealed class CatalogNarrationCoverageTests
{
    [Test]
    public void EveryPublicOperationHasSafeSuccessAndFailureNarration()
    {
        string[] unsafeSuccess = ProductCatalog.ToolDescriptors
            .Select(static descriptor => new
            {
                descriptor.Name,
                Message = OperationOutcomeNarration.For(
                    descriptor.Name,
                    OperationOutcome.Success()),
            })
            .Where(static item => !UserMessagePolicy.IsSafe(item.Message))
            .Select(static item => $"{item.Name}: {item.Message}")
            .ToArray();
        string[] unsafeFailure = ProductCatalog.ToolDescriptors
            .Select(static descriptor => new
            {
                descriptor.Name,
                Message = OperationOutcomeNarration.For(
                    descriptor.Name,
                    OperationOutcome.Failure("narration_coverage_probe")),
            })
            .Where(static item => !UserMessagePolicy.IsSafe(item.Message))
            .Select(static item => $"{item.Name}: {item.Message}")
            .ToArray();
        string[] unsafeStatus = ProductCatalog.ToolDescriptors
            .Select(static descriptor => new
            {
                descriptor.Name,
                Message = ProductOperationNarrator.Instance.NarrateStatus(
                    descriptor.Name,
                    OperationStatuses.Failed,
                    "narration_coverage_probe"),
            })
            .Where(static item => !UserMessagePolicy.IsSafe(item.Message))
            .Select(static item => $"{item.Name}: {item.Message}")
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(
                unsafeSuccess,
                Is.Empty,
                string.Join(Environment.NewLine, unsafeSuccess));
            Assert.That(
                unsafeFailure,
                Is.Empty,
                string.Join(Environment.NewLine, unsafeFailure));
            Assert.That(
                unsafeStatus,
                Is.Empty,
                string.Join(Environment.NewLine, unsafeStatus));
        });
    }

    [Test]
    public void EveryPublicNarrationSurvivesTheFullAppAcceptancePolicy()
    {
        string[] rejectedSuccess = ProductCatalog.ToolDescriptors
            .Select(static descriptor => new
            {
                descriptor.Name,
                Message = OperationOutcomeNarration.For(
                    descriptor.Name,
                    OperationOutcome.Success()),
            })
            .Select(static item => DescribeRejection(
                item.Name,
                item.Message,
                UserMessageEvent.Status))
            .Where(static rejection => rejection is not null)
            .Select(static rejection => rejection!)
            .ToArray();
        string[] rejectedFailure = ProductCatalog.ToolDescriptors
            .Select(static descriptor => new
            {
                descriptor.Name,
                Message = OperationOutcomeNarration.For(
                    descriptor.Name,
                    OperationOutcome.Failure("narration_coverage_probe")),
            })
            .Select(static item => DescribeRejection(
                item.Name,
                item.Message,
                UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted)))
            .Where(static rejection => rejection is not null)
            .Select(static rejection => rejection!)
            .ToArray();
        string[] rejectedStatus = ProductCatalog.ToolDescriptors
            .Select(static descriptor => new
            {
                descriptor.Name,
                Message = ProductOperationNarrator.Instance.NarrateStatus(
                    descriptor.Name,
                    OperationStatuses.Failed,
                    "narration_coverage_probe"),
            })
            .Select(static item => DescribeRejection(
                item.Name,
                item.Message,
                UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted)))
            .Where(static rejection => rejection is not null)
            .Select(static rejection => rejection!)
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(
                rejectedSuccess,
                Is.Empty,
                string.Join(Environment.NewLine, rejectedSuccess));
            Assert.That(
                rejectedFailure,
                Is.Empty,
                string.Join(Environment.NewLine, rejectedFailure));
            Assert.That(
                rejectedStatus,
                Is.Empty,
                string.Join(Environment.NewLine, rejectedStatus));
        });
    }

    [Test]
    public void EveryFamilyFloorMakesItsPersonFacingSubjectMandatory()
    {
        string[] failures = ProductCatalog.ToolDescriptors
            .Select(static descriptor => descriptor.Name.Split('.')[0])
            .Distinct(StringComparer.Ordinal)
            .SelectMany(static family => new[]
            {
                new
                {
                    Family = family,
                    Message = OperationOutcomeNarration.For(
                        $"{family}.narration.coverage",
                        OperationOutcome.Success()),
                    Event = UserMessageEvent.Status,
                    SubjectlessCandidate = "Lo completé y lo verifiqué.",
                },
                new
                {
                    Family = family,
                    Message = OperationOutcomeNarration.For(
                        $"{family}.narration.coverage",
                        OperationOutcome.Failure("narration_coverage_probe")),
                    Event = UserMessageEvent.Error(
                        UserMessageDiagnosticCodes.ActionNotCompleted),
                    SubjectlessCandidate = "No pude completarla.",
                },
            })
            .Select(static item =>
            {
                IReadOnlyList<string> facts =
                    UserMessagePolicy.RequiredLiteralFacts(item.Message);
                UserMessageDraft draft = UserMessagePolicy.Create(
                    item.Message,
                    item.Event);
                string? rejection = UserMessagePolicy.ModelResponseRejectionReason(
                    item.SubjectlessCandidate,
                    draft);
                return facts.Count == 1
                    && rejection == "missing_literal_fact"
                        ? null
                        : $"{item.Family}: source={item.Message}; "
                            + $"facts={string.Join(" | ", facts)}; "
                            + $"subjectlessRejection={rejection ?? "accepted"}";
            })
            .Where(static failure => failure is not null)
            .Select(static failure => failure!)
            .ToArray();

        Assert.That(failures, Is.Empty, string.Join(Environment.NewLine, failures));
    }

    private static string? DescribeRejection(
        string operation,
        string message,
        UserMessageEvent messageEvent)
    {
        UserMessageDraft draft = UserMessagePolicy.Create(message, messageEvent);
        string? rejection = UserMessagePolicy.ModelResponseRejectionReason(message, draft);
        return rejection is null
            ? null
            : $"{operation}: {rejection}: {message}";
    }
}
