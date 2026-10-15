using System.Buffers.Binary;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsProcessorTopologyTests
{
    [Test]
    public void MixedSmtAndProcessorGroupsCountPhysicalRecords()
    {
        byte[] topology = [.. Core(0, 3), .. Core(0, 4), .. Core(1, 12)];

        Assert.That(WindowsSystemStatusProbe.CountPhysicalCores(topology), Is.EqualTo(3));
    }

    [TestCase("empty")]
    [TestCase("header")]
    [TestCase("trailing")]
    [TestCase("relationship")]
    [TestCase("zero_size")]
    [TestCase("oversized")]
    [TestCase("missing_group")]
    [TestCase("truncated_groups")]
    public void InvalidNativeTopologyNeverBecomesACoreCount(string defect)
    {
        byte[] topology = Core(0, 3);
        switch (defect)
        {
            case "empty": topology = []; break;
            case "header": topology = topology[..7]; break;
            case "trailing": topology = [.. topology, 0]; break;
            case "relationship": BinaryPrimitives.WriteUInt32LittleEndian(topology, 3); break;
            case "zero_size": BinaryPrimitives.WriteUInt32LittleEndian(topology.AsSpan(4), 0); break;
            case "oversized": BinaryPrimitives.WriteUInt32LittleEndian(topology.AsSpan(4), uint.MaxValue); break;
            case "missing_group": BinaryPrimitives.WriteUInt16LittleEndian(topology.AsSpan(30), 0); break;
            case "truncated_groups": BinaryPrimitives.WriteUInt16LittleEndian(topology.AsSpan(30), 2); break;
        }

        Assert.That(() => WindowsSystemStatusProbe.CountPhysicalCores(topology), Throws.TypeOf<IOException>());
    }

    [Test]
    public void WindowsReportsPhysicalCoresSeparatelyFromLogicalProcessors()
    {
        var probe = new WindowsSystemStatusProbe();
        int physical = probe.ReadPhysicalCoreCount();
        int logical = probe.ReadLogicalProcessorCount();

        Assert.That(physical, Is.InRange(1, logical));
        TestContext.Out.WriteLine($"Observed CPU topology: physical={physical}; logical={logical}");
    }

    private static byte[] Core(ushort group, uint mask)
    {
        var record = new byte[32 + IntPtr.Size + 8];
        BinaryPrimitives.WriteUInt32LittleEndian(record.AsSpan(4), (uint)record.Length);
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(30), 1);
        BinaryPrimitives.WriteUInt32LittleEndian(record.AsSpan(32), mask);
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(32 + IntPtr.Size), group);
        return record;
    }
}
