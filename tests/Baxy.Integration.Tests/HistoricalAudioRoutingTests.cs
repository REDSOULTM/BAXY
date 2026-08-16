using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class HistoricalAudioRoutingTests
{
    private const string VolumeOracleIdsSha256 =
        "b1ddcd0623b9456f6852a7dc1b6c00ff1b4529ad24f2a0bcb1b0fce3c99d2c0b";
    private const string MuteOracleIdsSha256 =
        "0059de3914395a5e07beb2b3ccc57691bac2735d44455c7e0438a28dcf5f97c1";
    private const string NamedVolumeAliasIdsSha256 =
        "2c8aef1330fd16fdcf98b27dd2d5acae77f1e5d54c3f8692a600add3375bf39b";
    private const string StatusOracleIdsSha256 =
        "cd3512c246ca7b4fe29f98e944eac5885cd73ca478a4fa9183d21edb409c60fb";
    private const string CombinedOracleIdsSha256 =
        "e84eb27f2ff4d681304212051f1c3543c134edeedc6f9c3955eb64e918dec366";
    private const string HardNegativeIdsSha256 =
        "22087a6b94be7d200c152f2c0329f21acfa6b8160550e218f4fc3c9fe16628e1";

    private static readonly IReadOnlyDictionary<int, string[]> FrozenVolumeOracle =
        new Dictionary<int, string[]>
        {
            [0] = ["msg_05e8327cbd8e5443a676"],
            [5] = ["msg_c784e0527622c586e641"],
            [8] =
            [
                "msg_5e0703d1e2e225d8e398", "msg_83e6629ded7e56e8c896",
                "msg_929132743cd3652d70c4",
            ],
            [10] =
            [
                "msg_075561fa45a541c52266", "msg_1c2dc23c99248a766c69",
                "msg_20670a153dd7ac1c94a6", "msg_3209791442d4c401b9b3",
                "msg_55bf6ca71bced89650bb", "msg_5654f176cef91fd295fa",
                "msg_5678005f7946efcc21c7", "msg_8ca05d6502299cf1f80c",
                "msg_b464bbd1535c036e07a5", "msg_de1dc39bbfe7c525631f",
                "msg_f25ff9bcc45d55370113",
            ],
            [12] = ["msg_10b69e0ab824242ba6b6"],
            [15] =
            [
                "msg_04d9bfce58d9220540de", "msg_1720be72f6a66614bd34",
                "msg_51750f862b0089da6358", "msg_e2ee3500130619bf1821",
            ],
            [18] = ["msg_25713a74f93a06ff21be"],
            [20] =
            [
                "msg_0ccb0a4a2110f67ce29a", "msg_0f267f02f6cb9db5ba46",
                "msg_0f5fc9027f2fd70f0b03", "msg_10e3f69ae2513baa17a9",
                "msg_120c963d998d6c8f01aa", "msg_138883f1bb05fe02d7a3",
                "msg_2cd033388d72f08e9d73", "msg_3675b9d5811ce7b83179",
                "msg_5ec21724515008ee2cf8", "msg_618ef502c3968f568733",
                "msg_792cf8493d4a3f54aa4e", "msg_8b6f078ad5c9ecf1c8ec",
                "msg_989f41886ca069e8403d", "msg_9a6a31e398282e673bd8",
                "msg_9d0db275e6fd32689d3e", "msg_d0cd0612b7f1d7e9c411",
                "msg_d454f790b1b77eecc513", "msg_d8331f387176765d7fc9",
                "msg_e98388d5bd4ed1d8f614", "msg_f086cf01a3cfc562337c",
                "msg_f870d71249bffc4a3276", "msg_fd2397faef3093878eab",
                "msg_fe3f4464f38d52091267", "msg_907d788a2854c7cbb129",
                "msg_ef12bb5e0097efbd83ec",
            ],
            [22] = ["msg_a49271d0d9300f5c3117"],
            [25] =
            [
                "msg_38488114be485a197f9b", "msg_45c3bcc9cf9c669bbebd",
                "msg_65b65ec3920bb9fee69a", "msg_f9626e4d422d6a1eddcb",
            ],
            [26] = ["msg_959d7894e418f8d26e7a"],
            [28] = ["msg_6769925cb691c2f58ed5"],
            [30] =
            [
                "msg_17b326391e6180aeb38a", "msg_24cc3500a45acfbb62be",
                "msg_262406544412d2bd0c32", "msg_2bd6786d8bfecb1f901f",
                "msg_2f8e09c640dd064b8bb8", "msg_3d01f75f5a180a4a1d53",
                "msg_4a873999a00c3b9146fd", "msg_4b77baeb09fe39e988b2",
                "msg_5fea4dab62b69a91cfe9", "msg_6504f5332900e5ea5302",
                "msg_7503f71dcf61559f043b", "msg_786b847c9d2d184026ad",
                "msg_80840ce36b75c2d6fb1c", "msg_9e2e5afe38a8505d25dd",
                "msg_aa771c0ef82415cc6dfc", "msg_b9fb2f7a83536fd46fd9",
                "msg_c880026738be4b6560bf", "msg_d222f9ed2a2f2c7c95ad",
                "msg_dd0d04d333c6a5c31c4b", "msg_dd2c4c575e300eaa7ae9",
            ],
            [33] = ["msg_15888e1c122a54081cfd"],
            [35] =
            [
                "msg_1d27b2983b67ee8de10c", "msg_28a16edffe6593c77624",
                "msg_29e1db1929eb4c12071b", "msg_4cea6a03701705f4bfd6",
                "msg_5bafd621a4e563b3fc98", "msg_60e0ccdd48209471221e",
                "msg_8f136ab35e74efb73e3f", "msg_93b907f913d298dcc1f8",
            ],
            [38] = ["msg_dec5592eedcd7e64badb"],
            [40] =
            [
                "msg_194c43226b70db73f820", "msg_74ea83528305b0c0f0c0",
                "msg_b645f1c2adfdfe814572", "msg_d79ea47c5701ab11c150",
            ],
            [44] = ["msg_0190363ebfdc1a716f0d"],
            [45] =
            [
                "msg_4c34f2192ab0a8aeb2b5", "msg_b64ffa14a0f0f860f5a7",
                "msg_cebfa1c22f3f4efa568f",
            ],
            [48] = ["msg_f514d6b62105922505fd"],
            [50] =
            [
                "msg_14c330c05fcef481ca10", "msg_1fa9f566ed1d29869ea3",
                "msg_2d6da14aba470a45ef8b", "msg_320bf8f061dc64048c00",
                "msg_4164c710afe90d569213", "msg_6e018464e6c86bd4a747",
                "msg_a3e0d4b5a1c59e082167", "msg_a93891a56f67eba1182d",
                "msg_f3b7cce3845f0d8adb25", "msg_f9c5dbe65f536c4c7e31",
                "msg_fca95e4a81adcbf046c2",
            ],
            [55] = ["msg_3401ad0ae952b56bf435", "msg_f4b8d64aa3475c433822"],
            [56] = ["msg_2edac3130c6a3637a364"],
            [60] =
            [
                "msg_2ba2da98b86b6a505ec9", "msg_2f7529b401f552cc2cc3",
                "msg_b2b1603ddd98c474f8ef", "msg_fba181ed91580ee0c1f4",
            ],
            [65] = ["msg_0f2b5acdd27822427ea1"],
            [70] =
            [
                "msg_0991601cca1e299b1f92", "msg_3a1bc930a2592f535acd",
                "msg_73e22f90d6d760106170", "msg_ab60daba3a9852a07546",
            ],
            [78] = ["msg_0367d25b538df682da14"],
            [80] =
            [
                "msg_406f67425aa4206e3b10", "msg_723212e971c7a49a8620",
                "msg_d34da615456382428c6e", "msg_f00e49726561cf301ad1",
            ],
            [88] = ["msg_c3c006705707f2ba8514"],
            [90] = ["msg_7747b33c0f134b6e95a0", "msg_7833f5abb1aec9b90f21"],
            [100] =
            [
                "msg_0d45da141f6f0b9f951e", "msg_2381cac38c2cbb52b0ef",
                "msg_ed6fb0995bc40b7caec8",
            ],
        };

    private static readonly IReadOnlyDictionary<bool, string[]> FrozenMuteOracle =
        new Dictionary<bool, string[]>
        {
            [false] =
            [
                "msg_2b20deeb3cac9aec0878", "msg_32a9103b84e5d5f28ef7",
                "msg_38d03d66a142eea372dd", "msg_9367170923e676b25acf",
                "msg_c766eaf94529de7cc86a", "msg_d5561fa0f708efc9551e",
                "msg_ddbadb9f589f1bda88b3",
            ],
            [true] =
            [
                "msg_456bb310a63a344704d8", "msg_5104c628778381b8d449",
                "msg_660a81fe0d01c4b96729", "msg_7b7c26cb263eb29840d3",
                "msg_84a19319a9a1b19554d1", "msg_8d5936dfce659cf7a66f",
                "msg_95c69928a323e45c7889", "msg_9a6b4fc3ab3f9b35b982",
                "msg_a49670082e97d4062555",
            ],
        };

    private static readonly IReadOnlyDictionary<int, string[]> FrozenNamedVolumeAliasOracle =
        new Dictionary<int, string[]>
        {
            [0] =
            [
                "msg_7b5fb315ceec36880c42", "msg_8aecf2506b056897783a",
            ],
            [10] =
            [
                "msg_1acbc9e9889b29d7cfee", "msg_22ba6c64e71885221ca2",
                "msg_4e5c0f58e780dc0a69c1",
            ],
            [20] = ["msg_8d4815418499be30dc93"],
            [50] =
            [
                "msg_5267f608daeac78b0297", "msg_fa6d3b69b01df25b3313",
            ],
            [100] =
            [
                "msg_0c0eac6de5ce95b7f0ac", "msg_87b0588cfad78d45a5f6",
                "msg_e148fcf95e372b7da786", "msg_ecdc1b653c8fcbd476e3",
            ],
        };

    private static readonly string[] FrozenStatusOracle =
    [
        "msg_11bebb8ffbeb2e976ac4", "msg_1288704b9643a4a1d4e1",
        "msg_1c22e0cf4c5383bad801", "msg_22ed81cfe7e5a2ccfad8",
        "msg_38471afe056eaf737661", "msg_3bc24d4ad463eb1ca2f0",
        "msg_63f5dec2a3ec5f499193", "msg_79466a579827ab559899",
        "msg_89eb1eabaa03a75c157c", "msg_bf6d713c8957b2f65782",
        "msg_bf87cd86f01aa8fc3659", "msg_c170379cbadbb08e6b98",
        "msg_cf264814dae8e19b76df", "msg_d908e2aaeabfcca17109",
        "msg_df8ea3b8196c5bc7e728", "msg_f72552b9b7ac1caf8af3",
    ];

    private static readonly IReadOnlyDictionary<string, string[]> FrozenHardNegatives =
        new Dictionary<string, string[]>(StringComparer.Ordinal)
        {
            ["relative"] =
            [
                "msg_83fa827afa29b6b37198", "msg_845217eff716801c0606",
                "msg_88e1695b86f1d43f7567", "msg_ce0dfe761ea3ea849242",
                "msg_d3b2f1ede2690d9d985b", "msg_d80e05862cd59b8ee16b",
                "msg_e23be85039d6505208b4",
            ],
            ["app_specific_volume"] =
            [
                "msg_78aeb4933c1e84587bab", "msg_8dab443234c7b3b0fbcd",
                "msg_a826330f20eaa93c6b49", "msg_d6b7049c8717eeeae008",
            ],
            ["microphone"] =
            [
                "msg_14f06261113d16e70546", "msg_39843a6a78eb2b438612",
                "msg_4fb6a76c38a825228df4", "msg_5c614c927f5f0de2e806",
                "msg_9ec982ef5a445ac619e5", "msg_ad3df032471147ee5317",
                "msg_bbd227e1654285b35b97", "msg_c80597ccac7cace8e8ad",
                "msg_fa27bbfaba97fdd3bfbc",
            ],
            ["discord_button"] =
            [
                "msg_00f6df82a479f8fe18ae", "msg_07345ea6d9d5b1eba3ff",
                "msg_0eae33e24aad984730f1", "msg_13863ac2d295b811358b",
                "msg_14255d1d442e52e7abb0", "msg_19634f8338def5f94035",
                "msg_19ef83c9f8ba03d33247", "msg_27782b55d9ffe38eb122",
                "msg_2b13d101f71b534ded69", "msg_300f6d37acc076875348",
                "msg_3f30708d8bbf9a9ef440", "msg_41ab4f9fe8e369c9e017",
                "msg_44acc68e3f917ed44ae6", "msg_46f76823808094dcbdb1",
                "msg_4bcafac26b77c35a6806", "msg_51ccc54a1971ae6a7745",
                "msg_5267f3873806611f5938", "msg_540e6b705ef338a37300",
                "msg_5655eadd628d81eeb43e", "msg_58279e5a4408edd64ea1",
                "msg_5aa0d953fe59e7444dd1", "msg_5c011ed3fcb037efc0d9",
                "msg_5e136c7991e0bd5e8dc5", "msg_5fc0961e61bb006ef8d9",
                "msg_607a55e46a124740f8f8", "msg_63fafac0e2d067ff2154",
                "msg_6435aed1cf03a3f35d21", "msg_6bc6105c21ad2d946ffe",
                "msg_6be1b9b5c9c87629be86", "msg_74a55afff8b0ac3b7019",
                "msg_79644fa6c8fd40d20b70", "msg_79a95e1a9be1b68ea54d",
                "msg_7d2c929cf97a1409632e", "msg_829ebefc94b3c9afb18c",
                "msg_82afeba32f3ee6dc6d76", "msg_92c58d6f00c14caeb7a1",
                "msg_9b734f5f1e42e708b66a", "msg_a21809351f5019dae596",
                "msg_a3b2cb27596c41d852b3", "msg_aa946b0446f6e941ac40",
                "msg_ab7912771943c281d443", "msg_ad9a35c710c8f68e0fb3",
                "msg_adbbb615eb84ff403676", "msg_b3bdd26ec6ace0e4e18a",
                "msg_ba2c60d1b67742bafb13", "msg_bc94ea12002e76374910",
                "msg_c04ee01e1c7db580b399", "msg_c161a4326e721d21569f",
                "msg_c665c28fd62b56a25e50", "msg_c80de5c15f515088a76f",
                "msg_cab8db7f112114355ec1", "msg_d0f9ba7263c73ca74a4a",
                "msg_d59b28d0f90d2ca9520f", "msg_dc112c4ac6dd4f5ddc92",
                "msg_dee3b8b58325d1b7f9f1", "msg_e5dc428ae37bc49af153",
                "msg_e8193e460820347c5a23", "msg_e9e5c7000d3644ecb95e",
                "msg_eaa614c8a385e76e9521", "msg_f2ccce959a616d6224c2",
                "msg_f86a179d3c760dc9d784", "msg_f9f2bbb5cda84fa26c7f",
                "msg_fc32c083ff85912f6e0e",
            ],
            ["media_control"] =
            [
                "msg_005753049e7a2c6d5df8", "msg_1044acd1aa4fc5451af1",
                "msg_263449d5634d4c478a49", "msg_40426107a23bd92e045a",
                "msg_5c68cd2c6c0b7541ed4c", "msg_77b7eaf53b13739cd51b",
                "msg_827aab76be60c6644776", "msg_8500f1cd2dbe8703dd59",
                "msg_893891e82add744e778c", "msg_8b2c5ce1ab6a2b0846c4",
                "msg_8e7900587b8473161073", "msg_a1a429bfa58d13cc31ff",
                "msg_a2368852f0f1e58e212d", "msg_ab08de6d9ac2d7a4d705",
                "msg_baa92ea29cf7ce175550", "msg_bf3e8c04947fdae6dabb",
                "msg_c0a273b4ee41e0e422ff", "msg_c968a82378641cceb18a",
                "msg_e9444fa86bff476ec8c8",
            ],
            ["composition"] =
            [
                "msg_280199dec86496c87826", "msg_500284339eea5f9172bd",
                "msg_6166ffac59eae4ca3c41", "msg_66316b07a0c50eb292ae",
                "msg_9eae4b301065ac342756",
            ],
            ["ambiguous_mute"] =
            [
                "msg_1b62576c30d80a05953d", "msg_3ec133e1cea0e60244f6",
                "msg_3ee5c3e1caa301a802b3", "msg_9e2dfbb75297dda484fd",
                "msg_b1123ad80dfb3522c13e", "msg_e36b981bd69efd8a016b",
            ],
            ["negated"] =
            [
                "msg_0841f17f6107365dca1e", "msg_22ac78d858e48ddcff60",
                "msg_2fdc733b6f64878bdb24", "msg_3a5d54e2d9f757046c27",
                "msg_49a843a4578354aefd9a", "msg_57f4bc13854c2495eed8",
                "msg_5e862f52e5f4af5446bb", "msg_a27f5e44dc2eac66fe60",
                "msg_beb56864ed17b9ac76c7", "msg_decc9d5a9162ed958baf",
                "msg_e9195adaf4e41863aed0", "msg_f43ef3050d7bd63140ad",
                "msg_fabd5c6f1be2585d976a",
            ],
            ["accent_polarity"] =
            [
                "msg_12c34f82447d58a6ed9d", "msg_22d9f38bed38ed73f74b",
            ],
        };

    [Test]
    public void FrozenAbsoluteVolumeOracleRoutesOneHundredTwentySevenOfOneHundredTwentySeven()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        Dictionary<string, MappingRow> mappings = LoadMappings();
        (int Level, string Id)[] expected = FrozenVolumeOracle
            .SelectMany(static pair => pair.Value.Select(id => (pair.Key, id)))
            .OrderBy(static item => item.id, StringComparer.Ordinal)
            .Select(static item => (item.Key, item.id))
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(expected, Has.Length.EqualTo(127));
            Assert.That(expected.Select(static item => item.Id).Distinct(), Has.Exactly(127).Items);
            Assert.That(HashIds(expected.Select(static item => item.Id)), Is.EqualTo(VolumeOracleIdsSha256));
        });

        var literals = new HashSet<string>(StringComparer.Ordinal);
        var sources = new HashSet<string>(StringComparer.Ordinal);
        var missions = new HashSet<string>(StringComparer.Ordinal);
        foreach ((int expectedLevel, string messageId) in expected)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            AssertPositiveCorpusContract(row!, messageId, "audio.volume");
            Assert.That(mappings.TryGetValue(messageId, out MappingRow? mapping), Is.True, messageId);
            AssertHistoricalMappingContract(mapping!, messageId, "audio.volume");

            bool parsed = NaturalNoteRequestParser.TryParse(row!.TextLiteral, out RoutedOperation? operation);
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.True, $"{messageId}: {row.TextLiteral}");
                Assert.That(operation?.Name, Is.EqualTo("audio.volume"), messageId);
                Assert.That(operation?.Arguments["level"]?.GetValue<int>(), Is.EqualTo(expectedLevel), messageId);
                Assert.That(operation?.Arguments, Has.Count.EqualTo(1), messageId);
            });

            literals.Add(row.TextLiteral.ToLowerInvariant());
            sources.Add(row.Source);
            missions.Add(row.CanonicalMissionId);
        }

        Assert.Multiple(() =>
        {
            Assert.That(literals, Has.Count.EqualTo(97));
            Assert.That(sources, Has.Count.EqualTo(14));
            Assert.That(missions, Is.EquivalentTo(new[] { "mission_user_mission_audio_volume_3815947eab" }));
        });
    }

    [Test]
    public void FrozenGlobalOutputMuteOracleRoutesSixteenOfSixteen()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        Dictionary<string, MappingRow> mappings = LoadMappings();
        (bool State, string Id)[] expected = FrozenMuteOracle
            .SelectMany(static pair => pair.Value.Select(id => (pair.Key, id)))
            .OrderBy(static item => item.id, StringComparer.Ordinal)
            .Select(static item => (item.Key, item.id))
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(expected, Has.Length.EqualTo(16));
            Assert.That(expected.Select(static item => item.Id).Distinct(), Has.Exactly(16).Items);
            Assert.That(HashIds(expected.Select(static item => item.Id)), Is.EqualTo(MuteOracleIdsSha256));
        });

        var literals = new HashSet<string>(StringComparer.Ordinal);
        var sources = new HashSet<string>(StringComparer.Ordinal);
        var missions = new HashSet<string>(StringComparer.Ordinal);
        foreach ((bool expectedState, string messageId) in expected)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            AssertPositiveCorpusContract(row!, messageId, "audio.mute");
            Assert.That(mappings.TryGetValue(messageId, out MappingRow? mapping), Is.True, messageId);
            AssertHistoricalMappingContract(mapping!, messageId, "audio.mute");

            bool parsed = NaturalNoteRequestParser.TryParse(row!.TextLiteral, out RoutedOperation? operation);
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.True, $"{messageId}: {row.TextLiteral}");
                Assert.That(operation?.Name, Is.EqualTo("audio.mute"), messageId);
                Assert.That(operation?.Arguments["state"]?.GetValue<bool>(), Is.EqualTo(expectedState), messageId);
                Assert.That(operation?.Arguments, Has.Count.EqualTo(1), messageId);
            });

            literals.Add(row.TextLiteral.ToLowerInvariant());
            sources.Add(row.Source);
            missions.Add(row.CanonicalMissionId);
        }

        Assert.Multiple(() =>
        {
            Assert.That(literals, Has.Count.EqualTo(12));
            Assert.That(sources, Has.Count.EqualTo(7));
            Assert.That(missions, Is.EquivalentTo(new[] { "mission_user_mission_audio_mute_aefd4fe552" }));
        });
    }

    [Test]
    public void FrozenNamedAbsoluteVolumeAliasesRouteTwelveOfTwelve()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        Dictionary<string, MappingRow> mappings = LoadMappings();
        (int Level, string Id)[] expected = FrozenNamedVolumeAliasOracle
            .SelectMany(static pair => pair.Value.Select(id => (pair.Key, id)))
            .OrderBy(static item => item.id, StringComparer.Ordinal)
            .Select(static item => (item.Key, item.id))
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(expected, Has.Length.EqualTo(12));
            Assert.That(expected.Select(static item => item.Id).Distinct(),
                Has.Exactly(12).Items);
            Assert.That(HashIds(expected.Select(static item => item.Id)),
                Is.EqualTo(NamedVolumeAliasIdsSha256));
        });

        var literals = new HashSet<string>(StringComparer.Ordinal);
        foreach ((int expectedLevel, string messageId) in expected)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            AssertPositiveCorpusContract(row!, messageId, "audio.volume");
            Assert.That(mappings.TryGetValue(messageId, out MappingRow? mapping), Is.True, messageId);
            AssertHistoricalMappingContract(mapping!, messageId, "audio.volume");

            bool parsed = NaturalNoteRequestParser.TryParse(
                row!.TextLiteral,
                out RoutedOperation? operation);
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.True, $"{messageId}: {row.TextLiteral}");
                Assert.That(operation?.Name, Is.EqualTo("audio.volume"), messageId);
                Assert.That(operation?.Arguments["level"]?.GetValue<int>(),
                    Is.EqualTo(expectedLevel), messageId);
                Assert.That(operation?.Arguments, Has.Count.EqualTo(1), messageId);
            });

            literals.Add(row.TextLiteral.ToLowerInvariant());
        }

        Assert.That(literals, Has.Count.EqualTo(9));
    }

    [Test]
    public void FrozenReadOnlyAudioStatusOracleRoutesSixteenOfSixteen()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        Dictionary<string, MappingRow> mappings = LoadMappings();
        string[] expected = FrozenStatusOracle.Order(StringComparer.Ordinal).ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(expected, Has.Length.EqualTo(16));
            Assert.That(expected.Distinct(), Has.Exactly(16).Items);
            Assert.That(HashIds(expected), Is.EqualTo(StatusOracleIdsSha256));
        });

        var literals = new HashSet<string>(StringComparer.Ordinal);
        var missions = new HashSet<string>(StringComparer.Ordinal);
        foreach (string messageId in expected)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            AssertPositiveCorpusContract(row!, messageId, "audio.status");
            Assert.That(mappings.TryGetValue(messageId, out MappingRow? mapping), Is.True, messageId);
            AssertHistoricalMappingContract(mapping!, messageId, "audio.status");

            bool parsed = NaturalNoteRequestParser.TryParse(
                row!.TextLiteral,
                out RoutedOperation? operation);
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.True, $"{messageId}: {row.TextLiteral}");
                Assert.That(operation?.Name, Is.EqualTo("audio.status"), messageId);
                Assert.That(operation?.Arguments, Is.Empty, messageId);
            });

            literals.Add(row.TextLiteral.ToLowerInvariant());
            missions.Add(row.CanonicalMissionId);
        }

        Assert.Multiple(() =>
        {
            Assert.That(literals, Has.Count.EqualTo(2));
            Assert.That(missions, Is.EquivalentTo(new[]
            {
                "mission_user_mission_audio_status_3f06791dcc",
            }));
        });
    }

    [Test]
    public void CombinedFrozenAudioOracleHasStableIdentity()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        string[] ids = FrozenVolumeOracle.Values
            .Concat(FrozenMuteOracle.Values)
            .Concat(FrozenNamedVolumeAliasOracle.Values)
            .SelectMany(static group => group)
            .Concat(FrozenStatusOracle)
            .Order(StringComparer.Ordinal)
            .ToArray();
        CorpusRow[] rows = ids.Select(id => corpus[id]).ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(ids, Has.Length.EqualTo(171));
            Assert.That(ids.Distinct(), Has.Exactly(171).Items);
            Assert.That(HashIds(ids), Is.EqualTo(CombinedOracleIdsSha256));
            Assert.That(
                rows.Select(static row => row.TextLiteral.ToLowerInvariant()).Distinct(),
                Has.Exactly(120).Items);
            Assert.That(
                rows.Select(static row => row.Source).Distinct(),
                Has.Exactly(14).Items);
            Assert.That(
                rows.Select(static row => row.CanonicalMissionId).Distinct(),
                Has.Exactly(3).Items);
        });
    }

    [Test]
    public void FrozenRelativeScopedMediaNegatedAndOutOfSliceRowsRemainFailClosed()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        string[] ids = FrozenHardNegatives.Values
            .SelectMany(static group => group)
            .Order(StringComparer.Ordinal)
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(ids, Has.Length.EqualTo(128));
            Assert.That(ids.Distinct(), Has.Exactly(128).Items);
            Assert.That(HashIds(ids), Is.EqualTo(HardNegativeIdsSha256));
        });

        foreach (string messageId in ids)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            bool parsed = NaturalNoteRequestParser.TryParse(row!.TextLiteral, out RoutedOperation? operation);

            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.False, $"{messageId}: {row.TextLiteral}");
                Assert.That(operation, Is.Null, messageId);
            });
        }
    }

    [Test]
    public void EntireFrozenCorpusRoutesExactlyTheOneHundredSeventyOneApprovedAudioIds()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        string[] approved = FrozenVolumeOracle.Values
            .Concat(FrozenMuteOracle.Values)
            .Concat(FrozenNamedVolumeAliasOracle.Values)
            .SelectMany(static group => group)
            .Concat(FrozenStatusOracle)
            .Order(StringComparer.Ordinal)
            .ToArray();
        var routed = new List<string>();

        foreach ((string messageId, CorpusRow row) in corpus)
        {
            if (string.IsNullOrWhiteSpace(row.TextLiteral)
                || !NaturalNoteRequestParser.TryParse(row.TextLiteral, out RoutedOperation? operation)
                || operation?.Name is not ("audio.volume" or "audio.mute" or "audio.status"))
            {
                continue;
            }

            routed.Add(messageId);
        }

        routed.Sort(StringComparer.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(routed, Has.Count.EqualTo(171));
            Assert.That(routed, Is.EqualTo(approved));
            Assert.That(HashIds(routed), Is.EqualTo(CombinedOracleIdsSha256));
        });
    }

    private static void AssertPositiveCorpusContract(
        CorpusRow row,
        string messageId,
        string operation)
    {
        Assert.Multiple(() =>
        {
            Assert.That(row.AcceptanceScope, Is.EqualTo("product_1_0"), messageId);
            Assert.That(row.Class, Is.EqualTo("user_mission"), messageId);
            Assert.That(row.Operations, Is.EqualTo(new[] { operation }), messageId);
            Assert.That(row.DeniedOperations, Is.Empty, messageId);
        });
    }

    private static void AssertHistoricalMappingContract(
        MappingRow row,
        string messageId,
        string operation)
    {
        string verification = operation switch
        {
            "audio.volume" => "Nivel de sesión/dispositivo leído después del cambio.",
            "audio.mute" => "Estado mute observado tras la acción.",
            _ => "Nivel y estado mute leídos de la salida predeterminada sin modificarla.",
        };
        string riskClass = operation == "audio.status" ? "read_only" : "low_reversible";
        string riskReason = operation == "audio.status"
            ? "La consulta solo lee el estado actual; no autoriza efectos físicos."
            : "La orden actual autoriza un efecto ordinario y reversible.";
        Assert.Multiple(() =>
        {
            Assert.That(row.AcceptanceScope, Is.EqualTo("product_1_0"), messageId);
            Assert.That(row.Operations, Is.EqualTo(new[] { operation }), messageId);
            Assert.That(row.DeniedOperations, Is.Empty, messageId);
            Assert.That(row.OutcomeType, Is.EqualTo("mission_must_implement"), messageId);
            Assert.That(row.ProviderRoles, Is.EqualTo(new[] { "audio_adapter" }), messageId);
            Assert.That(row.RiskClass, Is.EqualTo(riskClass), messageId);
            Assert.That(row.Confirmation, Is.EqualTo("not_required"), messageId);
            Assert.That(
                row.RiskReason,
                Is.EqualTo(riskReason),
                messageId);
            Assert.That(row.Plan, Is.EqualTo(new[] { $"Ejecutar y verificar {operation}." }), messageId);
            Assert.That(row.Verification, Is.EqualTo(new[] { verification }), messageId);
        });
    }

    private static Dictionary<string, CorpusRow> LoadCorpus()
    {
        var rows = new Dictionary<string, CorpusRow>(StringComparer.Ordinal);
        foreach (string line in File.ReadLines(FindDataPath("historical_messages.jsonl")))
        {
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            string id = root.GetProperty("message_id").GetString()!;
            rows.Add(id, new CorpusRow(
                root.GetProperty("text_literal").GetString()!,
                root.GetProperty("acceptance_scope").GetString()!,
                root.GetProperty("class").GetString()!,
                ReadStrings(root, "operations"),
                ReadStrings(root, "denied_operations"),
                root.GetProperty("source").GetString()!,
                root.GetProperty("canonical_mission_id").GetString()!));
        }

        return rows;
    }

    private static Dictionary<string, MappingRow> LoadMappings()
    {
        var rows = new Dictionary<string, MappingRow>(StringComparer.Ordinal);
        foreach (string line in File.ReadLines(FindDataPath("historical_message_mapping.jsonl")))
        {
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            JsonElement risk = root.GetProperty("risk");
            string id = root.GetProperty("message_id").GetString()!;
            rows.Add(id, new MappingRow(
                root.GetProperty("acceptance_scope").GetString()!,
                ReadStrings(root, "operations"),
                ReadStrings(root, "denied_operations"),
                root.GetProperty("outcome_type").GetString()!,
                ReadStrings(root, "provider_roles"),
                risk.GetProperty("class").GetString()!,
                risk.GetProperty("confirmation").GetString()!,
                risk.GetProperty("reason").GetString()!,
                ReadStrings(root, "plan"),
                ReadStrings(root, "verification")));
        }

        return rows;
    }

    private static string[] ReadStrings(JsonElement root, string propertyName) =>
        root.GetProperty(propertyName)
            .EnumerateArray()
            .Select(static value => value.GetString()!)
            .ToArray();

    private static string HashIds(IEnumerable<string> ids) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
            string.Concat(string.Join('\n', ids.Order(StringComparer.Ordinal)), "\n"))))
            .ToLowerInvariant();

    private static string FindDataPath(string fileName)
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null)
        {
            string candidate = Path.Combine(directory.FullName, "tests", "data", fileName);
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException($"Could not locate the frozen historical data file {fileName}.");
    }

    private sealed record CorpusRow(
        string TextLiteral,
        string AcceptanceScope,
        string Class,
        IReadOnlyList<string> Operations,
        IReadOnlyList<string> DeniedOperations,
        string Source,
        string CanonicalMissionId);

    private sealed record MappingRow(
        string AcceptanceScope,
        IReadOnlyList<string> Operations,
        IReadOnlyList<string> DeniedOperations,
        string OutcomeType,
        IReadOnlyList<string> ProviderRoles,
        string RiskClass,
        string Confirmation,
        string RiskReason,
        IReadOnlyList<string> Plan,
        IReadOnlyList<string> Verification);
}
