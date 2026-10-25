using System.Collections;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión nb-q-apps2: an application handed a file by its own executable starts as InvokerLaunch starts the person's
/// programs, inheriting none of the core's handles (its stdio pipes among them) and out of its job. Only the plan and
/// the request are built here; nothing is started.
/// </summary>
[TestFixture]
public sealed class FileActivationLaunchTests
{
    [Test]
    public void TheFileGoesQuotedToItsApplicationThatInheritsNothing()
    {
        const string executable = @"C:\Program Files\Editor\editor.exe";
        const string file = @"C:\Users\persona\Documents\notas de clase.txt";

        InvokerLaunch.LaunchPlan plan = WindowsInstalledApplicationPlatform.FileLaunchPlan(executable, file);
        InvokerLaunch.StartRequest request = InvokerLaunch.PrepareOutsideBaxy(plan, new Hashtable { ["PATH"] = @"C:\Windows" });

        Assert.Multiple(() =>
        {
            Assert.That(plan.Executable, Is.EqualTo(executable));
            Assert.That(plan.Arguments, Is.EqualTo("\"" + file + "\""));
            Assert.That(plan.WorkingDirectory, Is.EqualTo(@"C:\Program Files\Editor"));
            Assert.That(request.InheritHandles, Is.False);
            Assert.That(request.CreationFlags & InvokerLaunch.CreateBreakawayFromJob, Is.Not.Zero);
            Assert.That(request.CommandLine, Is.EqualTo("\"" + executable + "\" \"" + file + "\""));
        });
    }
}
