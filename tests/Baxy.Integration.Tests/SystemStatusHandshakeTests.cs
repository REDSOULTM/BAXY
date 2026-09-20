using System.Text.Json;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class SystemStatusHandshakeTests
{
    private static readonly OperationDescriptor[] RequiredCapabilities =
        ProductCatalog.ToolDescriptors
            .Select(static descriptor => ProductCatalog.CreateToolDescriptor(
                new OperationDefinition(descriptor)))
            .ToArray();

    [Test]
    public void ShellRequiresExactOrderedPublicToolCatalogAndExcludesInternalStatus()
    {
        ProtocolHello complete = CreateHello(RequiredCapabilities);
        ProtocolHello missing = CreateHello(
            RequiredCapabilities.Where(static capability => capability.Name != "system.status"));
        ProtocolHello withInternalStatus = CreateHello(
            [.. RequiredCapabilities, CreateInternalStatusDescriptor()]);
        ProtocolHello wrongRisk = CreateHello(
            Replace("system.status", static capability => capability with
            {
                Risk = OperationRisks.LowReversible,
            }));
        ProtocolHello wrongSchema = CreateHello(
            Replace("system.status", static capability => capability with
            {
                ArgumentsSchema = Parse(
                    """{"type":"object","properties":{},"required":[],"additionalProperties":false}"""),
            }));
        ProtocolHello wrongVerifier = CreateHello(
            Replace("system.status", static capability => capability with
            {
                VerifierContractId = "system.status.windows.measurement.v2",
            }));
        ProtocolHello wrongDescription = CreateHello(
            Replace("system.status", static capability => capability with
            {
                Description = capability.Description + " ",
            }));
        ProtocolHello duplicate = CreateHello(
            [.. RequiredCapabilities, RequiredCapabilities[^1]]);
        ProtocolHello reordered = CreateHello(RequiredCapabilities.Reverse());

        Assert.Multiple(() =>
        {
            // 170 → 191 descriptores (21 operaciones de C03; plan post-goal 2026-09-20, Fase 1 grupo B)
            // → 195 (weather.current, web.news.headlines, package.uninstall y shell.command.run; auditoría semántica REOPEN1993).
            Assert.That(ProductCatalog.Descriptors, Has.Count.EqualTo(195));
            Assert.That(ProductCatalog.ToolDescriptors, Has.Count.EqualTo(194));
            Assert.That(complete.Capabilities, Has.Count.EqualTo(194));
            Assert.That(
                complete.Capabilities.Select(static capability => capability.Name),
                Does.Not.Contain("app.status"));
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(complete), Is.True);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(missing), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(withInternalStatus), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongRisk), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongSchema), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongVerifier), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongDescription), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(duplicate), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(reordered), Is.False);
        });
    }

    private static ProtocolHello CreateHello(
        IEnumerable<OperationDescriptor> capabilities) => new(
        ProtocolTypes.Hello,
        ProtocolVersion.Current,
        "1.0.0",
        42,
        capabilities.ToArray());

    private static IEnumerable<OperationDescriptor> Replace(
        string operationName,
        Func<OperationDescriptor, OperationDescriptor> replacement) =>
        RequiredCapabilities.Select(capability => string.Equals(
            capability.Name,
            operationName,
            StringComparison.Ordinal)
                ? replacement(capability)
                : capability);

    private static OperationDescriptor CreateInternalStatusDescriptor()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("app.status");
        return new OperationDescriptor(
            descriptor.Name,
            Parse(descriptor.ArgumentsSchema.CanonicalJson),
            descriptor.Risk,
            descriptor.VerifierContractId,
            descriptor.Description);
    }

    private static JsonElement Parse(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        return document.RootElement.Clone();
    }
}
