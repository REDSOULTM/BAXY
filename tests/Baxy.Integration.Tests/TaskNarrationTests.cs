using System.Text.Json;
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

        string narration = OperationOutcomeNarration.For("task.list", outcome);

        Assert.That(narration, Is.EqualTo("No encontré tareas en esa lista."));
        Assert.That(UserMessagePolicy.IsSafe(narration), Is.True);
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

        Assert.That(narration, Is.EqualTo("Creé la tarea «Informe Q3»."));
        Assert.That(UserMessagePolicy.IsSafe(narration), Is.True);
    }

    [Test]
    public void TaskFailureHasNaturalNontechnicalNarration()
    {
        string narration = OperationOutcomeNarration.For(
            "task.list",
            OperationOutcome.Failure("invalid_arguments"));

        Assert.That(
            narration,
            Is.EqualTo("Los datos de la tarea no tienen el formato esperado."));
        Assert.That(UserMessagePolicy.IsSafe(narration), Is.True);
    }
}
