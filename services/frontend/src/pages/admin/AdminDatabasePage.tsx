import { PageTitle, SectionTitle, Surface } from "../../components/PageUI";

const storageMetrics = [
  ["Total number of files", "128 402"],
  ["Average file size", "18.4 MB"],
  ["Used storage", "2.37 TB"],
  ["Database connection", "Online"],
  ["Response time", "42 ms"],
  ["Last synchronisation", "2 mins ago"],
  ["Raw files", "1.84 TB"],
  ["Anonymized files", "0.53 TB"],
  ["Today's uploads", "142 GB"],
];

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-[#dfe1e2]/90 px-2.5 py-1">
      <p className="truncate text-[10px] text-[#193456]">{label}</p>
      <p className="truncate text-[16px] font-bold leading-5 text-[#09264d]">{value}</p>
    </div>
  );
}

function AdminDatabasePage() {
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Database Management</PageTitle>
      <div className="space-y-3">
        <Surface className="px-5 py-3">
          <SectionTitle>EEG Files Storage Monitor</SectionTitle>
          <div className="px-2">
            <div className="mb-1 flex justify-between text-[12px] font-bold text-[#384149]">
              <span>Storage usage</span><span>74%</span>
            </div>
            <div aria-label="Storage usage 74 percent" className="h-[10px] overflow-hidden rounded-full bg-[#dedfe0]" role="progressbar" aria-valuenow={74} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full w-[74%] rounded-full bg-gradient-to-r from-[#00c1ca] to-[#0071b4]" />
            </div>
            <div className="mb-1 flex justify-between text-[9px] text-[#81898c]"><span>0%</span><span>50%</span><span>100%</span></div>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
              {storageMetrics.map(([label, value]) => <Metric key={label} label={label} value={value} />)}
            </div>
          </div>
        </Surface>
        <Surface className="px-5 py-3">
          <SectionTitle>Database and AI Model Management</SectionTitle>
          <div className="space-y-2 px-2">
            <div>
              <p className="mb-1 text-[13px] font-bold text-[#43494c]">Database state</p>
              <div className="grid gap-1 sm:grid-cols-3">
                <Metric label="Records processed" value="24 860" />
                <Metric label="Personal information deleted" value="98.2%" />
                <Metric label="Last synchronisation" value="5 min ago" />
              </div>
              <div className="mt-1"><Metric label="Last event" value="2026-01-01 09:42 — automatic deletion of 412 personal data records" /></div>
            </div>
            <div>
              <p className="mb-1 text-[13px] font-bold text-[#43494c]">AI Training dataset</p>
              <div className="grid gap-1 sm:grid-cols-3">
                <Metric label="Anonymous records" value="18 304" />
                <Metric label="Current model training base" value="14 902" />
                <Metric label="Retraining readiness" value="93.1%" />
              </div>
            </div>
            <div>
              <p className="mb-1 text-[13px] font-bold text-[#43494c]">Database consistency monitor</p>
              <Metric label="Index consistency" value="100%" />
            </div>
          </div>
        </Surface>
      </div>
    </div>
  );
}

export default AdminDatabasePage;
