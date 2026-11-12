using System.Net;
using System.Net.Sockets;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// PRIV-05: the hidden page reader is a browser and connects by itself, so each of its requests is asked first where
/// it goes. The answer is the page client's own rule (SearchPageReader.ConnectToPublicAddressAsync): a public name,
/// and every address it resolves to public.
/// </summary>
[TestFixture]
public sealed class PageDestinationTests
{
    private static readonly IPAddress Public = IPAddress.Parse("93.184.216.34");

    [Test]
    public async Task ANameThatResolvesOnlyToPublicAddressesMayBeAsked()
    {
        var asked = new List<string>();
        Task<IPAddress[]> Resolve(string host, CancellationToken cancellationToken)
        {
            asked.Add(host);
            return Task.FromResult<IPAddress[]>([Public, IPAddress.Parse("2606:4700::1111")]);
        }

        bool goes = await PageDestination.IsPublicAsync(new Uri("https://example.com/a?b=1"), Resolve, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(goes, Is.True);
            Assert.That(asked, Is.EqualTo(new[] { "example.com" }));
        });
    }

    // The router's panel under a public-looking name, a name that answers with this PC, and one that answers with both.
    [TestCase("192.168.1.1")]
    [TestCase("127.0.0.1")]
    [TestCase("10.0.0.7")]
    [TestCase("100.101.102.103")]
    [TestCase("169.254.169.254")]
    [TestCase("::1")]
    [TestCase("fd00::1")]
    [TestCase("93.184.216.34 192.168.1.10")]
    [TestCase("")]
    public async Task ANameThatResolvesIntoThisPcOrTheLocalNetworkMayNot(string addresses)
    {
        IPAddress[] resolved = [.. addresses.Split(' ', StringSplitOptions.RemoveEmptyEntries).Select(IPAddress.Parse)];

        bool goes = await PageDestination.IsPublicAsync(
            new Uri("http://example.com:11434/api/tags"),
            (_, _) => Task.FromResult(resolved),
            CancellationToken.None);

        Assert.That(goes, Is.False);
    }

    [Test]
    public async Task ANameThatDoesNotResolveMayNot()
    {
        bool goes = await PageDestination.IsPublicAsync(
            new Uri("https://no-such-host.example/"),
            (_, _) => Task.FromException<IPAddress[]>(new SocketException((int)SocketError.HostNotFound)),
            CancellationToken.None);

        Assert.That(goes, Is.False);
    }

    // What the address says by itself is not looked up: a literal address is judged as it is, and this PC, the local
    // network and what is not the web are refused without asking anyone.
    [Test]
    public async Task WhatTheAddressSaysByItselfIsNotLookedUp()
    {
        int lookups = 0;
        Task<IPAddress[]> Resolve(string host, CancellationToken cancellationToken)
        {
            lookups++;
            return Task.FromResult<IPAddress[]>([Public]);
        }

        var answers = new Dictionary<string, bool>();
        foreach (string address in new[]
        {
            "https://93.184.216.34/", "http://127.0.0.1:8080/v1/models", "http://localhost:11434/api/tags",
            "http://192.168.1.1/", "http://[::1]:8080/", "https://router/", "https://nas.local/", "ws://example.com/",
            "file:///C:/Users/x/secret.txt", "https://user:pass@example.com/",
        })
        {
            answers[address] = await PageDestination.IsPublicAsync(new Uri(address), Resolve, CancellationToken.None);
        }

        Assert.Multiple(() =>
        {
            Assert.That(answers.Where(static answer => answer.Value).Select(static answer => answer.Key),
                Is.EqualTo(new[] { "https://93.184.216.34/" }));
            Assert.That(lookups, Is.Zero);
            Assert.That(PageDestination.IsPublicByName(new Uri("https://example.com/")), Is.True);
            Assert.That(PageDestination.IsPublicByName(new Uri("http://127.0.0.1:8080/")), Is.False);
        });
    }
}
