using System.Text;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Contracts.Tests;

[TestFixture]
public sealed class ProtocolContractTests
{
    [TestCase(4096)]
    [TestCase(4097)]
    [TestCase(48_000)]
    public void OperationResponseMessageRoundTripsThroughItsDenseContract(int length)
    {
        const string prefix = "{\"observed\":{\"text\":\"";
        const string suffix = "\",\"layout\":{\"available\":true,\"lines\":[]}}}";
        string message = prefix + new string('x', length - prefix.Length - suffix.Length) + suffix;
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, NewId(), NewId(), NewId(),
            OperationStatuses.Completed, message, true, false, Json(message), null);

        byte[] encoded = ProtocolJson.SerializeToUtf8Bytes(response);
        byte[] bounded = ProtocolJson.SerializeBoundedToUtf8Bytes(response, 1024 * 1024);
        OperationResponse restored = ProtocolJson.DeserializeResponse(bounded);

        Assert.Multiple(() =>
        {
            Assert.That(message, Has.Length.EqualTo(length));
            Assert.That(bounded, Is.EqualTo(encoded));
            Assert.That(restored.Message, Is.EqualTo(message));
            Assert.That(restored.RequestId, Is.EqualTo(response.RequestId));
            Assert.That(restored.MissionId, Is.EqualTo(response.MissionId));
            Assert.That(restored.InvocationId, Is.EqualTo(response.InvocationId));
            Assert.That(restored.Status, Is.EqualTo(response.Status));
            Assert.That(restored.Verified, Is.True);
            Assert.That(restored.Replayed, Is.False);
            Assert.That(restored.Result!.Value.GetRawText(), Is.EqualTo(response.Result!.Value.GetRawText()));
        });
    }

    [Test]
    public void OperationResponseLimitCountsDecodedUtf16RatherThanWireEscapes()
    {
        string unicode = string.Concat(Enumerable.Repeat("á中🙂\"\\\n", 1000));
        string message = unicode + new string('x', 48_000 - unicode.Length);
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, NewId(), NewId(), NewId(),
            OperationStatuses.Completed, message, true, false, null, null);

        byte[] encoded = ProtocolJson.SerializeToUtf8Bytes(response);

        Assert.Multiple(() =>
        {
            Assert.That(encoded.Length, Is.GreaterThan(message.Length).And.LessThan(1024 * 1024));
            Assert.That(ProtocolJson.DeserializeResponse(encoded).Message, Is.EqualTo(message));
        });
    }

    [TestCase(null)]
    [TestCase("")]
    [TestCase("   ")]
    public void OperationResponseMessageStillRequiresNonWhitespace(string? message)
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, NewId(), NewId(), NewId(),
            OperationStatuses.Completed, message!, true, false, null, null);
        Assert.That(() => ProtocolJson.SerializeToUtf8Bytes(response), Throws.TypeOf<JsonException>());
    }

    [Test]
    public void OperationResponseRejectsMessageBeyondDenseLimitOnBothBoundaries()
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, NewId(), NewId(), NewId(),
            OperationStatuses.Completed, new string('x', 48_001), true, false, null, null);
        byte[] uncheckedWire = JsonSerializer.SerializeToUtf8Bytes(response, BaxyJsonContext.Default.OperationResponse);

        Assert.Multiple(() =>
        {
            Assert.That(() => ProtocolJson.SerializeToUtf8Bytes(response), Throws.TypeOf<JsonException>());
            Assert.That(() => ProtocolJson.DeserializeResponse(uncheckedWire), Throws.TypeOf<JsonException>());
        });
    }

    [TestCase(4096, true)]
    [TestCase(4097, false)]
    public void OtherProtocolTextFieldsKeepTheirOriginalLimit(int length, bool accepted)
    {
        string text = new('x', length);
        var descriptor = new OperationDescriptor("note.create", ClosedEmptyArgumentsSchema(),
            OperationRisks.LowReversible, "note.create.local.reopen.v1", text);
        var hello = new ProtocolHello(ProtocolTypes.Hello, ProtocolVersion.Current, text, 42,
            [descriptor with { Description = "Create a note." }]);
        var error = new ProtocolError(ProtocolTypes.ProtocolError, "malformed_json", text);
        TestDelegate[] checks = [() => ContractValidator.Validate(descriptor),
            () => ContractValidator.Validate(hello), () => ContractValidator.Validate(error)];
        foreach (TestDelegate check in checks)
        {
            if (accepted) Assert.That(check, Throws.Nothing);
            else Assert.That(check, Throws.TypeOf<JsonException>());
        }
    }

    [Test]
    public void ProtocolErrorRoundTripsStrictly()
    {
        var error = new ProtocolError(
            ProtocolTypes.ProtocolError,
            "malformed_json",
            "La solicitud no tiene un JSON válido.");

        byte[] json = ProtocolJson.SerializeToUtf8Bytes(error);
        ProtocolError restored = ProtocolJson.DeserializeError(json);

        Assert.That(restored, Is.EqualTo(error));
        Assert.That(
            () => ProtocolJson.DeserializeError(
                "{\"type\":\"protocol.error\",\"errorCode\":\"x\",\"message\":\"x\",\"extra\":true}"u8),
            Throws.InstanceOf<JsonException>());
    }

    [Test]
    public void Request_round_trip_preserves_every_field()
    {
        var expected = CreateRequest();

        var encoded = ProtocolJson.SerializeToUtf8Bytes(expected);
        var actual = ProtocolJson.DeserializeRequest(encoded);

        Assert.Multiple(() =>
        {
            Assert.That(actual.Type, Is.EqualTo(expected.Type));
            Assert.That(actual.RequestId, Is.EqualTo(expected.RequestId));
            Assert.That(actual.MissionId, Is.EqualTo(expected.MissionId));
            Assert.That(actual.InvocationId, Is.EqualTo(expected.InvocationId));
            Assert.That(actual.Operation, Is.EqualTo(expected.Operation));
            Assert.That(actual.Arguments.GetProperty("title").GetString(), Is.EqualTo("compras"));
            Assert.That(actual.ConfirmationToken, Is.Null);
        });
    }

    [Test]
    public void Optional_confirmation_token_round_trips_when_present()
    {
        string token = new('A', 43);
        OperationRequest expected = CreateRequest() with { ConfirmationToken = token };

        byte[] encoded = ProtocolJson.SerializeToUtf8Bytes(expected);
        OperationRequest actual = ProtocolJson.DeserializeRequest(encoded);

        Assert.That(actual.ConfirmationToken, Is.EqualTo(token));
        using var document = JsonDocument.Parse(encoded);
        Assert.That(document.RootElement.GetProperty("confirmationToken").GetString(), Is.EqualTo(token));
    }

    [Test]
    public void Missing_optional_confirmation_token_remains_wire_compatible()
    {
        OperationRequest request = CreateRequest();

        byte[] encoded = ProtocolJson.SerializeToUtf8Bytes(request);
        using var document = JsonDocument.Parse(encoded);
        OperationRequest restored = ProtocolJson.DeserializeRequest(encoded);

        Assert.Multiple(() =>
        {
            Assert.That(document.RootElement.TryGetProperty("confirmationToken", out _), Is.False);
            Assert.That(restored.ConfirmationToken, Is.Null);
        });
    }

    [Test]
    public void Hello_round_trip_carries_protocol_identity_and_capabilities()
    {
        var expected = new ProtocolHello(
            ProtocolTypes.Hello,
            ProtocolVersion.Current,
            "1.0.0",
            4242,
            [new OperationDescriptor(
                "note.create",
                ClosedEmptyArgumentsSchema(),
                OperationRisks.LowReversible,
                "note.create.local.reopen.v1",
                "Creates a local note.")]);

        byte[] encoded = ProtocolJson.SerializeToUtf8Bytes(expected);
        var actual = ProtocolJson.DeserializeHello(encoded);
        using JsonDocument document = JsonDocument.Parse(encoded);

        Assert.Multiple(() =>
        {
            Assert.That(actual.Protocol, Is.EqualTo("baxy.local.v1"));
            Assert.That(actual.CoreVersion, Is.EqualTo("1.0.0"));
            Assert.That(actual.Pid, Is.EqualTo(4242));
            Assert.That(actual.Capabilities, Has.Count.EqualTo(1));
            Assert.That(actual.Capabilities[0].Name, Is.EqualTo("note.create"));
            Assert.That(
                actual.Capabilities[0].ArgumentsSchema.GetRawText(),
                Is.EqualTo(ClosedEmptyArgumentsSchema().GetRawText()));
            Assert.That(actual.Capabilities[0].Risk, Is.EqualTo(OperationRisks.LowReversible));
            Assert.That(
                actual.Capabilities[0].VerifierContractId,
                Is.EqualTo("note.create.local.reopen.v1"));
            Assert.That(actual.Capabilities[0].Description, Is.EqualTo("Creates a local note."));
            Assert.That(actual.ApplicationCatalog, Is.Null);
            Assert.That(actual.GameCatalog, Is.Null);
            Assert.That(
                document.RootElement.TryGetProperty("applicationCatalog", out _),
                Is.False);
            Assert.That(
                document.RootElement.TryGetProperty("gameCatalog", out _),
                Is.False);
        });
    }

    [Test]
    public void Hello_round_trip_carries_a_bounded_verified_application_catalog()
    {
        var expected = new ProtocolHello(
            ProtocolTypes.Hello,
            ProtocolVersion.Current,
            "1.0.0",
            4242,
            [new OperationDescriptor(
                "app.open",
                ClosedEmptyArgumentsSchema(),
                OperationRisks.LowReversible,
                "app.open.process.window.focus.v1",
                "Opens an installed application.")],
            new ApplicationCatalogSnapshot(
                ApplicationCatalogContract.CurrentVersion,
                Verified: true,
                Complete: true,
                ["Paint", "Spotify", "Visual Studio Code"]));

        byte[] encoded = ProtocolJson.SerializeToUtf8Bytes(expected);
        ProtocolHello actual = ProtocolJson.DeserializeHello(encoded);
        using JsonDocument document = JsonDocument.Parse(encoded);
        JsonElement catalog = document.RootElement.GetProperty("applicationCatalog");

        Assert.Multiple(() =>
        {
            Assert.That(actual.ApplicationCatalog?.Version, Is.EqualTo(1));
            Assert.That(actual.ApplicationCatalog?.Verified, Is.True);
            Assert.That(actual.ApplicationCatalog?.Complete, Is.True);
            Assert.That(
                actual.ApplicationCatalog?.Names,
                Is.EqualTo(new[] { "Paint", "Spotify", "Visual Studio Code" }));
            Assert.That(
                catalog.EnumerateObject().Select(static property => property.Name),
                Is.EqualTo(new[] { "version", "verified", "complete", "names" }));
        });
    }

    [Test]
    public void Application_catalog_rejects_unverified_content()
    {
        var catalog = new ApplicationCatalogSnapshot(
            ApplicationCatalogContract.CurrentVersion,
            Verified: false,
            Complete: false,
            ["Paint"]);

        Assert.That(
            () => ContractValidator.Validate(catalog),
            Throws.TypeOf<JsonException>().With.Message.Contains("unverified"));
    }

    [Test]
    public void Application_catalog_rejects_names_that_collide_after_python_compatible_folding()
    {
        var catalog = new ApplicationCatalogSnapshot(
            ApplicationCatalogContract.CurrentVersion,
            Verified: true,
            Complete: true,
            ["Café", "Cafe"]);

        Assert.That(
            () => ContractValidator.Validate(catalog),
            Throws.TypeOf<JsonException>().With.Message.Contains("duplicate"));
    }

    [Test]
    public void Application_catalog_rejects_an_oversized_utf8_name()
    {
        var catalog = new ApplicationCatalogSnapshot(
            ApplicationCatalogContract.CurrentVersion,
            Verified: true,
            Complete: true,
            [new string('é', 257)]);

        Assert.That(
            () => ContractValidator.Validate(catalog),
            Throws.TypeOf<JsonException>().With.Message.Contains("oversized"));
    }

    [Test]
    public void Application_catalog_rejects_a_unicode_replacement_character()
    {
        var catalog = new ApplicationCatalogSnapshot(
            ApplicationCatalogContract.CurrentVersion,
            Verified: true,
            Complete: true,
            ["Configuraci\uFFFDn"]);

        Assert.That(
            () => ContractValidator.Validate(catalog),
            Throws.TypeOf<JsonException>().With.Message.Contains("invalid"));
    }

    [Test]
    public void Hello_round_trip_carries_a_bounded_verified_installed_game_catalog()
    {
        var expected = new ProtocolHello(
            ProtocolTypes.Hello,
            ProtocolVersion.Current,
            "1.0.0",
            4242,
            [new OperationDescriptor(
                "game.launch",
                ClosedEmptyArgumentsSchema(),
                OperationRisks.LowReversible,
                "game.launch.process.postread.v1",
                "Launches one installed game.")],
            ApplicationCatalog: null,
            new GameCatalogSnapshot(
                GameCatalogContract.CurrentVersion,
                Verified: true,
                Complete: true,
                [
                    new GameCatalogEntry("steam", "620", "Portal 2"),
                    new GameCatalogEntry("steam", "730", "Counter-Strike 2"),
                ]));

        byte[] encoded = ProtocolJson.SerializeToUtf8Bytes(expected);
        ProtocolHello actual = ProtocolJson.DeserializeHello(encoded);
        using JsonDocument document = JsonDocument.Parse(encoded);
        JsonElement catalog = document.RootElement.GetProperty("gameCatalog");

        Assert.Multiple(() =>
        {
            Assert.That(actual.GameCatalog?.Version, Is.EqualTo(1));
            Assert.That(actual.GameCatalog?.Verified, Is.True);
            Assert.That(actual.GameCatalog?.Complete, Is.True);
            Assert.That(
                actual.GameCatalog?.Entries,
                Is.EqualTo(new[]
                {
                    new GameCatalogEntry("steam", "620", "Portal 2"),
                    new GameCatalogEntry("steam", "730", "Counter-Strike 2"),
                }));
            Assert.That(
                catalog.EnumerateObject().Select(static property => property.Name),
                Is.EqualTo(new[] { "version", "verified", "complete", "entries" }));
            Assert.That(
                catalog.GetProperty("entries")[0]
                    .EnumerateObject()
                    .Select(static property => property.Name),
                Is.EqualTo(new[] { "provider", "appId", "name" }));
        });
    }

    [Test]
    public void Game_catalog_rejects_unverified_content()
    {
        var catalog = new GameCatalogSnapshot(
            GameCatalogContract.CurrentVersion,
            Verified: false,
            Complete: false,
            [new GameCatalogEntry("steam", "620", "Portal 2")]);

        Assert.That(
            () => ContractValidator.Validate(catalog),
            Throws.TypeOf<JsonException>().With.Message.Contains("unverified"));
    }

    [Test]
    public void Game_catalog_rejects_duplicate_provider_names_after_folding()
    {
        var catalog = new GameCatalogSnapshot(
            GameCatalogContract.CurrentVersion,
            Verified: true,
            Complete: true,
            [
                new GameCatalogEntry("steam", "620", "Portal 2"),
                new GameCatalogEntry("steam", "621", "Pórtal 2"),
            ]);

        Assert.That(
            () => ContractValidator.Validate(catalog),
            Throws.TypeOf<JsonException>().With.Message.Contains("duplicate"));
    }

    [TestCase("gog", "620")]
    [TestCase("steam", "620/evil")]
    public void Game_catalog_rejects_unauthenticated_identity_shapes(
        string provider,
        string appId)
    {
        var catalog = new GameCatalogSnapshot(
            GameCatalogContract.CurrentVersion,
            Verified: true,
            Complete: true,
            [new GameCatalogEntry(provider, appId, "Portal 2")]);

        Assert.That(
            () => ContractValidator.Validate(catalog),
            Throws.TypeOf<JsonException>());
    }

    [Test]
    public void Response_round_trip_preserves_verification_and_replay_evidence()
    {
        var expected = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            OperationStatuses.Completed,
            "Nota creada y verificada.",
            true,
            true,
            Json("""{"noteId":"n-1"}"""),
            null);

        var actual = ProtocolJson.DeserializeResponse(ProtocolJson.SerializeToUtf8Bytes(expected));

        Assert.Multiple(() =>
        {
            Assert.That(actual.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(actual.Verified, Is.True);
            Assert.That(actual.Replayed, Is.True);
            Assert.That(actual.Result?.GetProperty("noteId").GetString(), Is.EqualTo("n-1"));
            Assert.That(actual.ErrorCode, Is.Null);
        });
    }

    [Test]
    public void Response_round_trip_preserves_honesty_correction()
    {
        var expected = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            OperationStatuses.Failed,
            "No pude completar la petición solicitada.",
            false,
            false,
            null,
            "verification_failed",
            EffectMayHaveOccurred: true,
            CauseCode: "honesty_self_correction",
            HonestyCorrection: new HonestyCorrectionTrace(
                "Estoy entendiendo tu petición.",
                "verification_failed",
                "No pude completar la petición solicitada."));

        OperationResponse actual = ProtocolJson.DeserializeResponse(
            ProtocolJson.SerializeToUtf8Bytes(expected));

        Assert.Multiple(() =>
        {
            Assert.That(actual.HonestyCorrection, Is.EqualTo(expected.HonestyCorrection));
            Assert.That(actual.CauseCode, Is.EqualTo("honesty_self_correction"));
            Assert.That(actual.Verified, Is.False);
        });
    }

    [Test]
    public void Pending_response_round_trip_preserves_recovery_identity()
    {
        var expected = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            OperationStatuses.Pending,
            "Debo reconciliar el ajuste antes de continuar.",
            false,
            false,
            null,
            "audio_reconciliation_required");

        OperationResponse actual = ProtocolJson.DeserializeResponse(
            ProtocolJson.SerializeToUtf8Bytes(expected));

        Assert.Multiple(() =>
        {
            Assert.That(actual.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(actual.MissionId, Is.EqualTo(expected.MissionId));
            Assert.That(actual.InvocationId, Is.EqualTo(expected.InvocationId));
            Assert.That(actual.Verified, Is.False);
            Assert.That(actual.Replayed, Is.False);
            Assert.That(actual.ErrorCode, Is.EqualTo("audio_reconciliation_required"));
        });
    }

    [Test]
    public void Pending_response_cannot_claim_journal_replay()
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            OperationStatuses.Pending,
            "Debo reconciliar el ajuste.",
            false,
            true,
            null,
            "audio_reconciliation_required");

        Assert.That(
            () => ProtocolJson.SerializeToUtf8Bytes(response),
            Throws.TypeOf<JsonException>().With.Message.Contains("cannot be replayed"));
    }

    [Test]
    public void Request_json_names_and_order_are_stable_camel_case()
    {
        using var document = JsonDocument.Parse(ProtocolJson.SerializeToUtf8Bytes(CreateRequest()));
        var names = document.RootElement.EnumerateObject().Select(static property => property.Name).ToArray();

        Assert.That(
            names,
            Is.EqualTo(new[] { "type", "requestId", "missionId", "invocationId", "operation", "arguments" }));
    }

    [Test]
    public void Response_json_names_are_stable_even_when_nullable_fields_are_null()
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            OperationStatuses.Failed,
            "No se pudo completar.",
            false,
            false,
            null,
            "provider_failed");

        using var document = JsonDocument.Parse(ProtocolJson.SerializeToUtf8Bytes(response));
        var names = document.RootElement.EnumerateObject().Select(static property => property.Name).ToArray();

        Assert.That(
            names,
            Is.EqualTo(new[]
            {
                "type",
                "requestId",
                "missionId",
                "invocationId",
                "status",
                "message",
                "verified",
                "replayed",
                "result",
                "errorCode",
            }));
    }

    [Test]
    public void Missing_required_field_is_rejected()
    {
        var json = $$"""
            {
              "type": "operation.request",
              "requestId": "{{NewId()}}",
              "missionId": "{{NewId()}}",
              "operation": "note.create",
              "arguments": {}
            }
            """;

        Assert.That(
            () => ProtocolJson.DeserializeRequest(Encoding.UTF8.GetBytes(json)),
            Throws.TypeOf<JsonException>());
    }

    [Test]
    public void Malformed_json_is_rejected()
    {
        Assert.That(
            () => ProtocolJson.DeserializeRequest("{]"u8),
            Throws.TypeOf<JsonException>());
    }

    [Test]
    public void Unknown_message_type_is_rejected()
    {
        var request = CreateRequest() with { Type = "operation.future" };
        var json = JsonSerializer.SerializeToUtf8Bytes(request, BaxyJsonContext.Default.OperationRequest);

        Assert.That(
            () => ProtocolJson.DeserializeRequest(json),
            Throws.TypeOf<JsonException>().With.Message.Contains("unknown message type"));
    }

    [Test]
    public void Unknown_json_field_is_rejected()
    {
        var request = CreateRequest();
        var json = $$"""
            {
              "type": "{{request.Type}}",
              "requestId": "{{request.RequestId}}",
              "missionId": "{{request.MissionId}}",
              "invocationId": "{{request.InvocationId}}",
              "operation": "{{request.Operation}}",
              "arguments": {},
              "futureField": true
            }
            """;

        Assert.That(
            () => ProtocolJson.DeserializeRequest(Encoding.UTF8.GetBytes(json)),
            Throws.TypeOf<JsonException>());
    }

    [TestCase("")]
    [TestCase("00000000-0000-0000-0000-000000000000")]
    [TestCase("not-a-uuid")]
    [TestCase("A76D894A-0E70-4CA2-8D1C-05A27DCA0CF7")]
    [TestCase("{a76d894a-0e70-4ca2-8d1c-05a27dca0cf7}")]
    public void Invalid_or_noncanonical_identifiers_are_rejected(string identifier)
    {
        var request = CreateRequest() with { InvocationId = identifier };

        Assert.That(
            () => ProtocolJson.SerializeToUtf8Bytes(request),
            Throws.TypeOf<JsonException>().With.Message.Contains("invocationId"));
    }

    [TestCase("note")]
    [TestCase("Note.create")]
    [TestCase("note..create")]
    [TestCase("note.create-now")]
    [TestCase("note.1create")]
    [TestCase(" note.create")]
    public void Invalid_operation_names_are_rejected(string operation)
    {
        var request = CreateRequest() with { Operation = operation };

        Assert.That(
            () => ProtocolJson.SerializeToUtf8Bytes(request),
            Throws.TypeOf<JsonException>().With.Message.Contains("operation name"));
    }

    [TestCase("")]
    [TestCase("=")]
    [TestCase("abc=")]
    [TestCase("a b")]
    [TestCase("A")]
    [TestCase("AB")]
    [TestCase("AA+")]
    public void Invalid_or_noncanonical_confirmation_tokens_are_rejected(string token)
    {
        OperationRequest request = CreateRequest() with { ConfirmationToken = token };

        Assert.That(
            () => ProtocolJson.SerializeToUtf8Bytes(request),
            Throws.TypeOf<JsonException>().With.Message.Contains("confirmationToken"));
    }

    [Test]
    public void Oversized_confirmation_token_is_rejected()
    {
        OperationRequest request = CreateRequest() with
        {
            ConfirmationToken = new string('A', 129),
        };

        Assert.That(
            () => ProtocolJson.SerializeToUtf8Bytes(request),
            Throws.TypeOf<JsonException>().With.Message.Contains("at most 128"));
    }

    [Test]
    public void Null_json_and_non_object_arguments_are_rejected()
    {
        var request = CreateRequest() with { Arguments = Json("null") };

        Assert.That(
            () => ProtocolJson.SerializeToUtf8Bytes(request),
            Throws.TypeOf<JsonException>().With.Message.Contains("arguments"));
        Assert.That(
            () => ProtocolJson.DeserializeRequest("null"u8),
            Throws.TypeOf<JsonException>());
    }

    [Test]
    public void Unknown_status_and_risk_are_rejected()
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            "future",
            "Mensaje.",
            false,
            false,
            null,
            null);
        var descriptor = new OperationDescriptor(
            "note.create",
            ClosedEmptyArgumentsSchema(),
            "future",
            "note.create.local.reopen.v1",
            "Creates a note.");

        Assert.Multiple(() =>
        {
            Assert.That(() => ContractValidator.Validate(response), Throws.TypeOf<JsonException>());
            Assert.That(() => ContractValidator.Validate(descriptor), Throws.TypeOf<JsonException>());
        });
    }

    [Test]
    public void Privacy_sensitive_risk_is_a_valid_protocol_capability()
    {
        var descriptor = new OperationDescriptor(
            "memory.enable",
            ClosedEmptyArgumentsSchema(),
            OperationRisks.PrivacySensitive,
            "memory.enable.protected.status.v1",
            "Enables explicit local memory.");

        Assert.DoesNotThrow(() => ContractValidator.Validate(descriptor));
    }

    [TestCase("{}")]
    [TestCase("{\"type\":\"object\",\"properties\":{},\"required\":[],\"additionalProperties\":true}")]
    [TestCase("{\"type\":\"object\",\"properties\":{},\"required\":[]}")]
    [TestCase("{\"type\":\"object\",\"properties\":{},\"required\":[\"missing\"],\"additionalProperties\":false}")]
    public void Capability_requires_a_closed_arguments_schema(string schema)
    {
        var descriptor = new OperationDescriptor(
            "note.create",
            Json(schema),
            OperationRisks.LowReversible,
            "note.create.local.reopen.v1",
            "Creates a note.");

        Assert.That(
            () => ContractValidator.Validate(descriptor),
            Throws.TypeOf<JsonException>().With.Message.Contains("argumentsSchema"));
    }

    [TestCase("")]
    [TestCase("Note.create.local.reopen.v1")]
    [TestCase("note..create")]
    [TestCase("note-create")]
    [TestCase("note.create.")]
    public void Capability_requires_a_canonical_verifier_contract_id(string verifierContractId)
    {
        var descriptor = new OperationDescriptor(
            "note.create",
            ClosedEmptyArgumentsSchema(),
            OperationRisks.LowReversible,
            verifierContractId,
            "Creates a note.");

        Assert.That(
            () => ContractValidator.Validate(descriptor),
            Throws.TypeOf<JsonException>().With.Message.Contains("verifierContractId"));
    }

    [Test]
    public void Operation_contract_debug_strings_redact_arguments_results_and_bearers()
    {
        const string canary = "BAXY-PRIVATE-CANARY";
        const string token = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
        OperationRequest request = CreateRequest() with
        {
            Arguments = Json($"{{\"value\":\"{canary}\"}}"),
            ConfirmationToken = token,
        };
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Pending,
            canary,
            false,
            false,
            Json($"{{\"token\":\"{token}\",\"value\":\"{canary}\"}}"),
            "confirmation_required");

        Assert.Multiple(() =>
        {
            Assert.That(request.ToString(), Does.Not.Contain(canary));
            Assert.That(request.ToString(), Does.Not.Contain(token));
            Assert.That(response.ToString(), Does.Not.Contain(canary));
            Assert.That(response.ToString(), Does.Not.Contain(token));
        });
    }

    [Test]
    public void Bounded_response_is_byte_identical_when_it_already_fits()
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            OperationStatuses.Completed,
            "Nota creada y verificada.",
            true,
            false,
            Json("""{"noteId":"n-1"}"""),
            null);

        byte[] bounded = ProtocolJson.SerializeBoundedToUtf8Bytes(response, 1024 * 1024);

        Assert.That(bounded, Is.EqualTo(ProtocolJson.SerializeToUtf8Bytes(response)));
    }

    [Test]
    public void Bounded_response_elides_oversized_evidence_and_keeps_its_correlated_decision()
    {
        const int limit = 4096;
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            OperationStatuses.Failed,
            "No pude confirmar el envío.",
            false,
            false,
            Json($$"""{"evidence":"{{new string('e', limit * 2)}}"}"""),
            "external_effect_ambiguous",
            EffectMayHaveOccurred: true,
            CauseCode: "external_effect_ambiguous");

        Assert.That(
            ProtocolJson.SerializeToUtf8Bytes(response).Length,
            Is.GreaterThan(limit),
            "the unbounded response must exceed the limit for this test to be meaningful");

        byte[] bounded = ProtocolJson.SerializeBoundedToUtf8Bytes(response, limit);
        OperationResponse restored = ProtocolJson.DeserializeResponse(bounded);

        Assert.Multiple(() =>
        {
            Assert.That(bounded.Length, Is.LessThanOrEqualTo(limit));
            Assert.That(restored.RequestId, Is.EqualTo(response.RequestId));
            Assert.That(restored.MissionId, Is.EqualTo(response.MissionId));
            Assert.That(restored.InvocationId, Is.EqualTo(response.InvocationId));
            Assert.That(restored.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(restored.Message, Is.EqualTo(response.Message));
            Assert.That(restored.Verified, Is.False);
            Assert.That(restored.ErrorCode, Is.EqualTo("external_effect_ambiguous"));
            Assert.That(restored.EffectMayHaveOccurred, Is.True);
            Assert.That(restored.CauseCode, Is.EqualTo("external_effect_ambiguous"));
            Assert.That(restored.Result, Is.Null);
        });
    }

    [Test]
    public void Bounded_response_refuses_a_limit_that_cannot_carry_the_decision()
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            NewId(),
            NewId(),
            NewId(),
            OperationStatuses.Failed,
            "No se pudo completar.",
            false,
            false,
            Json("""{"noteId":"n-1"}"""),
            "provider_failed");

        Assert.Multiple(() =>
        {
            Assert.That(
                () => ProtocolJson.SerializeBoundedToUtf8Bytes(response, 32),
                Throws.TypeOf<JsonException>().With.Message.Contains("without evidence"));
            Assert.That(
                () => ProtocolJson.SerializeBoundedToUtf8Bytes(response, 0),
                Throws.TypeOf<ArgumentOutOfRangeException>());
        });
    }

    private static OperationRequest CreateRequest() =>
        new(
            ProtocolTypes.OperationRequest,
            NewId(),
            NewId(),
            NewId(),
            "note.create",
            Json("""{"title":"compras","body":"leche"}"""));

    private static string NewId() => Guid.NewGuid().ToString("D");

    private static JsonElement ClosedEmptyArgumentsSchema() =>
        Json("""{"type":"object","properties":{},"required":[],"additionalProperties":false}""");

    private static JsonElement Json(string value)
    {
        using var document = JsonDocument.Parse(value);
        return document.RootElement.Clone();
    }
}
