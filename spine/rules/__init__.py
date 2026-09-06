"""The deterministic rule engine, shared by every service.

One engine, several rule sets: Consult contributes red flags, Rx interaction and
duplicate therapy checks, Labs critical value thresholds, Scribe note
completeness, Forensics protocol compliance. The engine is generic over a rule
set; the rules and their action vocabulary are the service's.

Anything where being wrong causes physical harm lives here and never in a prompt.
"""
