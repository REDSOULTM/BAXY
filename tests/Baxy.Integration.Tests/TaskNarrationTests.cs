using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

public sealed class TaskNarrationTests
{
    [Test]
    public void EmptyTaskListHasNaturalNontechnicalNarration()
    {
        OperationOutcome outcome = OperationOutcome.Success(
            JsonSerializer.SerializeToElement(
                new TaskListResult([], 0, "tasks", 20),
                CoreJsonContext.Default.TaskListResult));

        var facts = OperationOutcomeNarration.Facts("task.list", outcome);

        Assert.That(facts["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
        Assert.That(facts["operation"]?.GetValue<string>(), Is.EqualTo("task.list"));
        Assert.That(UserMessagePolicy.IsSafe(facts.ToJsonString()), Is.True);
    }

    [Test]
    public void TaskCreationNamesTheVerifiedTaskNaturally()
    {
        OperationOutcome outcome = OperationOutcome.Success(
            JsonSerializer.SerializeToElement(
                new TaskResult(
                    Guid.NewGuid().ToString("D"),
                    "Informe Q3",
                    string.Empty,
                    null,
                    false,
                    null,
                    false,
                    DateTimeOffset.UtcNow,
                    DateTimeOffset.UtcNow,
                    1),
                CoreJsonContext.Default.TaskResult));

        string narration = OperationOutcomeNarration.For("task.create", outcome);

        Assert.That(narration, Does.Contain("Informe Q3"));
        Assert.That(OperationOutcomeNarration.Facts("task.create", outcome)["polarity"]?.GetValue<string>(),
            Is.EqualTo("success"));
        Assert.That(UserMessagePolicy.IsSafe(narration), Is.True);
    }

    [Test]
    public void TaskFailureHasNaturalNontechnicalNarration()
    {
        var facts = OperationOutcomeNarration.Facts(
            "task.list",
            OperationOutcome.Failure("invalid_arguments"));

        Assert.That(facts["polarity"]?.GetValue<string>(), Is.EqualTo("failure"));
        Assert.That(facts["error"]?.GetValue<string>(), Is.EqualTo("invalid_arguments"));
        Assert.That(UserMessagePolicy.IsSafe(facts.ToJsonString()), Is.True);
    }
}
