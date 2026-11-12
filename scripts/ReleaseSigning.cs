#:property TargetFramework=net10.0-windows10.0.19041.0
#:property UseWindowsForms=true
#:property PublishAot=false

// FIR1 (decisión A1 del líder, 10-11-2026): the key that signs BAXY's updates and the signature of a release.json.
//
//   dotnet run scripts/ReleaseSigning.cs -- new     [--name N] [--folder F] --public <out.pem>
//   dotnet run scripts/ReleaseSigning.cs -- public  [--name N] [--folder F] --public <out.pem>
//   dotnet run scripts/ReleaseSigning.cs -- sign    [--name N] [--folder F] <release.json>
//   dotnet run scripts/ReleaseSigning.cs -- verify  --keys <keys.pem> <release.json>
//   dotnet run scripts/ReleaseSigning.cs -- backup  [--name N] [--folder F] --out <file.p8.pem>
//   dotnet run scripts/ReleaseSigning.cs -- restore [--name N] [--folder F] --from <file.p8.pem>
//
// ECDSA P-256 with SHA-256, as .NET ships it (learn.microsoft.com/dotnet/api/system.security.cryptography.ecdsa, read
// 2026-11-10): the signature is release.json.sig beside release.json, the base64 of r||s (IEEE P1363, 64 bytes) over the
// file's exact bytes; src/Baxy.Core/Operations/ReleaseSignature.cs checks it. One small signed file that names every
// other file by size and SHA-256 is what TUF's «targets» role and minisign's signed checksum lists do
// (theupdateframework.github.io/specification/latest, read 2026-11-10).
//
// The private key never sits in the repository: it is a PKCS#8 file in %APPDATA%\BAXY-firma\<name>.key, encrypted with
// DPAPI for the Windows user who made it (ProtectedData, DataProtectionScope.CurrentUser: «only threads running under the
// current user context can unprotect the data», learn.microsoft.com/dotnet/api/system.security.cryptography.protecteddata,
// read 2026-11-10). That file opens only on this machine under this user: «backup» writes a password-protected PKCS#8
// (AES-256-CBC, PBKDF2-SHA256, 600 000 iterations, the OWASP figure for PBKDF2-HMAC-SHA256,
// cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html, read 2026-11-10) to keep apart from the PC,
// and «restore» brings it back on another machine or user. The password comes from BAXY_SIGNING_PASSWORD or is asked.
using System.Security.Cryptography;
using System.Text;

const string DefaultName = "BAXY-actualizaciones";
string[] given = args;
string? command = given.FirstOrDefault();
string name = Option("--name") ?? DefaultName;
string folder = Option("--folder") ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "BAXY-firma");
string keyFile = Path.Combine(folder, name + ".key");
// The one argument that is not an option's value: the release.json of sign and verify.
string? file = given.Where((value, index) => index > 0 && !value.StartsWith("--", StringComparison.Ordinal)
    && !given[index - 1].StartsWith("--", StringComparison.Ordinal)).LastOrDefault();

try
{
    switch (command)
    {
        case "new":
            if (File.Exists(keyFile))
            {
                return Fail($"{keyFile} already exists: a second key would orphan every BAXY that trusts the first");
            }

            using (ECDsa key = ECDsa.Create(ECCurve.NamedCurves.nistP256))
            {
                Save(key);
                return WritePublic(key, Required("--public"));
            }

        case "public":
            using (ECDsa key = Load())
            {
                return WritePublic(key, Required("--public"));
            }

        case "sign":
            using (ECDsa key = Load())
            {
                string manifest = file ?? throw new ArgumentException("which release.json?");
                byte[] signature = key.SignData(File.ReadAllBytes(manifest), HashAlgorithmName.SHA256);
                // What was signed is checked with the public half before the file is written: a broken key never leaves a .sig.
                if (!key.VerifyData(File.ReadAllBytes(manifest), signature, HashAlgorithmName.SHA256))
                {
                    return Fail("the signature does not verify with its own key");
                }

                File.WriteAllText(manifest + ".sig", Convert.ToBase64String(signature) + "\n", Encoding.ASCII);
                Console.WriteLine($"{manifest}.sig {Fingerprint(key)}");
                return 0;
            }

        case "verify":
        {
            string manifest = file ?? throw new ArgumentException("which release.json?");
            byte[] signature = Convert.FromBase64String(File.ReadAllText(manifest + ".sig", Encoding.ASCII).Trim());
            foreach (string pem in Blocks(File.ReadAllText(Required("--keys"), Encoding.ASCII)))
            {
                using ECDsa key = ECDsa.Create();
                key.ImportFromPem(pem);
                if (key.VerifyData(File.ReadAllBytes(manifest), signature, HashAlgorithmName.SHA256))
                {
                    Console.WriteLine($"valid {Fingerprint(key)}");
                    return 0;
                }
            }

            return Fail("not signed by any of those keys");
        }

        case "backup":
            using (ECDsa key = Load())
            {
                string target = Required("--out");
                PbeParameters pbe = new(PbeEncryptionAlgorithm.Aes256Cbc, HashAlgorithmName.SHA256, 600_000);
                File.WriteAllText(target, key.ExportEncryptedPkcs8PrivateKeyPem(Password(confirm: true), pbe), Encoding.ASCII);
                Console.WriteLine($"{target} {Fingerprint(key)}");
                return 0;
            }

        case "restore":
            if (File.Exists(keyFile))
            {
                return Fail($"{keyFile} already exists");
            }

            using (ECDsa key = ECDsa.Create())
            {
                key.ImportFromEncryptedPem(File.ReadAllText(Required("--from"), Encoding.ASCII), Password(confirm: false));
                Save(key);
                Console.WriteLine($"{keyFile} {Fingerprint(key)}");
                return 0;
            }

        default:
            return Fail("new | public | sign | verify | backup | restore (see the head of this file)");
    }
}
catch (Exception failed) when (failed is IOException or UnauthorizedAccessException or CryptographicException
    or ArgumentException or FormatException)
{
    return Fail(failed.Message);
}

