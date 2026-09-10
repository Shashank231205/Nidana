/* Who is using this machine.
 *
 * There is no authentication in this product. Scribe's `signed_by` and
 * Forensics' `actor` are strings the client sends, so this name is
 * self-declared and the UI says so where it is used rather than implying a
 * verified identity.
 *
 * Kept in sessionStorage rather than localStorage: a shared clinic machine
 * should forget the last person when the browser closes, and a name that
 * outlives the shift is a name that signs someone else's note.
 */

import { useCallback, useEffect, useState } from "react";

const KEY = "nidana.actor";

const read = (): string | null => {
  try {
    const stored = window.sessionStorage.getItem(KEY);
    return stored !== null && stored.trim().length > 0 ? stored : null;
  } catch {
    // Private mode and blocked site data both throw. The name is then held in
    // memory for this tab, which is enough for one shift.
    return null;
  }
};

export function useIdentity(): {
  actor: string | null;
  setActor: (name: string) => void;
  clear: () => void;
} {
  const [actor, setStored] = useState<string | null>(read);

  useEffect(() => {
    try {
      if (actor === null) window.sessionStorage.removeItem(KEY);
      else window.sessionStorage.setItem(KEY, actor);
    } catch {
      // Held in memory instead.
    }
  }, [actor]);

  const setActor = useCallback((name: string): void => {
    const trimmed = name.trim();
    if (trimmed.length > 0) setStored(trimmed);
  }, []);

  const clear = useCallback((): void => setStored(null), []);

  return { actor, setActor, clear };
}
