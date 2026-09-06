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
    public void StructuredFactsAreNotPublishableAndASentencePreservesPolarity()
    {
        string[] leakedJson = [];
        var rejectedRewrite = new List<string>();
        foreach (var descriptor in ProductCatalog.ToolDescriptors)
        {
            string successFacts = OperationOutcomeNarration.For(
                descriptor.Name,
                OperationOutcome.Success());
            string failureFacts = OperationOutcomeNarration.For(
                descriptor.Name,
                OperationOutcome.Failure("narration_coverage_probe"));
            UserMessageDraft successDraft = UserMessagePolicy.Create(
                successFacts,
                UserMessageEvent.Status);
            UserMessageDraft failureDraft = UserMessagePolicy.Create(
                failureFacts,
                UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
            if (UserMessagePolicy.ModelResponseRejectionReason(successFacts, successDraft)
                != "structured_facts_not_prose")
            {
                leakedJson = [.. leakedJson, descriptor.Name + " success"];
            }

            if (UserMessagePolicy.ModelResponseRejectionReason(failureFacts, failureDraft)
                != "structured_facts_not_prose")
            {
                leakedJson = [.. leakedJson, descriptor.Name + " failure"];
            }

            if (UserMessagePolicy.AcceptModelAuthoredResponse(
                    "Listo, quedó hecho y verificado.",
                    successDraft) is null)
            {
                rejectedRewrite.Add(descriptor.Name + " success rewrite");
            }

            if (UserMessagePolicy.AcceptModelAuthoredResponse(
                    "No pude completar lo que pediste.",
                    failureDraft) is null)
            {
                rejectedRewrite.Add(descriptor.Name + " failure rewrite");
            }
        }

        Assert.Multiple(() =>
        {
            Assert.That(leakedJson, Is.Empty, string.Join(Environment.NewLine, leakedJson));
            Assert.That(
                rejectedRewrite,
                Is.Empty,
                string.Join(Environment.NewLine, rejectedRewrite));
        });
    }

    [Test]
    public void FamilyFactsKeepPolarityWithoutASpanishSubjectFloor()
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
                    Reversed = "No pude completarla.",
                    Honest = "Listo, quedó hecho.",
                },
                new
                {
                    Family = family,
                    Message = OperationOutcomeNarration.For(
                        $"{family}.narration.coverage",
                        OperationOutcome.Failure("narration_coverage_probe")),
                    Event = UserMessageEvent.Error(
                        UserMessageDiagnosticCodes.ActionNotCompleted),
                    Reversed = "Listo, quedó hecho.",
                    Honest = "No pude completarla.",
                },
            })
            .Select(static item =>
            {
                UserMessageDraft draft = UserMessagePolicy.Create(
                    item.Message,
                    item.Event);
                bool structured = UserMessagePolicy.IsStructuredFacts(item.Message);
                string? reversed = UserMessagePolicy.ModelResponseRejectionReason(
                    item.Reversed,
                    draft);
                string? honest = UserMessagePolicy.ModelResponseRejectionReason(
                    item.Honest,
                    draft);
                return structured
                    && reversed == "reversed_result"
                    && honest is null
                        ? null
                        : $"{item.Family}: source={item.Message}; "
                            + $"structured={structured}; reversed={reversed}; "
                            + $"honest={honest ?? "accepted"}";
            })
            .Where(static failure => failure is not null)
            .Select(static failure => failure!)
            .ToArray();

        Assert.That(failures, Is.Empty, string.Join(Environment.NewLine, failures));
    }
}
