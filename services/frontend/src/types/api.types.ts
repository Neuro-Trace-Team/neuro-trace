export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface ApiUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Patient {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface RecentPatient extends Patient {
  patient_id: string;
  last_visited_at: string;
  examination_count: number;
  first_examination_date: string | null;
  last_examination_date: string | null;
}

export interface Examination {
  id: string;
  patient_id: string;
  uploaded_by: string;
  original_filename: string;
  file_format: string;
  file_size_bytes: number;
  examination_date: string | null;
  created_at: string;
  updated_at: string;
  status: string;
}

export interface DoctorDashboard {
  total_patients: number;
  total_examinations: number;
  examinations_by_status: Record<string, number>;
  total_analyses: number;
  completed_analyses: number;
  failed_analyses: number;
  recent_examinations: Array<{
    id: string;
    patient_id: string;
    created_at: string;
    processing_status: string;
  }>;
}

export interface PatientStatistics {
  patient_id: string;
  examination_count: number;
  first_examination_at: string | null;
  last_examination_at: string | null;
}

export interface StorageUsage {
  status: "available";
  bucket: string;
  bucket_exists: boolean;
  object_count: number;
  used_bytes: number;
}

export interface AppActivity {
  period_started_at: string;
  active_users_last_24h: number;
  failed_login_attempts_last_24h: number;
  examinations_uploaded_last_24h: number;
  storage: StorageUsage | { status: "unavailable"; bucket: string };
}

export interface AdminDashboard {
  period: string;
  total_users: number;
  active_users: number;
  successful_logins: number;
  failed_logins: number;
  examinations_created: number;
  analyses_created: number;
  preprocessing_failures: number;
  analysis_failures: number;
  exports: number;
}

export interface AuditLog {
  id: string;
  event_code: string;
  user_id: string | null;
  resource_type: string | null;
  resource_id: string | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  request_id: string | null;
  created_at: string;
}

export interface ExaminationResult {
  analysis: {
    id: string;
    status: string;
    model_name: string;
    model_version: string;
    created_at: string;
  };
  result: {
    pain_level: number | string | null;
    confidence: number | string | null;
    result: Record<string, unknown> | null;
    explanation: Record<string, unknown> | null;
  };
}

export interface PainAssessment {
  id: string;
  pain_level: number | string;
  scale: string;
  notes: string | null;
  assessed_at: string;
}

export interface BackendReadiness {
  status: string;
  dependencies: Record<string, string>;
}
