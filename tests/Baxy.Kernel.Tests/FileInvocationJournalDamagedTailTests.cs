using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// DIAX11 (vivo Radeon H-012): a line of «{{{» at the end of the journal stopped BAXY at every start («Tus datos
/// guardados no se pueden abrir»). Bytes after the end the authenticated anchor commits were never committed (a write a
/// power cut or a full disk cut short, or bytes that are not the journal's): they are set aside in a file of their own,
/// nothing deleted, and the journal opens with every committed record. Damage before that end still fails closed
/// (FileInvocationJournalTests: AuthenticatedAnchorRejects…, ReopenFailsClosedWhenCompleteRecordWasModified).
/// </summary>
[TestFixture]
public sealed class FileInvocationJournalDamagedTailTests
{
    private string _root = null!;
    private string _journalPath = null!;
    private byte[] _authenticationKey = null!;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-kernel-tests", Guid.NewGuid().ToString("N"));
        _journalPath = Path.Combine(_root, "journal", "missions.jsonl");
        _authenticationKey = RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength);
    }

    [TearDown]
    public void TearDown()
    {
        if (Directory.Exists(_root))
            Directory.Delete(_root, recursive: true);
        CryptographicOperations.ZeroMemory(_authenticationKey);
    }

    private static readonly byte[] Nuls = new byte[64];

    // Each damage a cut write or a full disk leaves at the end, and the CAMDY one («{{{» and a newline).
    private static IEnumerable<TestCaseData> Damages()
    {
        yield return new TestCaseData(Encoding.UTF8.GetBytes("{{{\n")).SetName("InvalidJsonLine");
        yield return new TestCaseData(Encoding.UTF8.GetBytes("{\"version\":2,\"authentication\":\"hmac-sha2")).SetName("TruncatedRecord");
        yield return new TestCaseData(Encoding.UTF8.GetBytes("{\"version\":2}\n")).SetName("ValidJsonThatIsNoRecord");
        yield return new TestCaseData(Encoding.UTF8.GetBytes("{\"version\":2}")).SetName("ValidJsonUnterminated");
        yield return new TestCaseData(Encoding.UTF8.GetBytes("\n")).SetName("EmptyLine");
        yield return new TestCaseData(Encoding.UTF8.GetBytes("\n\n{{{\n{}\n")).SetName("SeveralDamagedLines");
        yield return new TestCaseData(Nuls).SetName("NulBytes");
        yield return new TestCaseData(Nuls.Concat("\n"u8.ToArray()).ToArray()).SetName("NulBytesAndNewline");
    }

    [TestCaseSource(nameof(Damages))]
    public async Task ADamagedTailAfterTheCommittedEndIsSetAsideAndTheJournalOpens(byte[] damage)
    {
        (OperationRequest request, string fingerprint) = await CompleteOneAsync();
        byte[] committed = await File.ReadAllBytesAsync(_journalPath);
        await using (FileStream file = new(_journalPath, FileMode.Append, FileAccess.Write))
            await file.WriteAsync(damage);
        var said = new List<string>();

        await using (FileInvocationJournal reopened = await FileInvocationJournal.OpenAsync(
            _journalPath, new JournalHmacAuthenticator(_authenticationKey), said.Add))
        {
            CompletedInvocation? completed = await reopened.FindCompletedAsync(request.InvocationId, CancellationToken.None);
            Assert.That(completed?.RequestFingerprint, Is.EqualTo(fingerprint), "every committed record is kept");
        }

        string[] setAside = Directory.GetFiles(Path.GetDirectoryName(_journalPath)!,
            "missions.jsonl.damaged-*");
        byte[] journalAfter = await File.ReadAllBytesAsync(_journalPath);
        Assert.Multiple(() =>
        {
            Assert.That(journalAfter, Is.EqualTo(committed));
            Assert.That(setAside, Has.Length.EqualTo(1));
            Assert.That(File.ReadAllBytes(setAside[0]), Is.EqualTo(damage), "nothing deleted: the bytes as they were");
            Assert.That(said, Has.Some.Contain("set aside").And.Some.Contain(Path.GetFileName(setAside[0])));
        });

        // It opens again and goes on recording.
        await using FileInvocationJournal again = await FileInvocationJournal.OpenAsync(
            _journalPath, new JournalHmacAuthenticator(_authenticationKey));
        OperationRequest next = Request();
        await again.RecordStartedAsync(next, RequestFingerprint.Compute(next), CancellationToken.None);
    }

    // A fresh journal (nothing committed yet) with damage only: the same.
    [Test]
    public async Task ADamagedTailOnAJournalWithNothingCommittedIsSetAsideToo()
    {
        await using (FileInvocationJournal journal = await OpenAsync())
        {
        }
        await File.AppendAllTextAsync(_journalPath, "{{{\n");

        await using FileInvocationJournal reopened = await OpenAsync();

        Assert.That(new FileInfo(_journalPath).Length, Is.Zero);
    }

    // REVX2 DX11-2: the copy cannot be written (a full disk, a folder without permission, an antivirus). The 1.5.5 cut
    // such a tail back and started; so does this, and says so truthfully, leaving no empty copy behind.
    [Test]
    public async Task ATailThatCannotBeCopiedIsCutBackAnywayAndSaidSo()
    {
        (OperationRequest request, string fingerprint) = await CompleteOneAsync();
        byte[] committed = await File.ReadAllBytesAsync(_journalPath);
        await File.AppendAllTextAsync(_journalPath, "{\"version\":2,\"authentication\":\"hmac-sha2");
        // Where the copy goes there is a folder: creating the copy is refused, as a full disk or a denied folder refuse it.
        string copy = _journalPath + FileInvocationJournal.DamagedTailMarker + "20261116090000000";
        Directory.CreateDirectory(copy);
        var said = new List<string>();

        await using (FileInvocationJournal reopened = await FileInvocationJournal.OpenWithRotationForTestingAsync(
            _journalPath, new JournalHmacAuthenticator(_authenticationKey), 64L * 1024 * 1024, 2 * 1024 * 1024,
            48L * 1024 * 1024, 2, diagnostics: said.Add,
            time: new FixedTime(new DateTimeOffset(2026, 11, 16, 9, 0, 0, TimeSpan.Zero))))
        {
            CompletedInvocation? completed = await reopened.FindCompletedAsync(request.InvocationId, CancellationToken.None);
            Assert.That(completed?.RequestFingerprint, Is.EqualTo(fingerprint), "every committed record is kept");
        }

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(_journalPath), Is.EqualTo(committed), "cut back to its committed end");
            Assert.That(Directory.GetFiles(Path.GetDirectoryName(_journalPath)!, "missions.jsonl.damaged-*"),
                Is.EqualTo(new[] { copy + FileInvocationJournal.NotKeptSuffix }), "no empty copy: only the mark to say it");
            Assert.That(Directory.GetFileSystemEntries(copy), Is.Empty, "what was there is not touched");
            Assert.That(said, Has.Some.Contain("could not keep a copy"));
        });
    }

    // Counter-cases: what was committed is still authenticated, so damage before the committed end fails closed.
    [Test]
    public async Task DamageBeforeTheCommittedEndStillFailsClosed()
    {
        await CompleteOneAsync();
        byte[] committed = await File.ReadAllBytesAsync(_journalPath);
        byte[] damaged = (byte[])committed.Clone();
        int middle = Array.IndexOf(damaged, (byte)'\n') / 2;
        damaged[middle] = (byte)'{';
        await File.WriteAllBytesAsync(_journalPath, damaged.Concat("{{{\n"u8.ToArray()).ToArray());

        Assert.That(async () => await OpenAsync(), Throws.InstanceOf<JournalIntegrityException>());
    }

    [Test]
    public async Task AJournalEmptiedAfterItsCommitsStillFailsClosed()
    {
        await CompleteOneAsync();
        await File.WriteAllBytesAsync(_journalPath, []);

        Assert.That(async () => await OpenAsync(), Throws.InstanceOf<JournalIntegrityException>());
    }

    private ValueTask<FileInvocationJournal> OpenAsync() =>
        FileInvocationJournal.OpenAsync(_journalPath, new JournalHmacAuthenticator(_authenticationKey));

    private async Task<(OperationRequest Request, string Fingerprint)> CompleteOneAsync()
    {
        OperationRequest request = Request();
        string fingerprint = RequestFingerprint.Compute(request);
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, request.RequestId, request.MissionId, request.InvocationId,
            OperationStatuses.Completed, "done", true, false,
            JsonDocument.Parse("{\"ok\":true}").RootElement.Clone(), null);
        await using FileInvocationJournal journal = await OpenAsync();
        await journal.RecordStartedAsync(request, fingerprint, CancellationToken.None);
        await journal.RecordCompletedAsync(request, fingerprint, response, CancellationToken.None);
        return (request, fingerprint);
    }

    private sealed class FixedTime(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now;
    }

    private static OperationRequest Request() => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "note.create",
        JsonDocument.Parse("{\"title\":\"Recados\",\"content\":\"leche\"}").RootElement.Clone());
}