string? Option(string option)
{
    int at = Array.IndexOf(given, option);
    return at >= 0 && at + 1 < given.Length ? given[at + 1] : null;
}

string Required(string option) => Option(option) ?? throw new ArgumentException($"{option} is missing");

void Save(ECDsa key)
{
    Directory.CreateDirectory(folder);
    byte[] plain = key.ExportPkcs8PrivateKey();
    try
    {
        File.WriteAllBytes(keyFile, ProtectedData.Protect(plain, Encoding.ASCII.GetBytes(name), DataProtectionScope.CurrentUser));
    }
    finally
    {
        CryptographicOperations.ZeroMemory(plain);
    }
}

ECDsa Load()
{
    byte[] plain = ProtectedData.Unprotect(File.ReadAllBytes(keyFile), Encoding.ASCII.GetBytes(name), DataProtectionScope.CurrentUser);
    try
    {
        ECDsa key = ECDsa.Create();
        key.ImportPkcs8PrivateKey(plain, out _);
        return key;
    }
    finally
    {
        CryptographicOperations.ZeroMemory(plain);
    }
}

int WritePublic(ECDsa key, string target)
{
    File.WriteAllText(target, key.ExportSubjectPublicKeyInfoPem() + "\n", Encoding.ASCII);
    Console.WriteLine($"{target} {Fingerprint(key)}");
    return 0;
}

static string Fingerprint(ECDsa key) => Convert.ToHexStringLower(SHA256.HashData(key.ExportSubjectPublicKeyInfo()));

static IEnumerable<string> Blocks(string text)
{
    const string End = "-----END PUBLIC KEY-----";
    int start = 0;
    while (text.IndexOf("-----BEGIN PUBLIC KEY-----", start, StringComparison.Ordinal) is int begin and >= 0)
    {
        int end = text.IndexOf(End, begin, StringComparison.Ordinal) + End.Length;
        yield return text[begin..end];
        start = end;
    }
}

static string Password(bool confirm)
{
    if (Environment.GetEnvironmentVariable("BAXY_SIGNING_PASSWORD") is { Length: > 0 } given)
    {
        return given;
    }

    string first = Ask("Password: ");
    if (confirm && Ask("Again: ") != first)
    {
        throw new ArgumentException("the two passwords differ");
    }

    return first.Length >= 12 ? first : throw new ArgumentException("a password of at least 12 characters");
}

static string Ask(string prompt)
{
    Console.Error.Write(prompt);
    StringBuilder typed = new();
    for (ConsoleKeyInfo key = Console.ReadKey(intercept: true); key.Key != ConsoleKey.Enter; key = Console.ReadKey(intercept: true))
    {
        if (key.Key == ConsoleKey.Backspace && typed.Length > 0)
        {
            typed.Length--;
        }
        else if (!char.IsControl(key.KeyChar))
        {
            typed.Append(key.KeyChar);
        }
    }

    Console.Error.WriteLine();
    return typed.ToString();
}

static int Fail(string why)
{
    Console.Error.WriteLine($"ReleaseSigning: {why}");
    return 1;
}
