using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[SetUpFixture]
internal sealed class TestAssemblySetup
{
    [OneTimeSetUp]
    public void UseDeterministicMessageFixtures()
    {
        UserMessagePolicy.BypassLlmCompositionForTests = true;
    }

    [OneTimeTearDown]
    public void RestoreProductionMessageComposition()
    {
        UserMessagePolicy.BypassLlmCompositionForTests = false;
        FieldCompositionInjection.Reset();
        FieldPublicationInjection.Reset();
    }
}
