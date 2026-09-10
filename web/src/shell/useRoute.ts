/* Routing on the hash, without a router.
 *
 * The hash rather than the path because the build is served as static files by
 * whatever the clinic already runs, and a path router needs that server to
 * rewrite unknown paths onto index.html. A deployment that forgets gets a 404
 * on refresh. The hash needs no server cooperation at all.
 *
 * `#/scribe/draft` -> { service: "scribe", screen: "draft" }
 */

import { useEffect, useState } from "react";

export interface Route {
  readonly service: string | null;
  readonly screen: string | null;
}

const parse = (hash: string): Route => {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return { service: parts[0] ?? null, screen: parts[1] ?? null };
};

export const hrefFor = (service: string, screen?: string): string =>
  screen === undefined ? `#/${service}` : `#/${service}/${screen}`;

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));

  useEffect(() => {
    const onChange = (): void => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}

export const navigate = (to: string): void => {
  window.location.hash = to.startsWith("#") ? to : `#${to}`;
};
