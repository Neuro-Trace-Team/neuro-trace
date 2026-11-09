import PageTitle from "../../components/PageTitle";
import Surface from "../../components/Surface";

type Connection = { from: string; to: string; label: string; path: string; connected: boolean };
type Service = { name: string; description: string; x: number; y: number; width: number; kind: "app" | "service" | "data" };

const services: Service[] = [
  { name: "Frontend", description: "APPLICATION", x: 24, y: 265, width: 140, kind: "app" },
  { name: "Backend", description: "API & ORCHESTRATION", x: 215, y: 265, width: 160, kind: "app" },
  { name: "Auth DB", description: "ACCOUNTS", x: 20, y: 45, width: 135, kind: "data" },
  { name: "Medical DB", description: "PATIENTS & EXAMS", x: 175, y: 45, width: 145, kind: "data" },
  { name: "Audit DB", description: "ACTIVITY LOGS", x: 340, y: 45, width: 135, kind: "data" },
  { name: "RustFS", description: "FILE STORAGE", x: 460, y: 246, width: 145, kind: "data" },
  { name: "Preprocessing", description: "EEG PROCESSING", x: 460, y: 385, width: 155, kind: "service" },
  { name: "RabbitMQ", description: "MESSAGE BROKER", x: 665, y: 385, width: 145, kind: "service" },
  { name: "ML service", description: "PREDICTIONS", x: 805, y: 195, width: 150, kind: "service" },
  { name: "Model DB", description: "ANALYSIS RESULTS", x: 805, y: 45, width: 150, kind: "data" },
];

// Placeholder data until connection monitoring is available.
const connections: Connection[] = [
  { from: "Frontend", to: "Backend", label: "API", path: "M164 301 H215", connected: true },
  { from: "Backend", to: "Auth DB", label: "Accounts", path: "M235 265 V225 H87 V117", connected: true },
  { from: "Backend", to: "Medical DB", label: "Examinations", path: "M295 265 V195 H247 V117", connected: true },
  { from: "Backend", to: "Audit DB", label: "Audit logs", path: "M335 265 V145 H407 V117", connected: true },
  { from: "Backend", to: "RustFS", label: "Examination files", path: "M375 282 H460", connected: true },
  { from: "Backend", to: "Preprocessing", label: "Processing requests", path: "M375 320 H415 V421 H460", connected: true },
  { from: "Preprocessing", to: "RustFS", label: "Recording and output files", path: "M535 385 V318", connected: true },
  { from: "Preprocessing", to: "RabbitMQ", label: "Analysis tasks", path: "M615 421 H665", connected: true },
  { from: "RabbitMQ", to: "ML service", label: "Analysis tasks and completion events", path: "M810 421 H880 V267", connected: true },
  { from: "ML service", to: "Model DB", label: "Analysis results", path: "M880 195 V117", connected: false },
  { from: "Backend", to: "ML service", label: "Results API", path: "M375 275 H405 V170 H780 V231 H805", connected: true },
  { from: "RabbitMQ", to: "Backend", label: "Analysis completion", path: "M738 457 V510 H295 V337", connected: true },
];

function AdminDatabasePage() {
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>System Status</PageTitle>
      <Surface className="border-white/80 bg-gradient-to-br from-white/65 to-[#e9f5f7]/55 p-4 shadow-[0_6px_18px_rgba(8,38,76,0.09)] sm:p-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="font-heading text-xl font-bold text-[#102d58]">System connections</h2>
            <p className="mt-1 text-sm text-[#52677b]">How the application services and data stores connect.</p>
          </div>
          <span className="rounded-lg border border-white/80 bg-white/45 px-3 py-1.5 text-xs font-semibold text-[#52677b]">Example data</span>
        </div>
        <div className="overflow-x-auto rounded-xl border border-white/80 bg-white/35">
          <svg className="block h-auto min-w-[850px] w-full" viewBox="0 0 980 550" role="img" aria-labelledby="system-diagram-title system-diagram-description">
            <title id="system-diagram-title">System connections diagram</title>
            <desc id="system-diagram-description">Example connection statuses for frontend, backend, databases, file storage, preprocessing, RabbitMQ and the ML service. All statuses are simulated.</desc>
            <defs>
              <linearGradient id="node-glass" x1="0" y1="0" x2="1" y2="1"><stop stopColor="white" stopOpacity="0.8" /><stop offset="1" stopColor="#e7f5f6" stopOpacity="0.65" /></linearGradient>
              <linearGradient id="node-primary" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f7ffff" stopOpacity="0.95" /><stop offset="1" stopColor="#c9edf0" stopOpacity="0.8" /></linearGradient>
              <filter id="node-shadow" x="-20%" y="-30%" width="140%" height="170%"><feDropShadow dx="0" dy="3" stdDeviation="5" floodColor="#123c51" floodOpacity="0.1" /></filter>
            </defs>
            {connections.map((connection) => (
              <path key={`${connection.from}-${connection.to}`} d={connection.path} fill="none" stroke={connection.connected ? "#47a984" : "#cf6c6c"} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <title>{`${connection.from} to ${connection.to}: ${connection.label} — ${connection.connected ? "connected" : "disconnected"} (example)`}</title>
              </path>
            ))}
            {services.map((service) => (
              <g key={service.name} transform={`translate(${service.x} ${service.y})`}>
                <rect width={service.width} height="72" rx="12" fill={service.kind === "app" ? "url(#node-primary)" : "url(#node-glass)"} stroke="white" strokeWidth="1.5" filter="url(#node-shadow)" />
                <text x="16" y="30" fill="#102d58" fontSize="15" fontWeight="700">{service.name}</text>
                <text x="16" y="51" fill="#62798a" fontSize="9" fontWeight="700" letterSpacing="0.07em">{service.description}</text>
              </g>
            ))}
          </svg>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs font-medium text-[#52677b]">
          <span className="flex items-center gap-2"><span className="h-0.5 w-6 rounded-full bg-[#47a984]" /> Connected</span>
          <span className="flex items-center gap-2"><span className="h-0.5 w-6 rounded-full bg-[#cf6c6c]" /> Disconnected</span>
          <span className="sm:ml-auto">Connection statuses are simulated.</span>
        </div>
        <ul className="sr-only" aria-label="Example connection statuses">
          {connections.map((connection) => <li key={`${connection.from}-${connection.to}`}>{connection.from} to {connection.to}, {connection.label}: {connection.connected ? "connected" : "disconnected"}.</li>)}
        </ul>
      </Surface>
    </div>
  );
}

export default AdminDatabasePage;
