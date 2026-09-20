using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class ProductCatalogTests
{
    // C03 (2026-09-12 … 2026-09-20) creció el catálogo de 170 a 191 descriptores con estas 21
    // operaciones, cada una sellada por su tanda; la cifra se re-pina aquí junto a la lista nominal
    // (plan post-goal 2026-09-20, Fase 1 grupo B).
    internal static readonly string[] C03CatalogAdditions =
    [
        "audio.app.volume.adjust",
        "bluetooth.radio.status",
        "calculator.expression.evaluate",
        "client.channel.locate",
        "display.status",
        "document.pdf.read",
        "filesystem.known.list",
        "game.entitlement.named",
        "input.visible.controls",
        "message.draft",
        "message.send.test",
        "notification.list",
        "software.python.package.status",
        "software.python.status",
        "storage.removable.list",
        "wifi.radio.set",
        "wifi.radio.status",
        "wifi.scan",
        "window.close.all",
        "window.minimize.all",
        "window.snap",
    ];

    // Auditoría semántica 2026-09-20 (REOPEN1993): herramientas tipadas que la
    // encuesta pedía y el catálogo no tenía.
    internal static readonly string[] Reopen1993CatalogAdditions =
    [
        "weather.current",
        "web.news.headlines",
    ];

    internal const int ExpectedDescriptors = 170 + 21 + 2;

    internal const int ExpectedTools = ExpectedDescriptors - 1;

    [TestCase("{\"process\":\"*\"}", true)]
    [TestCase("{\"process\":\"*\",\"limit\":50,\"offset\":50}", true)]
    [TestCase("{\"process\":\"*\",\"byTitle\":true}", true)]
    [TestCase("{\"process\":\"editor.exe\",\"offset\":0}", true)]
    // CLOSE1060 (b7d005955): the flat v3 schema types both selectors and requires
    // neither; WindowResolveHandler enforces «exactly one» before any OS read.
    [TestCase("{}", true)]
    [TestCase("{\"process\":\"\"}", false)]
    [TestCase("{\"process\":\" \"}", false)]
    [TestCase("{\"process\":\"*\",\"offset\":-1}", false)]
    [TestCase("{\"process\":\"*\",\"offset\":0.5}", false)]
    [TestCase("{\"process\":\"*\",\"limit\":51}", false)]
    [TestCase("{\"process\":\"*\",\"limit\":0}", false)]
    [TestCase("{\"all\":true}", false)]
    public void WindowInventoryRemainsAReadOnlyBoundedOperationWithAnExplicitSelector(string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("window.resolve");
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(expected));
            // v2 → v3: CLOSE1060 (b7d005955) añadió el selector applicationName a window.resolve.
            Assert.That(descriptor.VerifierContractId, Is.EqualTo("window.resolve.identity.inventory.v3"));
        });
    }

    [TestCase("{\"applicationName\":\"Calculadora\"}", true)]
    [TestCase("{\"applicationName\":\" \"}", false)]
    public void WindowInventoryAcceptsTheApplicationNameSelectorOfV3(string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("window.resolve");
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(expected));
    }

    [Test]
    public void CatalogHasStableUniqueCompleteToolDescriptors()
    {
        ProductOperationDescriptor[] descriptors = ProductCatalog.Descriptors.ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(descriptors, Has.Length.EqualTo(ExpectedDescriptors));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Is.SupersetOf(C03CatalogAdditions));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Is.SupersetOf(Reopen1993CatalogAdditions));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Is.EqualTo(descriptors.Select(static descriptor => descriptor.Name)
                    .Order(StringComparer.Ordinal)));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name).Distinct(StringComparer.Ordinal),
                Is.EquivalentTo(descriptors.Select(static descriptor => descriptor.Name)));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.VerifierContractId)
                    .Distinct(StringComparer.Ordinal).Count(),
                Is.EqualTo(descriptors.Length));
            Assert.That(descriptors.All(static descriptor =>
                OperationRisks.IsKnown(descriptor.Risk)), Is.True);
            Assert.That(descriptors.All(static descriptor =>
                descriptor.ArgumentsSchema.AdditionalProperties is false), Is.True);
            Assert.That(descriptors.All(static descriptor =>
                !string.IsNullOrWhiteSpace(descriptor.VerifierContractId)), Is.True);
            Assert.That(
                ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name),
                Is.EqualTo(descriptors
                    .Where(static descriptor => descriptor.Name != "app.status")
                    .Select(static descriptor => descriptor.Name)));
            Assert.That(ProductCatalog.ToolDescriptors, Has.Count.EqualTo(ExpectedTools));
            Assert.That(
                ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name),
                Does.Not.Contain("app.status"));
            Assert.That(
                ProductCatalog.GetRequired("app.status").ToolExposure,
                Is.EqualTo(ToolExposure.Internal));
        });
    }

    [Test]
    public void PublicToolProjectionCarriesTheExactSchemaRiskVerifierAndDescription()
    {
        OperationDescriptor[] tools = ProductCatalog.ToolDescriptors
            .Select(static descriptor => ProductCatalog.CreateToolDescriptor(
                new OperationDefinition(descriptor)))
            .ToArray();

        Assert.That(tools, Has.Length.EqualTo(ExpectedTools));
        for (int index = 0; index < tools.Length; index++)
        {
            ProductOperationDescriptor product = ProductCatalog.ToolDescriptors[index];
            OperationDescriptor tool = tools[index];
            Assert.Multiple(() =>
            {
                Assert.That(tool.Name, Is.EqualTo(product.Name));
                Assert.That(
                    tool.ArgumentsSchema.GetRawText(),
                    Is.EqualTo(product.ArgumentsSchema.CanonicalJson),
                    product.Name);
                Assert.That(tool.Risk, Is.EqualTo(product.Risk), product.Name);
                Assert.That(
                    tool.VerifierContractId,
                    Is.EqualTo(product.VerifierContractId),
                    product.Name);
                Assert.That(tool.Description, Is.EqualTo(product.Description), product.Name);
            });
        }

        Assert.That(
            () => ProductCatalog.CreateToolDescriptor(ProductCatalog.CreateDefinition("app.status")),
            Throws.ArgumentException);
    }

    [Test]
    public void HistoricalCdpInspectionCapabilitiesArePrivateBoundedAndReadOnlyInEffect()
    {
        ProductOperationDescriptor page = ProductCatalog.GetRequired("browser.page.read");
        ProductOperationDescriptor tabs = ProductCatalog.GetRequired("browser.tabs.list");

        Assert.Multiple(() =>
        {
            Assert.That(page.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(tabs.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(page.VerifierContractId,
                Is.EqualTo("browser.page.read.cdp.dom.snapshot.v1"));
            Assert.That(tabs.VerifierContractId,
                Is.EqualTo("browser.tabs.list.cdp.targets.snapshot.v1"));
            Assert.That(page.ArgumentsSchema.CanonicalJson,
                Does.Contain("\"maximumCharacters\""));
            Assert.That(tabs.ArgumentsSchema.CanonicalJson, Does.Contain("\"limit\""));
        });
    }

    [Test]
    public void AudioStatusIsPublicReadOnlyAndAcceptsOnlyEmptyArguments()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("audio.status");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"scope\":\"output\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("audio.status.endpoint.read.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement,
                descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement,
                descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void MediaStatusIsPublicReadOnlyAndAcceptsOnlyEmptyArguments()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("media.status");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"provider\":\"spotify\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
            Assert.That(descriptor.VerifierContractId, Is.EqualTo("media.status.smtc.read.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement,
                descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement,
                descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void KeyPressIsPublicBoundedAndRejectsUnsafeCombinations()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("input.key.press");
        using JsonDocument escape = JsonDocument.Parse("{\"key\":\"escape\"}");
        using JsonDocument altF4 = JsonDocument.Parse("{\"key\":\"alt+f4\"}");
        using JsonDocument extra = JsonDocument.Parse("{\"key\":\"escape\",\"repeat\":2}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.LowReversible));
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("input.key.press.win32.sendinput.accepted.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                escape.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                altF4.RootElement, descriptor.ArgumentsSchema), Is.False);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void ClipboardPasteIsPrivacySensitiveClosedAndUsesFocusedClipboardVerifier()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("clipboard.paste");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"text\":\"secret\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("clipboard.paste.win32.clipboard.foreground.sendinput.accepted.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void ClipboardCopyIsPrivacySensitiveAndRequiresClipboardSequencePostread()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("clipboard.copy");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("clipboard.copy.win32.foreground.sendinput.sequence.postread.v1"));
        });
    }

    // Decisión del dueño 2026-09-13 (DECISIONES_DUENO_2026-09-13.md §6, NETWORK1201, 0fed0df6c): la IP
    // propia se lee a pedido sin confirmación; el riesgo pasó de privacy_sensitive a read_only.
    [Test]
    public void NetworkIpListIsReadOnlyClosedAndDoubleReadVerified()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("network.ip.list");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"scope\":\"public\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("network.ip.list.windows.unicast.secondread.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void WifiStatusIsReadOnlyClosedAndDoubleReadVerified()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("wifi.status");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"includeSsid\":true}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(
                RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), operation: descriptor.Name),
                Is.EqualTo(PolicyDecision.Allow));
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("wifi.status.netsh.wlan.secondread.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void PowerTransitionsAllowSessionSignoutWithoutConfirmation()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("system.power");
        using JsonDocument signout = JsonDocument.Parse("{\"action\":\"signout\"}");
        using JsonDocument shutdown = JsonDocument.Parse("{\"action\":\"shutdown\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.WorkLoss));
            Assert.That(
                RiskPolicy.Evaluate(
                    ProductCatalog.ToPolicyRisk(descriptor.Risk),
                    operation: descriptor.Name),
                Is.EqualTo(PolicyDecision.Allow));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("system.power.windows.transition.receipt.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                signout.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                shutdown.RootElement, descriptor.ArgumentsSchema), Is.True);
        });
    }

    [Test]
    public void WorkLossChallengesInNormalModeAndBypassSkipsIt()
    {
        ProductOperationDescriptor recycle = ProductCatalog.GetRequired("system.recyclebin.empty");
        ProductOperationDescriptor close = ProductCatalog.GetRequired("app.close");
        ProductOperationDescriptor overwrite = ProductCatalog.GetRequired("memory.forget");

        Assert.Multiple(() =>
        {
            Assert.That(recycle.Risk, Is.EqualTo(OperationRisks.WorkLoss));
            Assert.That(close.Risk, Is.EqualTo(OperationRisks.WorkLoss));
            Assert.That(overwrite.Risk, Is.EqualTo(OperationRisks.WorkLoss));
            Assert.That(
                RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(recycle.Risk)),
                Is.EqualTo(PolicyDecision.RequireConfirmation));
            Assert.That(
                RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(close.Risk)),
                Is.EqualTo(PolicyDecision.RequireConfirmation));
            Assert.That(
                RiskPolicy.Evaluate(
                    ProductCatalog.ToPolicyRisk(recycle.Risk),
                    ConfirmationMode.Bypass),
                Is.EqualTo(PolicyDecision.Allow));
        });
    }

    [Test]
    public void MediaSeekIsPublicReversibleAndBoundsTheRelativeDelta()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("media.seek.relative");
        using JsonDocument valid = JsonDocument.Parse("{\"seconds\":-15}");
        using JsonDocument zero = JsonDocument.Parse("{\"seconds\":0}");
        using JsonDocument excessive = JsonDocument.Parse("{\"seconds\":3601}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.LowReversible));
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("media.seek.relative.smtc.timeline.postread.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                valid.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                zero.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                excessive.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void EverySchemaIsClosedCanonicalAndSelfDescribing()
    {
        foreach (ProductOperationDescriptor descriptor in ProductCatalog.Descriptors)
        {
            OperationArgumentsSchema schema = descriptor.ArgumentsSchema;
            using JsonDocument document = JsonDocument.Parse(schema.CanonicalJson);
            JsonElement root = document.RootElement;

            Assert.Multiple(() =>
            {
                Assert.That(root.GetProperty("type").GetString(), Is.EqualTo("object"), descriptor.Name);
                Assert.That(root.GetProperty("additionalProperties").GetBoolean(), Is.False, descriptor.Name);
                Assert.That(root.GetProperty("properties").EnumerateObject()
                    .Select(static property => property.Name),
                    Is.EqualTo(schema.Properties.Select(static property => property.Name)),
                    descriptor.Name);
                Assert.That(root.GetProperty("required").EnumerateArray()
                    .Select(static item => item.GetString()),
                    Is.EqualTo(schema.Required),
                    descriptor.Name);
                Assert.That(root.GetRawText(), Is.EqualTo(schema.CanonicalJson), descriptor.Name);
            });
        }
    }

    [TestCase("{\"level\":0}", true)]
    [TestCase("{\"level\":100}", true)]
    [TestCase("{\"level\":-1}", false)]
    [TestCase("{\"level\":101}", false)]
    [TestCase("{\"level\":1.0}", false)]
    [TestCase("{\"level\":\"50\"}", false)]
    [TestCase("{\"level\":50,\"extra\":true}", false)]
    [TestCase("{}", false)]
    public void ValidatorRejectsExtraWrongTypeMissingAndOutOfRangeArguments(
        string json,
        bool expected)
    {
        using JsonDocument document = JsonDocument.Parse(json);

        bool valid = OperationArgumentValidator.IsValid(
            document.RootElement,
            ProductCatalog.GetRequired("audio.volume").ArgumentsSchema);

        Assert.That(valid, Is.EqualTo(expected));
    }

    [Test]
    public void RegistryAndCatalogAreOneToOneByExactDescriptorIdentity()
    {
        var exact = new OperationRegistry(ProductCatalog.Descriptors.Select(
            static descriptor => (IOperationHandler)new StubHandler(
                ProductCatalog.CreateDefinition(descriptor.Name))));
        IOperationHandler[] altered = ProductCatalog.Descriptors.Select(
                static descriptor => (IOperationHandler)new StubHandler(
                    ProductCatalog.CreateDefinition(descriptor.Name)))
            .ToArray();
        altered[0] = new StubHandler(new OperationDefinition(
            altered[0].Definition.Name,
            altered[0].Definition.Risk,
            altered[0].Definition.Description));
        var nonCatalogRegistry = new OperationRegistry(altered);

        Assert.Multiple(() =>
        {
            Assert.That(() => ProductCatalog.ValidateAgainst(exact), Throws.Nothing);
            Assert.That(
                () => ProductCatalog.ValidateAgainst(nonCatalogRegistry),
                Throws.InvalidOperationException);
            Assert.That(exact.Definitions.All(static definition =>
                definition.ProductDescriptor is not null), Is.True);
            Assert.That(exact.Definitions, Has.Count.EqualTo(ExpectedDescriptors));
            Assert.That(exact.ToolDefinitions, Has.Count.EqualTo(ExpectedTools));
            Assert.That(exact.ToolDescriptors, Has.Count.EqualTo(ExpectedTools));
            Assert.That(
                exact.ToolDefinitions.Select(static definition => definition.Name),
                Is.EqualTo(ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name)));
            Assert.That(
                exact.ToolDescriptors.Select(static descriptor => descriptor.Name),
                Is.EqualTo(ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name)));
            Assert.That(
                exact.ToolDefinitions.Select(static definition => definition.Name),
                Does.Not.Contain("app.status"));
        });
    }

    [Test]
    public void NullableEnumHasMatchingCanonicalSchemaAndRuntimeValidation()
    {
        OperationArgumentsSchema schema = ProductCatalog.GetRequired("note.list").ArgumentsSchema;
        using JsonDocument supplied = JsonDocument.Parse("{\"scope\":null}");
        using JsonDocument canonical = JsonDocument.Parse(schema.CanonicalJson);
        JsonElement scope = canonical.RootElement
            .GetProperty("properties")
            .GetProperty("scope");

        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.IsValid(supplied.RootElement, schema), Is.True);
            Assert.That(scope.GetProperty("type").EnumerateArray()
                .Select(static value => value.GetString()),
                Is.EqualTo(new string?[] { "null", "string" }));
            Assert.That(scope.GetProperty("enum").EnumerateArray().First().ValueKind,
                Is.EqualTo(JsonValueKind.Null));
        });
    }

    [Test]
    public void CatalogAssemblyHasNoParserPlannerOrModelRuntimeDependency()
    {
        string[] references = typeof(ProductCatalog).Assembly
            .GetReferencedAssemblies()
            .Select(static assembly => assembly.Name ?? string.Empty)
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(references, Does.Not.Contain("Baxy.App"));
            Assert.That(references, Does.Not.Contain("Baxy.Core"));
            Assert.That(references.Any(static reference =>
                reference.Contains("Parser", StringComparison.OrdinalIgnoreCase)
                || reference.Contains("Planner", StringComparison.OrdinalIgnoreCase)
                || reference.Contains("ModelRuntime", StringComparison.OrdinalIgnoreCase)),
                Is.False);
        });
    }

    private sealed class StubHandler(OperationDefinition definition) : IOperationHandler
    {
        public OperationDefinition Definition { get; } = definition;

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(OperationOutcome.Success(
                JsonDocument.Parse("{}").RootElement.Clone()));
        }
    }
}
