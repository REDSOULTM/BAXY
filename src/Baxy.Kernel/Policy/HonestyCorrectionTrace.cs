namespace Baxy.Kernel.Policy;

/// <summary>
/// Traza durable de autocorrección: una afirmación desmentida por la
/// verificación se corrige sola, sin esperar a que pregunten.
/// </summary>
public sealed record HonestyCorrectionTrace(
    string Claim,
    string Verification,
    string Correction);
