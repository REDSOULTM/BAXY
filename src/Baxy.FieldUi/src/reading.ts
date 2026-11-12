import type { ModelReading } from './causes';

/* VUL1 (2026-11-09): what the window says is left of the model's read never goes up while the person waits. On an RX
   7600 on Vulkan the host's count, taken from the pace measured so far, fell to «2 min» and then rose to 4 and 5 when
   the read slowed down (INFORME_AMD3.md §1): at 4 min of waiting the window promised more than it had at 2. A count
   above the least one already said is not said: the window says the read takes longer than expected, with its
   percentage, until the count is back at or under what was said. The host's count itself is not changed. */

/** what is said for ``seconds`` left, as a rank: 0 for «less than 1 min», else the minutes (causes.readingText). */
const rank = (seconds: number) => (seconds < 60 ? 0 : Math.ceil(seconds / 60));

/** The host's reading as the window may say it after ``before``, the one it holds: the same read going on keeps the
    least minutes said so far (``least``); a count above them goes without its minutes and as ``slower``. Another
    read (a different prompt, or one that starts again) keeps nothing of the last. */
export function heldReading(next: ModelReading | null, before: ModelReading | null): ModelReading | null {
  if (!next) return null;
  const same = !!before && before.total === next.total && next.done >= before.done;
  const least = same ? before!.least ?? null : null;
  if (next.seconds_left == null) return { ...next, least, slower: false };
  const now = rank(next.seconds_left);
  if (least != null && now > least) return { ...next, seconds_left: null, least, slower: true };
  return { ...next, least: now, slower: false };
}
