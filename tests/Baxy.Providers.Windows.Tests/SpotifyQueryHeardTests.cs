using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// e2e nb-29 («otra canción de los Bunkers»): the leftmost play control was a playlist's and Romeo Santos played, told as
// done. What plays is said when it holds none of the words searched.
public sealed class SpotifyQueryHeardTests
{
    [TestCase("Bunkers", "bailando solo de los bunkers", "Los Bunkers - Bailando Solo", true)]
    [TestCase("Bunkers", "propuesta indecente de romeo santos", "Romeo Santos - Propuesta Indecente", false)]
    [TestCase("los Bunkers", "propuesta indecente de los santos", "", false)]
    [TestCase("Búnkers", "nada nuevo bajo el sol de los bunkers", "", true)]
    [TestCase("rock", "rock with you single version de michael jackson", "", true)]
    [TestCase("de la", "cualquier cosa", "", true)]
    [TestCase("Bunkers", "", "", true)]
    public void WhatPlaysHoldsAWordOfTheSearch(string query, string nowPlaying, string title, bool heard) =>
        Assert.That(SpotifyDesktopAdapter.QueryHeard(query, nowPlaying, title), Is.EqualTo(heard));
}
