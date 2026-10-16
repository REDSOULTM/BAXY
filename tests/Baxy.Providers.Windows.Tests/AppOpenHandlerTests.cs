using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew (notebook): what app.open says back. A place its application does not have is refused with what was
/// asked; a verified opening names the program whose window it verified.
/// </summary>
[TestFixture]
public sealed class AppOpenHandlerTests
{
    [Test]
    public async Task APlaceOfAnotherApplicationIsRefusedWithWhatWasAsked()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\mspaint.exe");

        OperationOutcome outcome = await Handler(provider).ExecuteAsync(
            Invocation("""{"appId":"Paint","place":"library"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("place_not_of_application"));
            Assert.That(outcome.Result!.Value.GetProperty("appId").GetString(), Is.EqualTo("Paint"));
            Assert.That(outcome.Result!.Value.GetProperty("place").GetString(), Is.EqualTo("library"));
            Assert.That(outcome.Result!.Value.GetProperty("placeIn").EnumerateArray().Select(name => name.GetString()),
                Does.Contain("Steam"));
            Assert.That(provider.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task AVerifiedOpeningNamesTheProgramOfTheWindowItVerified()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\notepad.exe");

        OperationOutcome outcome = await Handler(provider).ExecuteAsync(
            Invocation("""{"appId":"Bloc de notas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("displayName").GetString(), Is.EqualTo("Bloc de notas"));
            Assert.That(outcome.Result!.Value.GetProperty("processName").GetString(), Is.EqualTo("notepad"));
        });
    }

    private static AppOpenHandler Handler(IApplicationOpenProvider provider) => new(
        provider,
        new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)));

    private static OperationInvocation Invocation(string arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments);
        return new OperationInvocation("request", "mission", "invocation", document.RootElement.Clone());
    }

    /// <summary>A window of a program already running, verified for the opening asked.</summary>
    private sealed class VerifiedOpening(string executablePath) : IApplicationOpenProvider
    {
        internal int Calls { get; private set; }

        public ValueTask<ApplicationOpenResult> OpenAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            Calls++;
            var receipt = new ApplicationLaunchReceipt(
                request.InvocationId, request.ApplicationId, LaunchIssued: false, ReusedExisting: true,
                ProcessId: 4242, ProcessCreationTimeUtcTicks: 638900000000000000, executablePath,
                PackageFamilyName: null, PackageFullName: null, WindowHandle: 777, ErrorCode: null);
            return ValueTask.FromResult(new ApplicationOpenResult(
                Succeeded: true, Verified: true, request.ApplicationId, AlreadyRunning: true,
                ProcessId: 4242, WindowHandle: 777, ErrorCode: null, receipt));
        }
    }
}
