import { Header } from "./shell/Header";
import { SubNav } from "./shell/SubNav";
import { NameEntry } from "./shell/NameEntry";
import { Home } from "./shell/Home";
import { serviceById } from "./shell/services";
import { ServiceStatus } from "./shell/ServiceStatus";
import type { ServiceId } from "./lib/http";
import { useRoute, navigate } from "./shell/useRoute";
import { useIdentity } from "./shell/useIdentity";
import { PatientConsult } from "./services/consult/patient/PatientConsult";
import { ConsultSessions } from "./services/consult/clinician/ConsultSessions";
import { ConsultAudit } from "./services/consult/clinician/ConsultAudit";
import { ScribeEncounters } from "./services/scribe/ScribeEncounters";
import { ScribeDraft } from "./services/scribe/ScribeDraft";
import { RxCheck } from "./services/rx/RxCheck";
import { RxRead } from "./services/rx/RxRead";
import { LabsReport } from "./services/labs/LabsReport";
import { LabsExtract } from "./services/labs/LabsExtract";
import { LabsThresholds } from "./services/labs/LabsThresholds";
import { ForensicsExaminations } from "./services/forensics/ForensicsExaminations";
import { ForensicsStatutes } from "./services/forensics/ForensicsStatutes";

/* The frame, and what goes in it.
 *
 * The patient triage flow is routed before the shell and renders without it.
 * A patient mid-triage has nowhere to navigate — every other service is a
 * clinician tool — and the emergency screen is terminal, so a nav link beside
 * "go to a hospital now" is a way out of an instruction that must not have
 * one.
 */

function screenFor(service: string, screen: string | null, actor: string): JSX.Element {
  switch (`${service}/${screen ?? ""}`) {
    case "consult/":
    case "consult/sessions":
      return <ConsultSessions />;
    case "consult/audit":
      return <ConsultAudit />;
    case "scribe/":
    case "scribe/encounters":
      return <ScribeEncounters />;
    case "scribe/draft":
      return <ScribeDraft actor={actor} />;
    case "rx/":
    case "rx/check":
      return <RxCheck actor={actor} />;
    case "rx/read":
      return <RxRead />;
    case "labs/":
    case "labs/report":
      return <LabsReport actor={actor} />;
    case "labs/extract":
      return <LabsExtract />;
    case "labs/thresholds":
      return <LabsThresholds />;
    case "forensics/":
    case "forensics/examinations":
      return <ForensicsExaminations actor={actor} />;
    case "forensics/statutes":
      return <ForensicsStatutes />;
    default:
      return (
        <main className="page page-narrow">
          <h1 className="page-title">That screen does not exist.</h1>
          <p className="body secondary">Pick a service from the header.</p>
        </main>
      );
  }
}

export function App(): JSX.Element {
  const route = useRoute();
  const { actor, setActor, clear } = useIdentity();

  // Before the shell: the patient surface has no header by design.
  if (route.service === "triage") return <PatientConsult />;

  if (actor === null) {
    return (
      <NameEntry
        onSubmit={(name) => {
          setActor(name);
          navigate("/");
        }}
      />
    );
  }

  const service = route.service === null ? undefined : serviceById(route.service);

  return (
    <>
      <Header active={service?.id ?? null} actor={actor} onChangeActor={clear} />
      {service !== undefined && <SubNav service={service} active={route.screen} />}
      {service === undefined ? (
        <Home actor={actor} />
      ) : (
        /* Every service screen sits beside what the deployment can actually
         * do. A form alone on a wide screen is the emptiness this fixes, and
         * the capability list is read before typing rather than discovered in
         * a result. */
        <div className="work">
          <div className="work-main">{screenFor(service.id, route.screen, actor)}</div>
          <ServiceStatus service={service.id as ServiceId} />
        </div>
      )}
    </>
  );
}
