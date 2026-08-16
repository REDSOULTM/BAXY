using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class OperationCallValidationTests
{
    [TestCase("{\"level\":50,\"extra\":true}")]
    [TestCase("{\"level\":\"50\"}")]
    [TestCase("{\"level\":-1}")]
    [TestCase("{\"level\":101}")]
    public async Task PublicInvalidCallIsRejectedBeforeHandler(string arguments)
    {
        var handler = new CountingProductHandler("audio.volume");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            Request("audio.volume", arguments),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(response.Verified, Is.False);
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task PublicValidCallReachesExactlyOneHandler()
    {
        var handler = new CountingProductHandler("audio.volume");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            Request("audio.volume", "{\"level\":50}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(response.Verified, Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task EveryPublicOperationAcceptsOneSchemaGeneratedValidCall()
    {
        CountingProductHandler[] handlers = ProductCatalog.ToolDescriptors
            .Select(static descriptor => new CountingProductHandler(descriptor.Name))
            .ToArray();
        var handlersByOperation = handlers.ToDictionary(
            static handler => handler.Definition.Name,
            StringComparer.Ordinal);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry(handlers),
            journal,
            new SchemaGeneratedPrivateAuthenticator());

        foreach (ProductOperationDescriptor descriptor in ProductCatalog.ToolDescriptors)
        {
            OperationRequest request = PrivateOperationBoundary.IsPrivateOperation(descriptor.Name)
                ? PrivateRequest(descriptor.Name)
                : Request(
                    descriptor.Name,
                    BuildValidArguments(descriptor.ArgumentsSchema));
            OperationResponse response = await engine.ExecuteAsync(
                request,
                CancellationToken.None);
            if (response.Status == OperationStatuses.Pending
                && string.Equals(response.ErrorCode, "confirmation_required", StringComparison.Ordinal))
            {
                string confirmationToken = response.Result!.Value
                    .GetProperty("token")
                    .GetString()!;
                response = await engine.ExecuteAsync(
                    request with
                    {
                        RequestId = Guid.NewGuid().ToString("D"),
                        ConfirmationToken = confirmationToken,
                    },
                    CancellationToken.None);
            }

            Assert.Multiple(() =>
            {
                Assert.That(
                    response.Status,
                    Is.EqualTo(OperationStatuses.Completed),
                    descriptor.Name);
                Assert.That(response.Verified, Is.True, descriptor.Name);
                Assert.That(
                    handlersByOperation[descriptor.Name].ExecutionCount,
                    Is.EqualTo(1),
                    descriptor.Name);
            });
        }

        Assert.That(
            handlers.Sum(static handler => handler.ExecutionCount),
            Is.EqualTo(ProductCatalog.ToolDescriptors.Count));
    }

    [Test]
    public async Task PrivateSchemaValidationStaysInsideEnvelopeBoundaryAndRedactsPayload()
    {
        const string canary = "PRIVATE-CANARY-MUST-NOT-LEAK";
        var handler = new CountingProductHandler("memory.status");
        var authenticator = new StubPrivateAuthenticator(
            Parse($"{{\"version\":1,\"extra\":\"{canary}\"}}"));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
            authenticator);
        OperationRequest request = PrivateRequest("memory.status");

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(response.Message, Does.Not.Contain(canary));
            Assert.That(response.Result, Is.Null);
            Assert.That(handler.ExecutionCount, Is.Zero);
            Assert.That(authenticator.SchemaValidationCount, Is.EqualTo(1));
        });
    }

    private static string BuildValidArguments(OperationArgumentsSchema schema)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            foreach (string requiredName in schema.Required)
            {
                OperationArgumentProperty property = schema.Properties.Single(candidate =>
                    string.Equals(candidate.Name, requiredName, StringComparison.Ordinal));
                writer.WritePropertyName(property.Name);
                WriteValidValue(writer, property.Types, property);
            }

            writer.WriteEndObject();
        }

        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private static void WriteValidValue(
        Utf8JsonWriter writer,
        OperationJsonType types,
        OperationArgumentProperty? property = null)
    {
        if (property?.AllowedValues.Count > 0)
        {
            writer.WriteStringValue(property.AllowedValues[0]);
            return;
        }

        if (types.HasFlag(OperationJsonType.String))
        {
            int length = Math.Max(
                property?.MinimumLength ?? 0,
                property?.NonWhitespace == true ? 1 : 0);
            writer.WriteStringValue(new string('x', length));
            return;
        }

        if (types.HasFlag(OperationJsonType.Integer))
        {
            long value = property?.Minimum ?? 0;
            if (property?.Minimum is null && property?.Maximum is < 0)
            {
                value = property.Maximum.Value;
            }

            writer.WriteNumberValue(value);
            return;
        }

        if (types.HasFlag(OperationJsonType.Number))
        {
            writer.WriteNumberValue(0.5);
            return;
        }

        if (types.HasFlag(OperationJsonType.Boolean))
        {
            writer.WriteBooleanValue(property?.ConstantBoolean ?? false);
            return;
        }

        if (types.HasFlag(OperationJsonType.Array))
        {
            writer.WriteStartArray();
            int itemCount = property?.MinimumItems ?? 0;
            for (int index = 0; index < itemCount; index++)
            {
                if (property?.ItemTypes.HasFlag(OperationJsonType.String) == true)
                {
                    writer.WriteStringValue(property.ItemNonWhitespace ? "x" : string.Empty);
                }
                else
                {
                    WriteValidValue(writer, property?.ItemTypes ?? OperationJsonType.Null);
                }
            }

            writer.WriteEndArray();
            return;
        }

        if (types.HasFlag(OperationJsonType.Null))
        {
            writer.WriteNullValue();
            return;
        }

        throw new InvalidOperationException("The product schema has no supported JSON type.");
    }

    private static OperationRequest Request(string operation, string arguments) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        operation,
        Parse(arguments));

    private static OperationRequest PrivateRequest(string operation)
    {
        string missionId = Guid.NewGuid().ToString("D");
        string invocationId = Guid.NewGuid().ToString("D");
        string purpose = $"memory.arguments.v1|{operation}|{missionId}|{invocationId}";
        string ciphertext = Convert.ToBase64String(Encoding.UTF8.GetBytes("authenticated"));
        return new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            missionId,
            invocationId,
            operation,
            Parse(JsonSerializer.Serialize(new
            {
                version = 1,
                protection = "test",
                purpose,
                ciphertext,
            })));
    }

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    private sealed class CountingProductHandler(string operation) : IOperationHandler
    {
        public OperationDefinition Definition { get; } =
            ProductCatalog.CreateDefinition(operation);

        public int ExecutionCount { get; private set; }

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            if (PrivateOperationBoundary.IsPrivateOperation(Definition.Name))
            {
                JsonElement protectedResult = Parse(JsonSerializer.Serialize(new
                {
                    version = 1,
                    protection = "test",
                    purpose = $"memory.result.v1|{Definition.Name}|{invocation.MissionId}|{invocation.InvocationId}",
                    ciphertext = Convert.ToBase64String(Encoding.UTF8.GetBytes("authenticated")),
                }));
                return ValueTask.FromResult(OperationOutcome.PrivateSuccess(protectedResult));
            }

            return ValueTask.FromResult(OperationOutcome.Success(Parse("{}")));
        }
    }

    private sealed class SchemaGeneratedPrivateAuthenticator
        : IPrivateOperationEnvelopeAuthenticator, IPrivateOperationArgumentSchemaValidator
    {
        public bool AuthenticateArguments(OperationRequest request) => true;

        public bool AuthenticateResult(OperationRequest request, JsonElement result) => true;

        public bool ValidateArguments(
            OperationRequest request,
            OperationArgumentsSchema argumentsSchema)
        {
            using JsonDocument clear = JsonDocument.Parse(
                BuildValidArguments(argumentsSchema));
            return OperationArgumentValidator.IsValid(
                clear.RootElement,
                argumentsSchema);
        }
    }

    private sealed class StubPrivateAuthenticator(JsonElement clearPayload)
        : IPrivateOperationEnvelopeAuthenticator, IPrivateOperationArgumentSchemaValidator
    {
        public int SchemaValidationCount { get; private set; }

        public bool AuthenticateArguments(OperationRequest request) => true;

        public bool AuthenticateResult(OperationRequest request, JsonElement result) => true;

        public bool ValidateArguments(
            OperationRequest request,
            OperationArgumentsSchema argumentsSchema)
        {
            SchemaValidationCount++;
            return OperationArgumentValidator.IsValid(clearPayload, argumentsSchema);
        }
    }
}
