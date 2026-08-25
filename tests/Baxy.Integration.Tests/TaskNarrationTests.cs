using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

public sealed class TaskNarrationTests
{
    [Test]
    public void EmptyTaskListCarriesItsVerifiedCountAsFacts()
    {
        OperationOutcome outcome = OperationOutcome.Success(
            JsonSerializer.SerializeToElement(
                new TaskListResult([], 0, "tasks", 20),
                CoreJsonContext.Default.TaskListResult));

        JsonElement facts = OperationOutcomeNarration.AssertFacts("task.list", outcome);

        Assert.That(
            facts.GetProperty("observed").GetProperty("count").GetInt32(),
            Is.Zero);
    }

    [Test]
    public void TaskCreationCarriesTheVerifiedTitleWithoutItsOpaqueId()
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

        JsonElement facts = OperationOutcomeNarration.AssertFacts("task.create", outcome);
        JsonElement observed = facts.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(observed.GetProperty("title").GetString(), Is.EqualTo("Informe Q3"));
            Assert.That(observed.TryGetProperty("id", out _), Is.False);
        });
    }

    [Test]
    public void TaskFailureCarriesItsExactPolarityAndCauseAsFacts()
    {
        JsonElement facts = OperationOutcomeNarration.AssertFacts(
            "task.list",
            OperationOutcome.Failure("invalid_arguments"));

        Assert.That(facts.GetProperty("error").GetString(), Is.EqualTo("invalid_arguments"));
    }
}
