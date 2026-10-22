using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.Memory;

[TestFixture]
public sealed class LocalMemoryStoreTests
{
    private static readonly DateTimeOffset Start =
        new(2026, 7, 15, 10, 0, 0, TimeSpan.Zero);

    [Test]
    public void StoreIsDefaultOffAndConfigureIsDurablyIdempotent()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        MutableTimeProvider clock = new(Start);
        LocalMemoryStore store = CreateStore(temporary.Path, protector, clock);

        Assert.That(
            () => store.Save(Save("save-while-disabled", "color", "azul")),
            Throws.TypeOf<MemoryDisabledException>());

        MemoryConfigurationResult enabled = store.Configure(new("configure-1", Enabled: true));
        MemoryConfigurationResult replay = store.Configure(new("configure-1", Enabled: true));
        LocalMemoryStore restarted = CreateStore(temporary.Path, protector, clock);

        Assert.Multiple(() =>
        {
            Assert.That(enabled, Is.EqualTo(new MemoryConfigurationResult(true, false)));
            Assert.That(replay, Is.EqualTo(new MemoryConfigurationResult(true, true)));
            Assert.That(
                () => restarted.Configure(new("configure-1", Enabled: false)),
                Throws.TypeOf<MemoryInvocationConflictException>());
            Assert.That(
                () => restarted.Save(Save("save-after-restart", "color", "azul")),
                Throws.Nothing);
        });
    }

    [Test]
    public void SaveRestartRecallNormalizesSelectorAndLeavesNoPlaintextAtRest()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        const string canary = "CANARY-memory-value-7729";

        MemorySaveResult saved = store.Save(new MemorySaveRequest(
            "save-1",
            "  Color   favorito ",
            "Color favorito",
            canary,
            MemoryKind.Preference,
            Tags: ["perfil", " color "]));
        LocalMemoryStore restarted = CreateStore(temporary.Path, protector);
        MemoryRecord recalled = restarted.Recall(new("color favorito")).Records.Single();

        Assert.Multiple(() =>
        {
            Assert.That(saved.RecordId, Is.Not.EqualTo(Guid.Empty));
            Assert.That(saved.Selector, Is.EqualTo("COLOR FAVORITO"));
            Assert.That(recalled.Id, Is.EqualTo(saved.RecordId));
            Assert.That(recalled.Value, Is.EqualTo(canary));
            Assert.That(recalled.Origin, Is.EqualTo(MemoryOrigin.Explicit));
            Assert.That(recalled.Tags, Is.EqualTo(new[] { "COLOR", "PERFIL" }));
            Assert.That(GetManagedBytes(temporary.Path), Has.None.Contains(canary));
        });
    }

    [Test]
    public void SameSelectorAndValueReturnsSameRecordButDifferentValueConflicts()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);

        MemorySaveResult first = store.Save(Save("save-1", "proyecto", "BAXY"));
        MemorySaveResult equivalent = store.Save(Save("save-2", " PROYECTO ", "BAXY"));

        Assert.Multiple(() =>
        {
            Assert.That(equivalent.RecordId, Is.EqualTo(first.RecordId));
            Assert.That(equivalent.Revision, Is.EqualTo(1));
            Assert.That(
                () => store.Save(Save("save-3", "proyecto", "otro")),
                Throws.TypeOf<MemoryConflictException>());
            Assert.That(
                () => store.Save(new MemorySaveRequest(
                    "save-sensitive",
                    "proyecto",
                    "proyecto",
                    "BAXY",
                    Sensitivity: MemorySensitivity.Personal)),
                Throws.TypeOf<MemoryConflictException>());
            Assert.That(
                () => store.Save(new MemorySaveRequest(
                    "save-tags",
                    "proyecto",
                    "proyecto",
                    "BAXY",
                    Tags: ["different"])),
                Throws.TypeOf<MemoryConflictException>());
            Assert.That(
                () => store.Save(new MemorySaveRequest(
                    "save-temporary",
                    "proyecto",
                    "proyecto",
                    "BAXY",
                    Retention: MemoryRetention.Temporary,
                    ExpiresAtUtc: DateTimeOffset.UtcNow.AddDays(1))),
                Throws.TypeOf<MemoryConflictException>());
            Assert.That(store.List(new()).Records, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public void CorrectUsesCompareAndSwapAndNeverOverwritesAStaleRevision()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        MemorySaveResult saved = store.Save(Save("save-1", "editor", "Bloc de notas"));

        MemoryCorrectRequest correction = new(
            "correct-1",
            "editor",
            "Visual Studio Code",
            ExpectedRevision: saved.Revision);
        MemoryCorrectResult corrected = store.Correct(correction);
        MemoryCorrectResult replay = store.Correct(correction);

        Assert.Multiple(() =>
        {
            Assert.That(corrected.Revision, Is.EqualTo(2));
            Assert.That(replay with { Replayed = false }, Is.EqualTo(corrected));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(
                () => store.Correct(new(
                    "correct-2",
                    "editor",
                    "otro",
                    ExpectedRevision: 1)),
                Throws.TypeOf<MemoryConflictException>());
            Assert.That(store.Recall(new("editor")).Records.Single().Value,
                Is.EqualTo("Visual Studio Code"));
        });
    }

    [Test]
    public void CorrectCanCompareAgainstTheExpectedOldValue()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        _ = store.Save(Save("save", "ciudad", "Curicó"));

        MemoryCorrectResult corrected = store.Correct(new(
            "correct",
            "ciudad",
            "Santiago",
            ExpectedValue: "Curicó"));

        Assert.Multiple(() =>
        {
            Assert.That(corrected.Revision, Is.EqualTo(2));
            Assert.That(store.Recall(new("ciudad")).Records.Single().Value, Is.EqualTo("Santiago"));
        });
    }

    [Test]
    public void ExactAndAllForgetSurviveRestartWithoutRecoveryResurrection()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        _ = store.Save(Save("save-a", "color", "azul"));
        _ = store.Save(Save("save-b", "ciudad", "Santiago"));

        MemoryForgetResult exact = store.Forget(new("forget-color", MemoryForgetScope.Exact, Selector: "color"));
        LocalMemoryStore afterExact = CreateStore(temporary.Path, protector);
        MemoryForgetResult all = afterExact.Forget(new("forget-all", MemoryForgetScope.All));
        LocalMemoryStore afterAll = CreateStore(temporary.Path, protector);

        Assert.Multiple(() =>
        {
            Assert.That(exact.DeletedCount, Is.EqualTo(1));
            Assert.That(afterExact.Recall(new("color")).Records, Is.Empty);
            Assert.That(all.DeletedCount, Is.EqualTo(1));
            Assert.That(afterAll.List(new()).Records, Is.Empty);
            Assert.That(File.Exists(Path.Combine(temporary.Path, "mutation.intent")), Is.False);
            Assert.That(File.ReadAllBytes(Path.Combine(temporary.Path, "current.bin")),
                Is.EqualTo(File.ReadAllBytes(Path.Combine(temporary.Path, "recovery.bin"))));
        });
    }

    // Auditoría final G4: a topic forgets the memory that is that selector or carries that tag, never one whose
    // selector, label or tags merely contain it («color» never takes «color favorito» nor the tag «colores»).
    [Test]
    public void TopicForgetDeletesOnlyTheExactSelectorOrTag()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        _ = store.Save(Save("save-a", "color", "azul"));
        _ = store.Save(Save("save-b", "color favorito", "verde"));
        _ = store.Save(new MemorySaveRequest("save-c", "pintura", "pintura", "óleo", Tags: [" Color "]));
        _ = store.Save(new MemorySaveRequest("save-d", "paleta", "paleta", "pastel", Tags: ["colores"]));

        MemoryForgetResult forgotten = store.Forget(new("forget-topic", MemoryForgetScope.Topic, Topic: "COLOR"));

        Assert.Multiple(() =>
        {
            Assert.That(forgotten.DeletedCount, Is.EqualTo(2));
            Assert.That(store.List(new()).Records.Select(record => record.Selector),
                Is.EquivalentTo(new[] { "COLOR FAVORITO", "PALETA" }));
        });
    }

    // Auditoría final 2 (otros proveedores, 6): recall «exact» is the memory named so, folded in case, accents and
    // spacing; «color» never brings «color favorito», nor a label or a tag that contains it.
    [Test]
    public void ExactRecallMatchesTheFoldedSelectorOnly()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        _ = store.Save(Save("save-a", "canción", "Yesterday"));
        _ = store.Save(Save("save-b", "canción favorita", "Help"));
        _ = store.Save(new MemorySaveRequest("save-c", "disco", "mi canción", "Abbey Road", Tags: ["canción"]));

        Assert.Multiple(() =>
        {
            Assert.That(store.Recall(new("  CANCION ")).Records.Select(record => record.Value),
                Is.EqualTo(new[] { "Yesterday" }));
            Assert.That(store.Recall(new("canc")).Records, Is.Empty);
        });
    }

    // Auditoría final 2 (otros proveedores, 7): a forget is read back with its own criterion; the memories of another
    // kind or topic that remain do not make it look undone.
    [Test]
    public void HoldsReadsAForgetBackWithItsOwnCriterion()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        _ = store.Save(Save("save-a", "color", "azul"));
        _ = store.Save(new MemorySaveRequest("save-b", "pintura", "pintura", "óleo", Tags: ["color"]));
        _ = store.Save(Save("save-c", "ciudad", "Santiago"));
        var topic = new MemoryForgetRequest("forget-topic", MemoryForgetScope.Topic, Topic: "color");

        bool before = store.Holds(topic);
        MemoryForgetResult forgotten = store.Forget(topic);

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.True);
            Assert.That(forgotten.DeletedCount, Is.EqualTo(2));
            Assert.That(store.Holds(topic), Is.False);
            Assert.That(store.Holds(new MemoryForgetRequest("check-all", MemoryForgetScope.All)), Is.True);
        });
    }

    [Test]
    public void BeginningANewSessionPurgesTheOldSessionAndPreservesPersistentRecords()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        _ = store.Save(Save("persistent", "modo", "corto"));
        MemoryBeginSessionResult beganA = store.BeginSession(new("session-a"));
        _ = store.Save(new MemorySaveRequest(
            "session-a",
            "turno",
            "Turno",
            "primero",
            Retention: MemoryRetention.Session,
            SessionId: "session-a"));
        Assert.That(store.List(new(SessionId: "session-a")).Records.Select(record => record.Value),
            Is.EquivalentTo(new[] { "corto", "primero" }));

        MemoryBeginSessionResult beganB = store.BeginSession(new("session-b"));
        _ = store.Save(new MemorySaveRequest(
            "session-b",
            "turno",
            "Turno",
            "segundo",
            Retention: MemoryRetention.Session,
            SessionId: "session-b"));

        MemoryForgetResult forgotten = store.Forget(new(
            "forget-session-b",
            MemoryForgetScope.Session,
            SessionId: "session-b"));

        Assert.Multiple(() =>
        {
            Assert.That(beganA, Is.EqualTo(new MemoryBeginSessionResult(0, true)));
            Assert.That(beganB, Is.EqualTo(new MemoryBeginSessionResult(1, true)));
            Assert.That(forgotten.DeletedCount, Is.EqualTo(1));
            Assert.That(store.List(new(SessionId: "session-b")).Records.Select(record => record.Value),
                Is.EqualTo(new[] { "corto" }));
            Assert.That(
                () => store.List(new(SessionId: "session-a")),
                Throws.TypeOf<MemoryConflictException>());
            Assert.That(
                store.BeginSession(new("session-b")),
                Is.EqualTo(new MemoryBeginSessionResult(0, false)));
        });
    }

    [Test]
    public void StatusWorksWhileDisabledAndInspectionCanReturnEveryBoundedRecord()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 110,
            maximumReceipts: 120);
        MemoryStatusResult disabled = store.Status(new());
        _ = store.Configure(new("configure", true));
        for (int index = 0; index < 101; index++)
        {
            _ = store.Save(Save(
                $"save-{index}",
                $"selector-{index:D3}",
                index.ToString(CultureInfo.InvariantCulture)));
        }

        MemoryListResult all = store.List(new(MaximumResults: 101));
        MemoryStatusResult enabled = store.Status(new());

        Assert.Multiple(() =>
        {
            Assert.That(disabled.Enabled, Is.False);
            Assert.That(disabled.TotalRecords, Is.Zero);
            Assert.That(all.Records, Has.Count.EqualTo(101));
            Assert.That(enabled.Enabled, Is.True);
            Assert.That(enabled.TotalRecords, Is.EqualTo(101));
            Assert.That(enabled.PersistentRecords, Is.EqualTo(101));
            Assert.That(enabled.MaximumRecords, Is.EqualTo(110));
        });
    }

    [Test]
    public void TemporaryMemoryExpiresAndClockRollbackCannotReviveIt()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        MutableTimeProvider clock = new(Start);
        LocalMemoryStore store = EnabledStore(temporary.Path, protector, clock);
        _ = store.Save(new MemorySaveRequest(
            "temporary",
            "reunion",
            "Reunión",
            "a las 11",
            Retention: MemoryRetention.Temporary,
            ExpiresAtUtc: Start.AddMinutes(10)));
        Assert.That(
            () => store.Save(new MemorySaveRequest(
                "effectively-permanent",
                "future",
                "Future",
                "too far",
                Retention: MemoryRetention.Temporary,
                ExpiresAtUtc: Start.Add(LocalMemoryStore.MaximumTemporaryLifetime).AddTicks(1))),
            Throws.TypeOf<ArgumentException>());

        clock.UtcNow = Start.AddMinutes(11);
        Assert.That(store.Recall(new("reunion")).Records, Is.Empty);
        clock.UtcNow = Start.AddMinutes(1);
        Assert.That(store.Recall(new("reunion")).Records, Is.Empty);

        LocalMemoryStore restarted = CreateStore(temporary.Path, protector, clock);
        Assert.That(restarted.Recall(new("reunion")).Records, Is.Empty);
    }

    [Test]
    public void ReadsDoNotRewriteTheStoreUntilTheClockMovesAnHourOrSomethingExpires()
    {
        // Renew al máximo (R11.4): every recall, list and status sealed and fsynced a full snapshot just to persist the
        // newest observed time.
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        MutableTimeProvider clock = new(Start);
        LocalMemoryStore store = EnabledStore(temporary.Path, protector, clock);
        _ = store.Save(Save("save", "color", "azul"));
        _ = store.Save(new MemorySaveRequest(
            "temporary",
            "reunion",
            "Reunión",
            "a las 11",
            Retention: MemoryRetention.Temporary,
            ExpiresAtUtc: Start.AddMinutes(90)));
        int sealsAfterSave = protector.SealCount;

        clock.UtcNow = Start.AddMinutes(1);
        _ = store.Recall(new("color"));
        clock.UtcNow = Start.AddMinutes(2);
        _ = store.Recall(new("color"));
        _ = store.List(new());
        _ = store.Status(new());
        int sealsAfterReads = protector.SealCount;

        clock.UtcNow = Start.AddMinutes(91);
        bool expired = store.Recall(new("reunion")).Records.Count == 0;
        int sealsAfterExpiry = protector.SealCount;
        clock.UtcNow = Start.AddMinutes(91 + 61);
        _ = store.Recall(new("color"));
        int sealsAfterAnHour = protector.SealCount;
        clock.UtcNow = Start.AddMinutes(1);
        LocalMemoryStore restarted = CreateStore(temporary.Path, protector, clock);

        Assert.Multiple(() =>
        {
            Assert.That(sealsAfterReads, Is.EqualTo(sealsAfterSave));
            Assert.That(expired, Is.True);
            Assert.That(sealsAfterExpiry, Is.GreaterThan(sealsAfterReads));
            Assert.That(sealsAfterAnHour, Is.GreaterThan(sealsAfterExpiry));
            Assert.That(restarted.Recall(new("reunion")).Records, Is.Empty);
            Assert.That(restarted.Recall(new("color")).Records.Single().Value, Is.EqualTo("azul"));
        });
    }

    [Test]
    public void SensitiveAndSecretValuesAreAlwaysRedactedFromRecallAndList()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        _ = store.Save(new MemorySaveRequest(
            "secret",
            "api key",
            "API key",
            "sk-secret-canary",
            Sensitivity: MemorySensitivity.Secret));
        _ = store.Save(new MemorySaveRequest(
            "sensitive",
            "health detail",
            "Health detail",
            "sensitive-canary",
            Sensitivity: MemorySensitivity.Sensitive));

        Assert.Multiple(() =>
        {
            Assert.That(store.Recall(new("api key")).Records.Single().Value,
                Is.EqualTo(LocalMemoryStore.RedactedSecretValue));
            Assert.That(store.Recall(new("health detail")).Records.Single().Value,
                Is.EqualTo(LocalMemoryStore.RedactedSecretValue));
            Assert.That(
                store.List(new()).Records.Select(record => record.Value),
                Is.All.EqualTo(LocalMemoryStore.RedactedSecretValue));
            Assert.That(GetManagedBytes(temporary.Path), Has.None.Contains("sk-secret-canary"));
            Assert.That(GetManagedBytes(temporary.Path), Has.None.Contains("sensitive-canary"));
        });
    }

    [Test]
    public void RecordCapacityFailsBeforeAnyEffectAndAFullReceiptLedgerRollsOver()
    {
        using TemporaryDirectory recordDirectory = new();
        TestProtectedPayload recordProtector = new();
        LocalMemoryStore recordStore = new(
            recordDirectory.Path,
            recordProtector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 1,
            maximumReceipts: 10);
        _ = recordStore.Configure(new("configure", true));
        _ = recordStore.Save(Save("save-1", "uno", "1"));

        Assert.That(
            () => recordStore.Save(Save("save-2", "dos", "2")),
            Throws.TypeOf<MemoryCapacityException>());
        Assert.That(recordStore.List(new()).Records.Select(record => record.Selector),
            Is.EqualTo(new[] { "UNO" }));

        using TemporaryDirectory receiptDirectory = new();
        TestProtectedPayload receiptProtector = new();
        LocalMemoryStore receiptStore = new(
            receiptDirectory.Path,
            receiptProtector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 10,
            maximumReceipts: 2);
        _ = receiptStore.Configure(new("configure", true));
        _ = receiptStore.Save(Save("save-1", "uno", "1"));

        // Renew al máximo (B-SYS-3): a full ledger drops its oldest receipt instead of refusing the save; the recent
        // invocations still replay and the dropped one runs again with no change.
        MemorySaveResult second = receiptStore.Save(Save("save-2", "dos", "2"));
        MemorySaveResult firstReplay = receiptStore.Save(Save("save-1", "uno", "1"));
        MemoryConfigurationResult configureAgain = receiptStore.Configure(new("configure", true));
        Assert.Multiple(() =>
        {
            Assert.That(second.Replayed, Is.False);
            Assert.That(firstReplay.Replayed, Is.True);
            Assert.That(configureAgain, Is.EqualTo(new MemoryConfigurationResult(true, false, Changed: false)));
            Assert.That(receiptStore.List(new()).Records, Has.Count.EqualTo(2));
        });
    }

    [Test]
    public void FullReceiptLedgerCannotBlockForgetDisableOrALaterEnable()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 10,
            maximumReceipts: 2);
        _ = store.Configure(new("configure-on", true));
        _ = store.Save(Save("save", "selector", "private"));

        MemoryForgetRequest forgetRequest = new(
            "forget",
            MemoryForgetScope.Exact,
            Selector: "selector");
        MemoryForgetResult forgotten = store.Forget(forgetRequest);
        MemoryForgetResult replay = store.Forget(forgetRequest);
        MemoryRecord[] visibleAfterForget = store.List(new()).Records.ToArray();
        MemoryConfigurationResult disabled = store.Configure(new("configure-off", false));
        MemoryConfigurationResult disabledReplay = store.Configure(new("configure-off", false));
        MemoryForgetResult recentReplay = store.Forget(forgetRequest);
        LocalMemoryStore restarted = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 10,
            maximumReceipts: 2);
        bool disabledAfterRestart = !restarted.Status(new()).Enabled;
        TestDelegate saveWhileDisabled = () => restarted.Save(Save("save-disabled", "selector", "resurrected"));

        // Renew al máximo (B-SYS-3): this test used to assert that enabling again failed with memory_capacity_reached
        // once two receipts existed; that defended the lifetime cap itself (a «full» memory with zero records), not a
        // privacy property. What it guards now: the disable survives a restart, a new enable works, and the forgotten
        // value never comes back.
        Assert.Multiple(() =>
        {
            Assert.That(forgotten, Is.EqualTo(new MemoryForgetResult(1, false)));
            Assert.That(replay, Is.EqualTo(new MemoryForgetResult(1, true)));
            Assert.That(visibleAfterForget, Is.Empty);
            Assert.That(disabled, Is.EqualTo(new MemoryConfigurationResult(false, false)));
            Assert.That(disabledReplay, Is.EqualTo(new MemoryConfigurationResult(false, true)));
            Assert.That(recentReplay, Is.EqualTo(new MemoryForgetResult(1, true)));
            Assert.That(disabledAfterRestart, Is.True);
            Assert.That(saveWhileDisabled, Throws.TypeOf<MemoryDisabledException>());
        });

        MemoryConfigurationResult enabledAgain = restarted.Configure(new("configure-new", true));
        MemorySaveResult saved = restarted.Save(Save("save-new", "otro", "nuevo"));
        Assert.Multiple(() =>
        {
            Assert.That(enabledAgain, Is.EqualTo(new MemoryConfigurationResult(true, false)));
            Assert.That(saved.Replayed, Is.False);
            Assert.That(
                restarted.List(new()).Records.Select(record => record.Value),
                Is.EqualTo(new[] { "nuevo" }));
        });
    }

    [Test]
    public void ForgetAllFreesTheReceiptLedgerAndOldReceiptsRollOff()
    {
        // Renew al máximo (B-SYS-3): a lifetime receipt cap left the memory «full» with zero records.
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 10,
            maximumReceipts: 2);
        _ = store.Configure(new("configure-on", true));
        _ = store.Save(Save("save-1", "uno", "1"));
        MemoryForgetResult forgotten = store.Forget(new("forget-all", MemoryForgetScope.All));

        MemorySaveResult afterForget = store.Save(Save("save-2", "dos", "2"));
        MemorySaveResult third = store.Save(Save("save-3", "tres", "3"));
        MemorySaveResult fourth = store.Save(Save("save-4", "cuatro", "4"));
        MemorySaveResult fourthReplay = store.Save(Save("save-4", "cuatro", "4"));
        LocalMemoryStore restarted = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 10,
            maximumReceipts: 2);

        Assert.Multiple(() =>
        {
            Assert.That(forgotten, Is.EqualTo(new MemoryForgetResult(1, false)));
            Assert.That(afterForget.Replayed, Is.False);
            Assert.That(third.Replayed, Is.False);
            Assert.That(fourth.Replayed, Is.False);
            Assert.That(fourthReplay, Is.EqualTo(fourth with { Replayed = true, Changed = true }));
            Assert.That(restarted.Status(new()).TotalRecords, Is.EqualTo(3));
            Assert.That(
                () => restarted.Configure(new("configure-again", true)),
                Throws.Nothing);
        });
    }

    [Test]
    public void ForgottenAndExpiredMemoriesLeaveNoReceiptNamingThemAtRest()
    {
        // Renew al máximo (R11.3): save and correct receipts carried the selector of a memory already forgotten.
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        MutableTimeProvider clock = new(Start);
        LocalMemoryStore store = EnabledStore(temporary.Path, protector, clock);
        MemorySaveResult diagnosis = store.Save(Save("save-diag", "diagnostico privado", "reservado"));
        _ = store.Correct(new MemoryCorrectRequest(
            "correct-diag",
            "diagnostico privado",
            "corregido",
            ExpectedRevision: diagnosis.Revision));
        _ = store.Save(new MemorySaveRequest(
            "save-cita",
            "cita pasajera",
            "Cita pasajera",
            "a las 11",
            Retention: MemoryRetention.Temporary,
            ExpiresAtUtc: Start.AddMinutes(10)));
        _ = store.Save(Save("save-kept", "color", "azul"));

        MemoryForgetResult forgotten = store.Forget(new(
            "forget-diag",
            MemoryForgetScope.Exact,
            Selector: "diagnostico privado"));
        clock.UtcNow = Start.AddMinutes(11);
        Assert.That(store.Recall(new("cita pasajera")).Records, Is.Empty);
        MemorySaveResult keptReplay = store.Save(Save("save-kept", "color", "azul"));

        string[] atRest = new[] { "current.bin", "recovery.bin" }
            .Select(name => Encoding.UTF8.GetString(protector.Open(
                File.ReadAllBytes(Path.Combine(temporary.Path, name)),
                "memory.store.v1")))
            .ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(forgotten, Is.EqualTo(new MemoryForgetResult(1, false)));
            Assert.That(keptReplay.Replayed, Is.True);
            Assert.That(atRest, Has.All.Not.Contains("DIAGNOSTICO").IgnoreCase);
            Assert.That(atRest, Has.All.Not.Contains("save-diag"));
            Assert.That(atRest, Has.All.Not.Contains("correct-diag"));
            Assert.That(atRest, Has.All.Not.Contains("CITA PASAJERA").IgnoreCase);
            Assert.That(atRest, Has.All.Not.Contains("save-cita"));
            Assert.That(atRest, Has.All.Contains("save-kept"));
        });
    }

    [Test]
    public void AStoreWithTheOldEmergencyPrivacyReceiptStillLoadsAndFoldsItIntoTheRing()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 10,
            maximumReceipts: 2);
        _ = store.Configure(new("configure-on", true));
        _ = store.Save(Save("save-1", "uno", "1"));
        RewriteSnapshotWithMatchingWatermark(temporary.Path, protector, state => state.EmergencyPrivacyReceipt =
            new MemoryReceiptDocument
            {
                InvocationId = "legacy-forget",
                RequestDigest = new string('a', 64),
                Operation = "forget",
                DeletedCount = 0,
            });

        LocalMemoryStore restarted = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: null,
            maximumRecords: 10,
            maximumReceipts: 2);
        MemorySaveResult saved = restarted.Save(Save("save-2", "dos", "2"));
        MemoryStateDocument after = ReadState(temporary.Path, protector);

        Assert.Multiple(() =>
        {
            Assert.That(saved.Replayed, Is.False);
            Assert.That(after.EmergencyPrivacyReceipt, Is.Null);
            Assert.That(
                after.Receipts.Select(receipt => receipt.InvocationId),
                Is.EqualTo(new[] { "legacy-forget", "save-2" }));
            Assert.That(restarted.Status(new()).TotalRecords, Is.EqualTo(2));
        });
    }

    [Test]
    public void EveryCommitCrashStageRollsForwardAndReplaysTheReceipt()
    {
        foreach (MemoryCommitStage stage in Enum.GetValues<MemoryCommitStage>())
        {
            using TemporaryDirectory temporary = new();
            TestProtectedPayload protector = new();
            _ = EnabledStore(temporary.Path, protector);
            MemorySaveRequest request = Save("crash-save", "etapa", stage.ToString());
            var simulated = new SimulatedCrashException();
            LocalMemoryStore crashing = new(
                temporary.Path,
                protector,
                timeProvider: null,
                crashHook: current =>
                {
                    if (current == stage)
                    {
                        throw simulated;
                    }
                });

            Assert.That(
                () => crashing.Save(request),
                Throws.TypeOf<SimulatedCrashException>(),
                stage.ToString());

            LocalMemoryStore recovered = CreateStore(temporary.Path, protector);
            MemoryRecord record = recovered.Recall(new("etapa")).Records.Single();
            MemorySaveResult replay = recovered.Save(request);
            Assert.Multiple(() =>
            {
                Assert.That(record.Value, Is.EqualTo(stage.ToString()), stage.ToString());
                Assert.That(replay.Replayed, Is.True, stage.ToString());
                Assert.That(File.Exists(Path.Combine(temporary.Path, "mutation.intent")), Is.False,
                    stage.ToString());
            });
        }
    }

    [Test]
    public void ARollForwardThatFailsAfterTheDurableIntentIsAChangeThatMayStand()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        _ = EnabledStore(temporary.Path, protector);
        LocalMemoryStore failing = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: stage =>
            {
                if (stage == MemoryCommitStage.CurrentDurable)
                {
                    throw new IOException("disk");
                }
            });

        Assert.That(
            () => failing.Save(Save("save-io", "disco", "durable")),
            Throws.TypeOf<MemoryCommitUnconfirmedException>());
        LocalMemoryStore recovered = CreateStore(temporary.Path, protector);
        Assert.That(recovered.Recall(new("disco")).Records.Single().Value, Is.EqualTo("durable"));
    }

    [Test]
    public void CorruptCurrentRepairsFromExactRecoveryButHigherGenerationNeverRollsBack()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, protector);
        _ = store.Save(Save("save-old", "uno", "old"));
        byte[] oldWatermark = File.ReadAllBytes(Path.Combine(temporary.Path, "watermark.bin"));
        byte[] oldRecovery = File.ReadAllBytes(Path.Combine(temporary.Path, "recovery.bin"));

        string currentPath = Path.Combine(temporary.Path, "current.bin");
        byte[] corrupted = File.ReadAllBytes(currentPath);
        corrupted[^1] ^= 0x5A;
        File.WriteAllBytes(currentPath, corrupted);
        LocalMemoryStore repaired = CreateStore(temporary.Path, protector);
        Assert.That(repaired.Recall(new("uno")).Records.Single().Value, Is.EqualTo("old"));

        _ = repaired.Save(Save("save-new", "dos", "new"));
        byte[] higherCurrent = File.ReadAllBytes(currentPath);
        File.WriteAllBytes(Path.Combine(temporary.Path, "watermark.bin"), oldWatermark);
        File.WriteAllBytes(Path.Combine(temporary.Path, "recovery.bin"), oldRecovery);
        File.WriteAllBytes(currentPath, higherCurrent);

        Assert.That(
            () => CreateStore(temporary.Path, protector),
            Throws.TypeOf<MemoryStoreCorruptException>());
    }

    [Test]
    public void OldAuthenticatedIntentCannotReplaceNewerSnapshotsWithoutAWatermark()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        _ = EnabledStore(temporary.Path, protector);
        var simulated = new SimulatedCrashException();
        LocalMemoryStore crashing = new(
            temporary.Path,
            protector,
            timeProvider: null,
            crashHook: stage =>
            {
                if (stage == MemoryCommitStage.IntentDurable)
                {
                    throw simulated;
                }
            });

        Assert.That(
            () => crashing.Save(Save("save-old", "old", "old")),
            Throws.TypeOf<SimulatedCrashException>());
        string intentPath = Path.Combine(temporary.Path, "mutation.intent");
        byte[] oldIntent = File.ReadAllBytes(intentPath);

        LocalMemoryStore recovered = CreateStore(temporary.Path, protector);
        _ = recovered.Save(Save("save-new", "new", "new"));
        File.WriteAllBytes(intentPath, oldIntent);
        File.Delete(Path.Combine(temporary.Path, "watermark.bin"));

        Assert.That(
            () => CreateStore(temporary.Path, protector),
            Throws.TypeOf<MemoryStoreCorruptException>());
    }

    [Test]
    public void WrongKeyTamperingAndOversizedManagedFilesFailClosed()
    {
        using TemporaryDirectory wrongKeyDirectory = new();
        TestProtectedPayload original = new();
        _ = EnabledStore(wrongKeyDirectory.Path, original);
        Assert.That(
            () => CreateStore(wrongKeyDirectory.Path, new TestProtectedPayload()),
            Throws.TypeOf<MemoryStoreCorruptException>());

        using TemporaryDirectory tamperDirectory = new();
        TestProtectedPayload protector = new();
        _ = EnabledStore(tamperDirectory.Path, protector);
        foreach (string fileName in new[] { "current.bin", "recovery.bin" })
        {
            string path = Path.Combine(tamperDirectory.Path, fileName);
            byte[] bytes = File.ReadAllBytes(path);
            bytes[bytes.Length / 2] ^= 0x3C;
            File.WriteAllBytes(path, bytes);
        }

        Assert.That(
            () => CreateStore(tamperDirectory.Path, protector),
            Throws.TypeOf<MemoryStoreCorruptException>());

        using TemporaryDirectory oversizedDirectory = new();
        TestProtectedPayload oversizedProtector = new();
        _ = EnabledStore(oversizedDirectory.Path, oversizedProtector);
        foreach (string fileName in new[] { "current.bin", "recovery.bin" })
        {
            using FileStream stream = new(
                Path.Combine(oversizedDirectory.Path, fileName),
                FileMode.Create,
                FileAccess.Write,
                FileShare.None);
            stream.SetLength(LocalMemoryStore.MaximumClearSnapshotBytes + 8192L);
        }

        Assert.That(
            () => CreateStore(oversizedDirectory.Path, oversizedProtector),
            Throws.TypeOf<MemoryStoreCorruptException>());
    }

    [Test]
    public void AuthenticatedButNoncanonicalDocumentsFailClosed()
    {
        using (TemporaryDirectory snapshotDirectory = new())
        {
            TestProtectedPayload protector = new();
            _ = EnabledStore(snapshotDirectory.Path, protector);
            RewriteSnapshotWithLeadingWhitespaceAndMatchingWatermark(
                snapshotDirectory.Path,
                protector);

            Assert.That(
                () => CreateStore(snapshotDirectory.Path, protector),
                Throws.TypeOf<MemoryStoreCorruptException>());
        }

        using (TemporaryDirectory intentDirectory = new())
        {
            TestProtectedPayload protector = new();
            _ = EnabledStore(intentDirectory.Path, protector);
            LocalMemoryStore crashing = new(
                intentDirectory.Path,
                protector,
                timeProvider: null,
                crashHook: stage =>
                {
                    if (stage == MemoryCommitStage.IntentDurable)
                    {
                        throw new SimulatedCrashException();
                    }
                });
            Assert.That(
                () => crashing.Save(Save("noncanonical-intent", "intent", "value")),
                Throws.TypeOf<SimulatedCrashException>());
            ResealWithLeadingWhitespace(
                Path.Combine(intentDirectory.Path, "mutation.intent"),
                protector,
                "memory.intent.v1");

            Assert.That(
                () => CreateStore(intentDirectory.Path, protector),
                Throws.TypeOf<MemoryStoreCorruptException>());
        }

        using (TemporaryDirectory watermarkDirectory = new())
        {
            TestProtectedPayload protector = new();
            _ = EnabledStore(watermarkDirectory.Path, protector);
            ResealWithLeadingWhitespace(
                Path.Combine(watermarkDirectory.Path, "watermark.bin"),
                protector,
                "memory.watermark.v1");

            Assert.That(
                () => CreateStore(watermarkDirectory.Path, protector),
                Throws.TypeOf<MemoryStoreCorruptException>());
        }
    }

    [Test]
    public void ConcurrentInstancesSerializeMutationsUnderTheStaticRootLock()
    {
        using TemporaryDirectory temporary = new();
        TestProtectedPayload protector = new();
        LocalMemoryStore first = EnabledStore(temporary.Path, protector);
        LocalMemoryStore second = CreateStore(temporary.Path, protector);

        Parallel.For(0, 24, index =>
        {
            LocalMemoryStore selected = index % 2 == 0 ? first : second;
            _ = selected.Save(Save($"save-{index}", $"key-{index}", $"value-{index}"));
        });

        Assert.That(first.List(new(MaximumResults: 100)).Records, Has.Count.EqualTo(24));
    }

    [Test]
    public void RelativeAndReparseRootsAreRejected()
    {
        Assert.That(
            () => new LocalMemoryStore("relative-memory", new TestProtectedPayload()),
            Throws.TypeOf<UnsafeMemoryStorePathException>());

        using TemporaryDirectory temporary = new();
        string target = Path.Combine(temporary.Path, "target");
        string link = Path.Combine(temporary.Path, "link");
        Directory.CreateDirectory(target);
        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            Assert.That(
                () => new LocalMemoryStore(link, new TestProtectedPayload()),
                Throws.TypeOf<UnsafeMemoryStorePathException>());
        }
        finally
        {
            if (Path.Exists(link))
            {
                Directory.Delete(link);
            }
        }
    }

    [Test]
    public void HardLinkedManagedSnapshotIsRejectedBeforeItIsRead()
    {
        using TemporaryDirectory temporary = new();
        LocalMemoryStore store = EnabledStore(temporary.Path, new TestProtectedPayload());
        _ = store.Save(Save("save-hardlink", "tema", "valor"));
        string current = Path.Combine(temporary.Path, "current.bin");
        string hardLink = Path.Combine(temporary.Path, "current-copy.bin");
        if (!WindowsPathAttackTestSupport.TryCreateHardLink(hardLink, current))
        {
            Assert.Ignore("This volume does not permit creating a hard link for the test.");
            return;
        }

        Assert.That(
            () => CreateStore(temporary.Path, new TestProtectedPayload()),
            Throws.TypeOf<UnsafeMemoryStorePathException>());
    }

    [Test]
    public void RealDpapiProtectedStoreRoundTripsAndMissingKeyFailsClosed()
    {
        if (!OperatingSystem.IsWindows())
        {
            Assert.Ignore("DPAPI CurrentUser is a Windows-only boundary.");
        }

        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "key.bin");
        string storePath = Path.Combine(temporary.Path, "memory");
        var protector = new WindowsProtectedPayload(keyPath);
        LocalMemoryStore store = EnabledStore(storePath, protector);
        _ = store.Save(Save("save", "sistema", "Windows"));

        var restartedProtector = new WindowsProtectedPayload(keyPath);
        LocalMemoryStore restarted = CreateStore(storePath, restartedProtector);
        Assert.That(restarted.Recall(new("sistema")).Records.Single().Value, Is.EqualTo("Windows"));

        File.Delete(keyPath);
        Assert.That(
            () => CreateStore(storePath, new WindowsProtectedPayload(keyPath)),
            Throws.TypeOf<MemoryStoreCorruptException>());
        Assert.That(File.Exists(keyPath), Is.False);
    }

    private static LocalMemoryStore EnabledStore(
        string path,
        IProtectedPayload protector,
        TimeProvider? clock = null)
    {
        LocalMemoryStore store = CreateStore(path, protector, clock);
        _ = store.Configure(new("configure", Enabled: true));
        return store;
    }

    private static LocalMemoryStore CreateStore(
        string path,
        IProtectedPayload protector,
        TimeProvider? clock = null) => new(path, protector, clock);

    private static MemorySaveRequest Save(
        string invocationId,
        string selector,
        string value) => new(invocationId, selector, selector, value);

    private static IEnumerable<string> GetManagedBytes(string rootDirectory) =>
        Directory.EnumerateFiles(rootDirectory)
            .Select(path => Encoding.UTF8.GetString(File.ReadAllBytes(path)));

    private static void ResealWithLeadingWhitespace(
        string path,
        TestProtectedPayload protector,
        string purpose)
    {
        byte[] envelope = File.ReadAllBytes(path);
        byte[] clear = protector.Open(envelope, purpose);
        byte[] noncanonical = new byte[clear.Length + 1];
        noncanonical[0] = (byte)' ';
        clear.CopyTo(noncanonical, 1);
        File.WriteAllBytes(path, protector.Seal(noncanonical, purpose));
    }

    private static MemoryStateDocument ReadState(string root, TestProtectedPayload protector) =>
        JsonSerializer.Deserialize(
            protector.Open(File.ReadAllBytes(Path.Combine(root, "current.bin")), "memory.store.v1"),
            MemoryJsonContext.Default.MemoryStateDocument)!;

    private static void RewriteSnapshotWithMatchingWatermark(
        string root,
        TestProtectedPayload protector,
        Action<MemoryStateDocument> change)
    {
        string currentPath = Path.Combine(root, "current.bin");
        byte[] clear = protector.Open(File.ReadAllBytes(currentPath), "memory.store.v1");
        MemoryStateDocument state = JsonSerializer.Deserialize(
            clear,
            MemoryJsonContext.Default.MemoryStateDocument)!;
        change(state);
        byte[] changed = JsonSerializer.SerializeToUtf8Bytes(state, MemoryJsonContext.Default.MemoryStateDocument);
        byte[] snapshotEnvelope = protector.Seal(changed, "memory.store.v1");
        File.WriteAllBytes(currentPath, snapshotEnvelope);
        File.WriteAllBytes(Path.Combine(root, "recovery.bin"), snapshotEnvelope);

        string watermarkPath = Path.Combine(root, "watermark.bin");
        byte[] watermarkClear = protector.Open(File.ReadAllBytes(watermarkPath), "memory.watermark.v1");
        string updatedWatermark = Encoding.UTF8
            .GetString(watermarkClear)
            .Replace(
                Convert.ToHexStringLower(SHA256.HashData(clear)),
                Convert.ToHexStringLower(SHA256.HashData(changed)),
                StringComparison.Ordinal);
        File.WriteAllBytes(
            watermarkPath,
            protector.Seal(Encoding.UTF8.GetBytes(updatedWatermark), "memory.watermark.v1"));
    }

    private static void RewriteSnapshotWithLeadingWhitespaceAndMatchingWatermark(
        string root,
        TestProtectedPayload protector)
    {
        string currentPath = Path.Combine(root, "current.bin");
        byte[] clear = protector.Open(File.ReadAllBytes(currentPath), "memory.store.v1");
        byte[] noncanonical = new byte[clear.Length + 1];
        noncanonical[0] = (byte)' ';
        clear.CopyTo(noncanonical, 1);
        byte[] snapshotEnvelope = protector.Seal(noncanonical, "memory.store.v1");
        File.WriteAllBytes(currentPath, snapshotEnvelope);
        File.WriteAllBytes(Path.Combine(root, "recovery.bin"), snapshotEnvelope);

        string watermarkPath = Path.Combine(root, "watermark.bin");
        byte[] watermarkClear = protector.Open(
            File.ReadAllBytes(watermarkPath),
            "memory.watermark.v1");
        string oldDigest = Convert.ToHexStringLower(SHA256.HashData(clear));
        string newDigest = Convert.ToHexStringLower(SHA256.HashData(noncanonical));
        string updatedWatermark = Encoding.UTF8
            .GetString(watermarkClear)
            .Replace(oldDigest, newDigest, StringComparison.Ordinal);
        File.WriteAllBytes(
            watermarkPath,
            protector.Seal(
                Encoding.UTF8.GetBytes(updatedWatermark),
                "memory.watermark.v1"));
    }

    private sealed class TestProtectedPayload : IProtectedPayload
    {
        private const int NonceLength = 12;
        private const int TagLength = 16;
        private static readonly byte[] Magic = "TST1"u8.ToArray();
        private readonly byte[] _key;

        public TestProtectedPayload()
            : this(RandomNumberGenerator.GetBytes(32))
        {
        }

        private TestProtectedPayload(byte[] key)
        {
            _key = key;
        }

        public string ProtectionMode => "test-aes-gcm";

        public int SealCount { get; private set; }

        public byte[] Seal(ReadOnlySpan<byte> plaintext, string purpose)
        {
            SealCount++;
            byte[] nonce = RandomNumberGenerator.GetBytes(NonceLength);
            byte[] ciphertext = new byte[plaintext.Length];
            byte[] tag = new byte[TagLength];
            using var aes = new AesGcm(_key, TagLength);
            aes.Encrypt(nonce, plaintext, ciphertext, tag, Encoding.UTF8.GetBytes(purpose));
            byte[] envelope = new byte[Magic.Length + nonce.Length + tag.Length + ciphertext.Length];
            Magic.CopyTo(envelope, 0);
            nonce.CopyTo(envelope, Magic.Length);
            tag.CopyTo(envelope, Magic.Length + nonce.Length);
            ciphertext.CopyTo(envelope, Magic.Length + nonce.Length + tag.Length);
            return envelope;
        }

        public byte[] Open(ReadOnlySpan<byte> envelope, string purpose)
        {
            if (envelope.Length < Magic.Length + NonceLength + TagLength
                || !envelope[..Magic.Length].SequenceEqual(Magic))
            {
                throw new CryptographicException();
            }

            ReadOnlySpan<byte> nonce = envelope.Slice(Magic.Length, NonceLength);
            ReadOnlySpan<byte> tag = envelope.Slice(Magic.Length + NonceLength, TagLength);
            ReadOnlySpan<byte> ciphertext = envelope[(Magic.Length + NonceLength + TagLength)..];
            byte[] plaintext = new byte[ciphertext.Length];
            using var aes = new AesGcm(_key, TagLength);
            aes.Decrypt(nonce, ciphertext, tag, plaintext, Encoding.UTF8.GetBytes(purpose));
            return plaintext;
        }
    }

    private sealed class MutableTimeProvider : TimeProvider
    {
        public MutableTimeProvider(DateTimeOffset utcNow)
        {
            UtcNow = utcNow;
        }

        public DateTimeOffset UtcNow { get; set; }

        public override DateTimeOffset GetUtcNow() => UtcNow;
    }

    private sealed class SimulatedCrashException : Exception;

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                $"baxy-memory-tests-{Guid.NewGuid():N}");
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
