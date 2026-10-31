using System.Text;
using Baxy.Contracts;
using Baxy.Core;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ajuste c3 (humos del 31-10): the hello carried no installed application and the mind decided the whole session
/// without one. A start whose read is late carries the list the last verified read kept, and a read that ends after the
/// hello is sent to the App when it says other names, so the mind is never left without the list for the session.
/// </summary>
[TestFixture]
public sealed class HelloApplicationCatalogTests
{
    private static readonly InstalledApplicationCatalogSnapshot Read =
        new(true, true, ["Bloc de notas", "Configuración", "Paint"]);

    private string _folder = null!;

    [SetUp]
    public void SetUp()
    {
        _folder = Path.Combine(Path.GetTempPath(), "baxy-hello-catalog-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_folder);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_folder, recursive: true);

    private string KeptFile => Path.Combine(_folder, "application-catalog.v1.json");

    [Test]
    public async Task AStartWhoseReadIsLateCarriesTheListTheLastReadKept()
    {
        new KeptApplicationCatalog(KeptFile).Keep(Read);
        var neverEnds = new TaskCompletionSource<InstalledApplicationCatalogSnapshot>();

        InstalledApplicationCatalogSnapshot hello = await HelloCatalogWait.WithinAsync(
            neverEnds.Task, CoreStartupBudget.HelloCatalogWait, new KeptApplicationCatalog(KeptFile).Load,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(hello.Verified, Is.True);
            Assert.That(hello.Complete, Is.True);
            Assert.That(hello.Names, Is.EqualTo(Read.Names));
        });
    }

    [Test]
    public async Task AFirstStartWhoseReadIsLateCarriesNoList()
    {
        var neverEnds = new TaskCompletionSource<InstalledApplicationCatalogSnapshot>();

        InstalledApplicationCatalogSnapshot hello = await HelloCatalogWait.WithinAsync(
            neverEnds.Task, CoreStartupBudget.HelloCatalogWait, new KeptApplicationCatalog(KeptFile).Load,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(hello.Verified, Is.False);
            Assert.That(hello.Names, Is.Empty);
        });
    }

    [Test]
    public void OnlyAVerifiedReadIsKeptAndADamagedFileIsNoList()
    {
        var kept = new KeptApplicationCatalog(KeptFile);
        kept.Keep(new InstalledApplicationCatalogSnapshot(false, false, []));
        Assert.That(File.Exists(KeptFile), Is.False);

        kept.Keep(Read);
        Assert.That(kept.Load()?.Names, Is.EqualTo(Read.Names));

        File.WriteAllText(KeptFile, "{\"version\":1,\"verified\":true,\"complete\":true,\"names\":[\"A B\"]}", Encoding.UTF8);
        Assert.That(kept.Load(), Is.Null);
        File.WriteAllText(KeptFile, "not json", Encoding.UTF8);
        Assert.That(kept.Load(), Is.Null);
    }

    [Test]
    public void ALateReadIsSentOnlyWhenItIsVerifiedAndSaysOtherNames()
    {
        var none = new InstalledApplicationCatalogSnapshot(false, false, []);
        var unverified = new InstalledApplicationCatalogSnapshot(false, false, []);
        var other = new InstalledApplicationCatalogSnapshot(true, true, ["Bloc de notas", "Paint"]);

        Assert.Multiple(() =>
        {
            Assert.That(HelloCatalogWait.LateUpdate(none, Read)?.Names, Is.EqualTo(Read.Names));
            Assert.That(HelloCatalogWait.LateUpdate(other, Read)?.Names, Is.EqualTo(Read.Names));
            Assert.That(HelloCatalogWait.LateUpdate(Read, Read), Is.Null);
            Assert.That(HelloCatalogWait.LateUpdate(none, unverified), Is.Null);
        });
    }

    [Test]
    public void TheUpdateTravelsAsAVerifiedCatalogOnly()
    {
        var update = new ApplicationCatalogUpdate(
            ProtocolTypes.ApplicationCatalogUpdate,
            new ApplicationCatalogSnapshot(ApplicationCatalogContract.CurrentVersion, true, true, [.. Read.Names]));

        ApplicationCatalogUpdate back = ProtocolJson.DeserializeApplicationCatalogUpdate(ProtocolJson.SerializeToUtf8Bytes(update));

        Assert.Multiple(() =>
        {
            Assert.That(back.ApplicationCatalog.Names, Is.EqualTo(Read.Names));
            Assert.That(() => ProtocolJson.SerializeToUtf8Bytes(update with
            {
                ApplicationCatalog = new ApplicationCatalogSnapshot(ApplicationCatalogContract.CurrentVersion, false, false, []),
            }), Throws.InstanceOf<System.Text.Json.JsonException>());
        });
    }
}
