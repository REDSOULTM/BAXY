using System.Diagnostics;
using NUnit.Framework;
using NUnit.Framework.Internal;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class ChildOutputTests
{
    private static Process Start(string script)
    {
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-Command", script })
            start.ArgumentList.Add(argument);
        return Process.Start(start)!;
    }

    private static string Failure(Action read)
    {
        // The assertion it raises is the outcome under test, not this test's own: it is read in a context of its own.
        using var isolated = new TestExecutionContext.IsolatedContext();
        AssertionException failure = Assert.Throws<AssertionException>(() => read())!;
        return failure.Message;
    }

    [Test]
    public void WhatAChildWroteComesBack()
    {
        using Process child = Start("Write-Output 'hola'");

        Assert.That(ChildOutput.Read(child).Trim(), Is.EqualTo("hola"));
    }

    [Test]
    public void AChildThatDoesNotEndFailsWithinTheLimitAndEnds()
    {
        using Process child = Start("Start-Sleep -Seconds 600");
        var clock = Stopwatch.StartNew();

        string failure = Failure(() => ChildOutput.Read(child, TimeSpan.FromSeconds(2)));

        Assert.Multiple(() =>
        {
            Assert.That(failure, Does.Contain("did not end"));
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(30)));
            Assert.That(child.WaitForExit(10_000), Is.True, "the child ended with the test");
        });
    }

    // The pipe is inherited: the child is gone, and a process it started keeps the read open. WaitForExit alone says it
    // exited; only the read hangs.
    [Test]
    public void AGrandchildHoldingTheOutputFailsWithinTheLimit()
    {
        using Process child = Start(
            "$s=New-Object System.Diagnostics.ProcessStartInfo 'powershell.exe','-NonInteractive -NoProfile -Command Start-Sleep -Seconds 15';"
            + "$s.UseShellExecute=$false;$s.CreateNoWindow=$true;[void][System.Diagnostics.Process]::Start($s)");
        var clock = Stopwatch.StartNew();

        string failure = Failure(() => ChildOutput.Read(child, TimeSpan.FromSeconds(6)));

        Assert.Multiple(() =>
        {
            Assert.That(failure, Does.Contain("still holds its output"));
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(14)));
        });
    }
}
