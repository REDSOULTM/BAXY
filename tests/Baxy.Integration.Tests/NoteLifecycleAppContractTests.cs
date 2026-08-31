using System.Text;
using System.Text.Json;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class NoteLifecycleAppContractTests
{
    private static readonly OperationDescriptor[] RequiredCapabilities =
        ProductCatalog.ToolDescriptors
            .Select(static descriptor => ProductCatalog.CreateToolDescriptor(
                new OperationDefinition(descriptor)))
            .ToArray();

    [Test]
    public void HandshakeRequiresTheWholeNaturalNoteLifecycleWithExactRisks()
    {
        ProtocolHello complete = CreateHello(RequiredCapabilities);

        Assert.That(CoreProcessClient.SupportsInteractiveOperations(complete), Is.True);
        foreach (OperationDescriptor capability in RequiredCapabilities)
        {
            ProtocolHello missing = CreateHello(
                RequiredCapabilities.Where(candidate => candidate.Name != capability.Name));
            ProtocolHello wrongRisk = CreateHello(
                RequiredCapabilities.Select(candidate => candidate.Name == capability.Name
                    ? candidate with { Risk = DifferentRisk(capability.Risk) }
                    : candidate));

            Assert.Multiple(() =>
            {
                Assert.That(
                    CoreProcessClient.SupportsInteractiveOperations(missing),
                    Is.False,
                    $"A hello without {capability.Name} must not enable input.");
                Assert.That(
                    CoreProcessClient.SupportsInteractiveOperations(wrongRisk),
                    Is.False,
                    $"A hello with the wrong {capability.Name} risk must not enable input.");
            });
        }
    }

    [Test]
    public void HandshakeRejectsDuplicateRequiredCapabilities()
    {
        ProtocolHello duplicate = CreateHello(
            [.. RequiredCapabilities, RequiredCapabilities[0]]);

        Assert.That(CoreProcessClient.SupportsInteractiveOperations(duplicate), Is.False);
    }

    [Test]
    public void NoteReadProjectionShowsTitleAndContentWithoutJson()
    {
        OperationResponse response = CompletedWithResult(
            """
            {"noteId":"f330ff7d-47f2-4d50-9892-56708c25bb45","title":"Compras","content":"leche\npan"}
            """);

        OperationResponseProjection projection = OperationResponseProjection.Create(
            response,
            "note.read");

        Assert.Multiple(() =>
        {
            Assert.That(projection.Message, Is.EqualTo("Encontré la nota."));
            Assert.That(projection.Message, Does.Not.Contain("noteId"));
        });
    }

    [Test]
    public void EmptyNoteReadProjectionStatesThatTheNoteIsEmpty()
    {
        OperationResponse response = CompletedWithResult(
            """{"title":"Ideas","content":""}""");

        OperationResponseProjection projection = OperationResponseProjection.Create(
            response,
            "note.read");

        Assert.That(projection.Message, Is.EqualTo("Encontré la nota."));
    }

    [Test]
    public void LongNoteReadProjectionIsExplicitlyTruncatedOnAUnicodeBoundary()
    {
        string content = string.Concat(Enumerable.Repeat("🙂", 20_000));
        string json = JsonSerializer.Serialize(new { title = "Emoji", content });
        using JsonDocument document = JsonDocument.Parse(json);
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Completed,
            content,
            true,
            false,
            document.RootElement.Clone(),
            null);

        OperationResponseProjection projection = OperationResponseProjection.Create(
            response,
            "note.read");

        Assert.Multiple(() =>
        {
            Assert.That(projection.Message.Length, Is.LessThanOrEqualTo(16_384));
            Assert.That(projection.Message, Does.EndWith("… [respuesta truncada]"));
            Assert.DoesNotThrow(() => new UTF8Encoding(false, true).GetBytes(projection.Message));
        });
    }

    private static ProtocolHello CreateHello(
        IEnumerable<OperationDescriptor> capabilities) => new(
            ProtocolTypes.Hello,
            ProtocolVersion.Current,
            "1.0.0",
            42,
            capabilities.ToArray());

    private static string DifferentRisk(string risk) =>
        string.Equals(risk, OperationRisks.ReadOnly, StringComparison.Ordinal)
            ? OperationRisks.LowReversible
            : OperationRisks.ReadOnly;

    private static OperationResponse CompletedWithResult(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        return new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Completed,
            "Encontré la nota.",
            true,
            false,
            document.RootElement.Clone(),
            null);
    }
}
